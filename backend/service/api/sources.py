import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from service.config import Settings
from service.core.knowledge import KnowledgeService
from service.core.llm import HttpxChatCompletionClient
from service.core.parsers import get_parser
from service.core.storage import move_to_final, resolve_file_path, save_temp_upload
from service.db import get_db
from service.models import Source
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    BookmarkImportRequest,
    BulkUploadResult,
    LinkCapture,
    SourceCreate,
    SourceDetailRead,
    SourceRead,
    WebCrawlRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


_TYPE_MAP: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".pdf": "pdf",
    ".docx": "docx",
    ".epub": "epub",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
}

_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})


def _source_type_for_filename(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    return _TYPE_MAP.get(suffix)


def _failed_source(sources: SourceRepository, data: SourceCreate, message: str):
    source = sources.create(data)
    sources.mark_failed(source.id, message)
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


def _source_detail(source, db: Session) -> SourceDetailRead:
    return SourceDetailRead.model_validate(
        {
            "id": source.id,
            "title": source.title,
            "source_type": source.source_type,
            "status": source.status,
            "url": source.url,
            "filename": source.filename,
            "error_message": source.error_message,
            "created_at": source.created_at,
            "chunk_count": ChunkRepository(db).count_for_source(source.id),
        }
    )


@lru_cache
def _build_vision_client() -> HttpxChatCompletionClient | None:
    settings = get_settings()
    if settings.llm_api_key and settings.llm_model:
        return HttpxChatCompletionClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return None


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(data)


@router.post("/upload", response_model=BulkUploadResult)
async def upload_source(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))

    result_sources: list[Source] = []
    succeeded = 0
    failed = 0

    for file in files:
        filename = file.filename or "Untitled file"
        source_type = _source_type_for_filename(filename)

        if source_type is None:
            # Fallback to "text" for schema compatibility; error_message clarifies the real issue
            failed_source = _failed_source(
                sources,
                SourceCreate(title=filename, source_type="text", filename=filename),
                "Unsupported file type",
            )
            result_sources.append(failed_source)
            failed += 1
            continue

        file_data = await file.read()

        temp_relative: str | None = None
        try:
            # For text/markdown, decode content directly; for others, save to disk
            if source_type in ("text", "markdown"):
                # Try UTF-8 first, then common Chinese encodings, then latin-1 as last resort
                try:
                    content = file_data.decode("utf-8").strip()
                except UnicodeDecodeError:
                    for enc in ("gbk", "gb2312", "big5"):
                        try:
                            content = file_data.decode(enc).strip()
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        content = file_data.decode("utf-8", errors="replace").strip()
                source = sources.create(
                    SourceCreate(
                        title=filename,
                        source_type=source_type,
                        filename=filename,
                        content=content,
                    )
                )
                parser = get_parser(source_type)
                result = await parser.parse(source)
                final_content = result.text.strip()
                if not final_content:
                    raise ValueError("No text content found")
                if result.title:
                    sources.update_title(source.id, result.title)
            else:
                # a. Save to temp
                temp_relative = save_temp_upload(file_data, filename)

                # b. Create source with temp filename
                source = sources.create(
                    SourceCreate(
                        title=filename,
                        source_type=source_type,
                        filename=temp_relative,
                    )
                )

                # c. Move to final
                final_relative = move_to_final(temp_relative, source.id, filename)
                sources.update_filename(source.id, final_relative)

                # d. Parse
                parser = get_parser(source_type)
                kwargs: dict = {}
                if source_type == "image":
                    vision_client = _build_vision_client()
                    if vision_client is not None:
                        kwargs["vision_client"] = vision_client

                result = await parser.parse(source, **kwargs)
                final_content = result.text.strip()

                if not final_content:
                    raise ValueError("No text content found")

                # e. Update content and title
                sources.update_content(source.id, final_content)
                if result.title:
                    sources.update_title(source.id, result.title)

            # f. Index source
            knowledge.index_source(source.id)

            refreshed = sources.get(source.id)
            if refreshed is not None:
                result_sources.append(refreshed)
            succeeded += 1

        except Exception as exc:
            # Clean up temp file on failure
            if temp_relative is not None:
                try:
                    resolve_file_path(temp_relative).unlink(missing_ok=True)
                except Exception:
                    pass
            failed_source = _failed_source(
                sources,
                SourceCreate(title=filename, source_type=source_type or "text", filename=filename),
                f"Could not parse file: {exc}",
            )
            result_sources.append(failed_source)
            failed += 1

    return BulkUploadResult(
        total=len(files),
        succeeded=succeeded,
        failed=failed,
        sources=[SourceRead.model_validate(s) for s in result_sources],
    )


@router.post("/crawl", response_model=SourceRead)
async def crawl_source(data: WebCrawlRequest, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))

    try:
        source = sources.create(
            SourceCreate(
                title=data.url,
                source_type="web_crawl",
                url=data.url,
            )
        )

        parser = get_parser("web_crawl")
        result = await parser.parse(
            source,
            mode="crawl",
            max_depth=data.max_depth,
            max_pages=data.max_pages,
            same_domain_only=data.same_domain_only,
        )
        content = result.text.strip()
        if not content:
            raise ValueError("No text content found")
    except Exception as exc:
        if "source" in locals():
            sources.mark_failed(source.id, str(exc))
            refreshed = sources.get(source.id)
            if refreshed is None:
                raise HTTPException(status_code=404, detail="Source not found")
            return refreshed
        return _failed_source(
            sources,
            SourceCreate(title=data.url, source_type="web_crawl", url=data.url),
            str(exc),
        )

    sources.update_content(source.id, content)
    if result.title:
        sources.update_title(source.id, result.title)

    knowledge.index_source(source.id)
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.post("/link", response_model=SourceRead)
async def capture_link(data: LinkCapture, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    try:
        temp_source = Source(
            title=data.url,
            source_type="link",
            url=data.url,
        )
        parser = get_parser("link")
        result = await parser.parse(temp_source)
        content = result.text.strip()
        if not content:
            raise ValueError("No text content found")
    except Exception as exc:
        return _failed_source(
            sources,
            SourceCreate(title=data.url, source_type="link", url=data.url),
            str(exc),
        )
    source = sources.create(SourceCreate(title=data.url, source_type="link", url=data.url, content=content))
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    knowledge.index_source(source.id)
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return SourceRepository(db).list()


@router.get("/{source_id}", response_model=SourceDetailRead)
def get_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_detail(source, db)


@router.post("/{source_id}/index", response_model=SourceRead)
def index_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    knowledge.index_source(source_id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/{source_id}/retry", response_model=SourceDetailRead)
async def retry_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    parser = get_parser(source.source_type)
    try:
        kwargs: dict = {}
        if source.source_type == "image":
            vision_client = _build_vision_client()
            if vision_client is not None:
                kwargs["vision_client"] = vision_client
        result = await parser.parse(source, **kwargs)
        content = result.text.strip()
        if not content:
            raise ValueError("No text content found")
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
        refreshed = sources.get(source.id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="Source not found")
        return _source_detail(refreshed, db)

    sources.update_content(source.id, content)
    if result.title:
        sources.update_title(source.id, result.title)

    knowledge = KnowledgeService(sources, ChunkRepository(db))
    knowledge.index_source(source_id)
    refreshed = sources.get(source_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_detail(refreshed, db)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    ChunkRepository(db).delete_for_source(source_id)
    sources.delete(source_id)
    return Response(status_code=204)


@router.post("/bookmarks", response_model=BulkUploadResult)
async def import_bookmarks(data: BookmarkImportRequest, db: Session = Depends(get_db)):
    import asyncio

    from bs4 import BeautifulSoup

    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))

    soup = BeautifulSoup(data.html_content, "html.parser")
    bookmarks = []

    for dt in soup.find_all("dt"):
        a_tag = dt.find("a")
        if a_tag is None:
            continue
        href = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)
        if not href or not title:
            continue
        bookmarks.append({"title": title, "url": href})

    if not bookmarks:
        raise HTTPException(status_code=400, detail="No bookmarks found in HTML content")

    result_sources: list[Source] = []
    succeeded = 0
    failed = 0
    semaphore = asyncio.Semaphore(5)

    async def _import_one(bm: dict) -> Source | None:
        nonlocal succeeded, failed
        async with semaphore:
            try:
                temp_source = Source(
                    title=bm["title"],
                    source_type="bookmark",
                    url=bm["url"],
                )
                link_parser = get_parser("link")
                parse_result = await link_parser.parse(temp_source)
                content = parse_result.text.strip()
                if not content:
                    raise ValueError("No text content found")
                source = sources.create(
                    SourceCreate(
                        title=bm["title"],
                        source_type="bookmark",
                        url=bm["url"],
                        content=content,
                    )
                )
                knowledge.index_source(source.id)
                return sources.get(source.id)
            except Exception:
                fallback_content = f"标题: {bm['title']}\n链接: {bm['url']}"
                try:
                    source = sources.create(
                        SourceCreate(
                            title=bm["title"],
                            source_type="bookmark",
                            url=bm["url"],
                            content=fallback_content,
                        )
                    )
                    knowledge.index_source(source.id)
                    return sources.get(source.id)
                except Exception:
                    return None

    results = await asyncio.gather(*[_import_one(bm) for bm in bookmarks])
    for result in results:
        if result is not None:
            result_sources.append(result)
            succeeded += 1
        else:
            failed += 1

    return BulkUploadResult(
        total=len(bookmarks),
        succeeded=succeeded,
        failed=failed,
        sources=[SourceRead.model_validate(s) for s in result_sources],
    )
