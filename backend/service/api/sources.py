from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.core.parsers import get_parser
from service.core.storage import save_temp_upload, move_to_final
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
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


_TEXT_SUFFIXES = {".txt": "text", ".md": "markdown"}


def _source_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        return _TEXT_SUFFIXES[suffix]
    if suffix == ".pdf":
        return "pdf"
    return "text"


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


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(data)


@router.post("/upload", response_model=SourceRead)
async def upload_source(file: UploadFile = File(...), db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    filename = file.filename or "Untitled file"
    suffix = Path(filename).suffix.lower()
    source_type = _source_type_for_filename(filename)
    data = await file.read()

    try:
        if suffix in _TEXT_SUFFIXES:
            content = data.decode("utf-8").strip()
        elif suffix == ".pdf":
            temp_relative = save_temp_upload(data, filename)
            temp_source = Source(
                title=filename,
                source_type="pdf",
                filename=temp_relative,
            )
            parser = get_parser("pdf")
            result = await parser.parse(temp_source)
            content = result.text.strip()
        else:
            return _failed_source(
                sources,
                SourceCreate(title=filename, source_type=source_type, filename=filename),
                "Unsupported file type",
            )
    except Exception as exc:
        return _failed_source(
            sources,
            SourceCreate(title=filename, source_type=source_type, filename=filename),
            f"Could not parse file: {exc}",
        )

    if not content:
        return _failed_source(
            sources,
            SourceCreate(title=filename, source_type=source_type, filename=filename),
            "No text content found",
        )
    return sources.create(SourceCreate(title=filename, source_type=source_type, filename=filename, content=content))


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
        result = await parser.parse(source)
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

    for bm in bookmarks:
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
            refreshed = sources.get(source.id)
            if refreshed is not None:
                result_sources.append(refreshed)
            succeeded += 1
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
                refreshed = sources.get(source.id)
                if refreshed is not None:
                    result_sources.append(refreshed)
                succeeded += 1
            except Exception:
                failed += 1

    return BulkUploadResult(
        total=len(bookmarks),
        succeeded=succeeded,
        failed=failed,
        sources=[SourceRead.model_validate(s) for s in result_sources],
    )
