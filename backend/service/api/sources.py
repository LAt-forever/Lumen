import asyncio
import logging

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from service.core.ingestion import IngestionService, source_type_for_filename
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


def _ingestion_service(db: Session) -> IngestionService:
    return IngestionService(SourceRepository(db), ChunkRepository(db))


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(data)


@router.post("/upload", response_model=BulkUploadResult)
async def upload_source(files: list[UploadFile] = File(), db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    service = IngestionService(sources, ChunkRepository(db))

    result_sources: list[Source] = []
    succeeded = 0
    failed = 0

    for file in files:
        filename = file.filename or "Untitled file"
        source_type = source_type_for_filename(filename)
        if source_type is None:
            failed_source = _failed_source(
                sources,
                SourceCreate(title=filename, source_type="text", filename=filename),
                "Unsupported file type",
            )
            result_sources.append(failed_source)
            failed += 1
            continue
        try:
            source = await service.create_and_index_upload(filename, await file.read())
            result_sources.append(source)
            if source.status == "failed":
                failed += 1
            else:
                succeeded += 1
        except Exception as exc:
            failed_source = _failed_source(
                sources,
                SourceCreate(title=filename, source_type=source_type, filename=filename),
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
    source = sources.create(SourceCreate(title=data.url, source_type="web_crawl", url=data.url))
    try:
        service = IngestionService(sources, ChunkRepository(db))
        await service.parse_crawl_source(source.id, data)
        service.index_existing_source(source.id)
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.post("/link", response_model=SourceRead)
async def capture_link(data: LinkCapture, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    source = sources.create(SourceCreate(title=data.url, source_type="link", url=data.url))
    try:
        service = IngestionService(sources, ChunkRepository(db))
        await service.parse_link_source(source.id)
        service.index_existing_source(source.id)
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
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
    service = IngestionService(sources, ChunkRepository(db))
    service.index_existing_source(source_id)
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

    try:
        service_source = await _ingestion_service(db).retry_source(source_id)
        refreshed = sources.get(service_source.id)
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
        refreshed = sources.get(source.id)
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
    sources = SourceRepository(db)
    soup = BeautifulSoup(data.html_content, "html.parser")
    bookmarks = []

    for dt in soup.find_all("dt"):
        a_tag = dt.find("a")
        if a_tag is None:
            continue
        href = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)
        if href and title:
            bookmarks.append({"title": title, "url": href})

    if not bookmarks:
        raise HTTPException(status_code=400, detail="No bookmarks found in HTML content")

    result_sources: list[Source] = []
    semaphore = asyncio.Semaphore(5)

    async def _import_one(bm: dict) -> Source | None:
        async with semaphore:
            try:
                source = sources.create(
                    SourceCreate(
                        title=bm["title"],
                        source_type="bookmark",
                        url=bm["url"],
                    )
                )
                await IngestionService(sources, ChunkRepository(db)).parse_bookmark_source(source.id)
                IngestionService(sources, ChunkRepository(db)).index_existing_source(source.id)
                return sources.get(source.id)
            except Exception:
                logger.exception("Could not import bookmark %s", bm.get("url"))
                return None

    results = await asyncio.gather(*[_import_one(bm) for bm in bookmarks])
    for result in results:
        if result is not None:
            result_sources.append(result)

    return BulkUploadResult(
        total=len(bookmarks),
        succeeded=len(result_sources),
        failed=len(bookmarks) - len(result_sources),
        sources=[SourceRead.model_validate(s) for s in result_sources],
    )
