import asyncio
import logging

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.ingestion import IngestionService, source_type_for_filename
from service.core.runtime_embeddings import build_user_embedding_provider
from service.db import get_db
from service.models import Source, User
from service.repositories.chunks import ChunkRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.source_assets import SourceAssetRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    BookmarkImportRequest,
    BulkUploadResult,
    LinkCapture,
    SourceCreate,
    SourceDetailRead,
    SourceImageRead,
    SourceRead,
    WebCrawlRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _raise_kb_http(exc: ValueError) -> None:
    message = str(exc)
    status_code = 404 if "not found" in message else 400
    raise HTTPException(status_code=status_code, detail=message) from exc


def _active_knowledge_base(db: Session, current_user: User, knowledge_base_id: int | None):
    try:
        return KnowledgeBaseRepository(db, current_user.id).require_active(knowledge_base_id)
    except ValueError as exc:
        _raise_kb_http(exc)


def _source_data_for_kb(data: SourceCreate, knowledge_base_id: int) -> SourceCreate:
    return data.model_copy(update={"knowledge_base_id": knowledge_base_id})


def _source_repo(db: Session, current_user: User, knowledge_base_id: int) -> SourceRepository:
    return SourceRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base_id)


def _chunk_repo(db: Session, current_user: User, knowledge_base_id: int) -> ChunkRepository:
    return ChunkRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base_id)


def _failed_source(sources: SourceRepository, data: SourceCreate, message: str):
    source = sources.create(data)
    sources.mark_failed(source.id, message)
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


def _summary_status(statuses: list[str], *, empty_status: str) -> str:
    if not statuses:
        return empty_status
    unique = set(statuses)
    if "failed" in unique:
        return "failed"
    if len(unique) == 1:
        return statuses[0]
    if "pending" in unique:
        return "pending"
    return statuses[0]


def _empty_index_status(source: Source) -> str:
    if source.status == "failed":
        return "failed"
    return "pending"


def _source_detail(source, db: Session, user_id: int | None = None) -> SourceDetailRead:
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=source.knowledge_base_id).list_for_source(source.id)
    assets = SourceAssetRepository(db, user_id=user_id, knowledge_base_id=source.knowledge_base_id).list_for_source(source.id)
    runs = IndexingRunRepository(db, user_id=user_id, knowledge_base_id=source.knowledge_base_id).list_for_source(source.id)
    organization = OrganizationRepository(db, user_id=user_id)
    tags = [assignment.tag for assignment in organization.assignments_for_target("source", source.id)]
    embedding_status = _summary_status(
        [chunk.embedding_status for chunk in chunks],
        empty_status=_empty_index_status(source),
    )
    index_status = _summary_status(
        [chunk.index_status for chunk in chunks],
        empty_status=_empty_index_status(source),
    )
    has_failed_asset = any(
        asset.parse_status == "failed" or asset.embedding_status == "failed" or asset.index_status == "failed" for asset in assets
    )
    has_failed_run = any(run.status == "failed" for run in runs)
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
            "knowledge_base_id": source.knowledge_base_id,
            "knowledge_base_name": getattr(source, "knowledge_base_name", None),
            "chunk_count": len(chunks),
            "assets": assets,
            "embedding_status": embedding_status,
            "index_status": index_status,
            "graph_status": "pending",
            "indexing_runs": runs,
            "tags": tags,
            "is_favorite": organization.is_favorite("source", source.id),
            "can_retry": source.status == "failed" or has_failed_asset or has_failed_run,
        }
    )


def _source_image(source: Source, asset, db: Session, user_id: int | None = None) -> SourceImageRead:
    organization = OrganizationRepository(db, user_id=user_id)
    tags = [assignment.tag for assignment in organization.assignments_for_target("source", source.id)]
    return SourceImageRead.model_validate(
        {
            "id": source.id,
            "title": source.title,
            "source_type": source.source_type,
            "status": source.status,
            "url": source.url,
            "filename": source.filename,
            "error_message": source.error_message,
            "created_at": source.created_at,
            "knowledge_base_id": source.knowledge_base_id,
            "knowledge_base_name": getattr(source, "knowledge_base_name", None),
            "asset": asset,
            "tags": tags,
            "is_favorite": organization.is_favorite("source", source.id),
        }
    )


def _ingestion_service(
    db: Session,
    current_user: User,
    knowledge_base_id: int,
    sources: SourceRepository | None = None,
) -> IngestionService:
    scoped_sources = sources or _source_repo(db, current_user, knowledge_base_id)
    return IngestionService(
        scoped_sources,
        _chunk_repo(db, current_user, knowledge_base_id),
        source_assets=SourceAssetRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base_id),
        embeddings=build_user_embedding_provider(db, current_user.id),
    )


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    knowledge_base = _active_knowledge_base(db, current_user, data.knowledge_base_id)
    return _source_repo(db, current_user, knowledge_base.id).create(_source_data_for_kb(data, knowledge_base.id))


@router.post("/upload", response_model=BulkUploadResult)
async def upload_source(
    files: list[UploadFile] = File(),
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    knowledge_base = _active_knowledge_base(db, current_user, knowledge_base_id)
    sources = _source_repo(db, current_user, knowledge_base.id)
    service = _ingestion_service(db, current_user, knowledge_base.id, sources)

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
            source = await service.create_and_index_upload(filename, await file.read(), mime_type=file.content_type)
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
async def crawl_source(data: WebCrawlRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    knowledge_base = _active_knowledge_base(db, current_user, data.knowledge_base_id)
    sources = _source_repo(db, current_user, knowledge_base.id)
    source = sources.create(SourceCreate(title=data.url, source_type="web_crawl", url=data.url, knowledge_base_id=knowledge_base.id))
    try:
        service = _ingestion_service(db, current_user, knowledge_base.id, sources)
        await service.parse_crawl_source(source.id, data)
        service.index_existing_source(source.id)
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.post("/link", response_model=SourceRead)
async def capture_link(data: LinkCapture, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    knowledge_base = _active_knowledge_base(db, current_user, data.knowledge_base_id)
    sources = _source_repo(db, current_user, knowledge_base.id)
    source = sources.create(SourceCreate(title=data.url, source_type="link", url=data.url, knowledge_base_id=knowledge_base.id))
    try:
        service = _ingestion_service(db, current_user, knowledge_base.id, sources)
        await service.parse_link_source(source.id)
        service.index_existing_source(source.id)
    except Exception as exc:
        sources.mark_failed(source.id, str(exc))
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.get("", response_model=list[SourceRead])
def list_sources(
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    knowledge_base = _active_knowledge_base(db, current_user, knowledge_base_id)
    return _source_repo(db, current_user, knowledge_base.id).list()


@router.get("/images", response_model=list[SourceImageRead])
def list_images(
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    knowledge_base = _active_knowledge_base(db, current_user, knowledge_base_id)
    rows = SourceAssetRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base.id).list_images()
    return [_source_image(source, asset, db, current_user.id) for source, asset in rows]


@router.get("/{source_id}", response_model=SourceDetailRead)
def get_source(source_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sources = SourceRepository(db, user_id=current_user.id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_detail(source, db, current_user.id)


@router.post("/{source_id}/index", response_model=SourceRead)
def index_source(source_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sources = SourceRepository(db, user_id=current_user.id)
    existing = sources.get(source_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Source not found")
    knowledge_base = _active_knowledge_base(db, current_user, existing.knowledge_base_id)
    sources = SourceRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base.id)
    service = _ingestion_service(db, current_user, knowledge_base.id, sources)
    service.index_existing_source(source_id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/{source_id}/retry", response_model=SourceDetailRead)
async def retry_source(source_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sources = SourceRepository(db, user_id=current_user.id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    knowledge_base = _active_knowledge_base(db, current_user, source.knowledge_base_id)
    scoped_sources = SourceRepository(db, user_id=current_user.id, knowledge_base_id=knowledge_base.id)

    try:
        service = _ingestion_service(db, current_user, knowledge_base.id, scoped_sources)
        service_source = await service.retry_source(source_id)
        refreshed = scoped_sources.get(service_source.id)
    except Exception as exc:
        scoped_sources.mark_failed(source.id, str(exc))
        refreshed = scoped_sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_detail(refreshed, db, current_user.id)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sources = SourceRepository(db, user_id=current_user.id)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    ChunkRepository(db, user_id=current_user.id).delete_for_source(source_id)
    sources.delete(source_id)
    return Response(status_code=204)


@router.post("/bookmarks", response_model=BulkUploadResult)
async def import_bookmarks(data: BookmarkImportRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    knowledge_base = _active_knowledge_base(db, current_user, data.knowledge_base_id)
    sources = _source_repo(db, current_user, knowledge_base.id)
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
                        knowledge_base_id=knowledge_base.id,
                    )
                )
                service = _ingestion_service(db, current_user, knowledge_base.id, sources)
                await service.parse_bookmark_source(source.id)
                service.index_existing_source(source.id)
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
