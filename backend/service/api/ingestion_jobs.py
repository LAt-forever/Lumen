from __future__ import annotations

import json
from uuid import uuid4

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from service.core.ingestion import decode_text_upload, source_type_for_filename
from service.core.storage import move_to_final, resolve_file_path, save_temp_upload
from service.db import get_db
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    BookmarkImportRequest,
    IngestionBatchRead,
    IngestionJobRead,
    LinkCapture,
    SourceCreate,
    SourceRead,
    WebCrawlRequest,
)
from service.worker import process_ingestion_job

router = APIRouter(prefix="/api/ingestion-jobs", tags=["ingestion-jobs"])


def _job_read(job) -> IngestionJobRead:
    return IngestionJobRead(
        id=job.id,
        batch_id=job.batch_id,
        source_id=job.source_id,
        source_title=job.source.title if job.source else None,
        job_type=job.job_type,
        status=job.status,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        message=job.message,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _batch_response(batch_id: str, jobs: list, sources: list) -> IngestionBatchRead:
    counts = {"queued": 0, "running": 0, "succeeded": 0, "failed": 0, "canceled": 0}
    for job in jobs:
        if job.status in counts:
            counts[job.status] += 1
    return IngestionBatchRead(
        batch_id=batch_id,
        total=len(jobs),
        queued=counts["queued"],
        running=counts["running"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        canceled=counts["canceled"],
        jobs=[_job_read(job) for job in jobs],
        sources=[SourceRead.model_validate(source) for source in sources],
    )


def _enqueue_or_503(db: Session, job, source_id: int | None = None):
    jobs = IngestionJobRepository(db)
    sources = SourceRepository(db)
    try:
        result = process_ingestion_job.delay(job.id)
    except Exception as exc:
        jobs.mark_failed(job.id, f"队列服务不可用: {exc}")
        if source_id is not None:
            sources.mark_failed(source_id, "队列服务不可用，请启动 Redis 和 worker 后重试。")
        raise HTTPException(status_code=503, detail="队列服务不可用，请启动 Redis 和 worker 后重试。") from exc
    return jobs.mark_queued(job.id, result.id)


@router.post("/notes", response_model=IngestionBatchRead)
def enqueue_note(data: SourceCreate, db: Session = Depends(get_db)):
    if data.source_type != "note":
        raise HTTPException(status_code=422, detail="Only note sources can be submitted here")
    batch_id = str(uuid4())
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    source = sources.create(data)
    job = jobs.create(
        job_type="note",
        batch_id=batch_id,
        source_id=source.id,
        payload_json=json.dumps({"source_id": source.id}),
        progress_total=3,
        message="已加入队列",
    )
    job = _enqueue_or_503(db, job, source.id)
    return _batch_response(batch_id, [job], [source])


@router.post("/uploads", response_model=IngestionBatchRead)
async def enqueue_uploads(files: list[UploadFile] = File(), db: Session = Depends(get_db)):
    batch_id = str(uuid4())
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    created_jobs = []
    created_sources = []

    for file in files:
        filename = file.filename or "Untitled file"
        source_type = source_type_for_filename(filename)
        if source_type is None:
            source = sources.create(SourceCreate(title=filename, source_type="text", filename=filename))
            sources.mark_failed(source.id, "Unsupported file type")
            job = jobs.create(
                job_type="upload",
                batch_id=batch_id,
                source_id=source.id,
                payload_json=json.dumps({"source_id": source.id, "filename": filename}),
                progress_total=1,
                message="不支持的文件类型",
            )
            job = jobs.mark_failed(job.id, "Unsupported file type")
        else:
            file_data = await file.read()
            if source_type in ("text", "markdown"):
                content = decode_text_upload(file_data)
                source = sources.create(
                    SourceCreate(title=filename, source_type=source_type, filename=filename, content=content)
                )
            else:
                temp_relative = save_temp_upload(file_data, filename)
                try:
                    source = sources.create(SourceCreate(title=filename, source_type=source_type, filename=temp_relative))
                    final_relative = move_to_final(temp_relative, source.id, filename)
                    temp_relative = ""
                    sources.update_filename(source.id, final_relative)
                    source = sources.get(source.id) or source
                finally:
                    if temp_relative:
                        resolve_file_path(temp_relative).unlink(missing_ok=True)
            job = jobs.create(
                job_type="upload",
                batch_id=batch_id,
                source_id=source.id,
                payload_json=json.dumps({"source_id": source.id, "filename": filename}),
                progress_total=3,
                message="已加入队列",
            )
            job = _enqueue_or_503(db, job, source.id)
        refreshed = sources.get(source.id)
        created_sources.append(refreshed or source)
        created_jobs.append(job)

    return _batch_response(batch_id, created_jobs, created_sources)


@router.post("/links", response_model=IngestionBatchRead)
def enqueue_link(data: LinkCapture, db: Session = Depends(get_db)):
    batch_id = str(uuid4())
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    source = sources.create(SourceCreate(title=data.url, source_type="link", url=data.url))
    job = jobs.create(
        job_type="link",
        batch_id=batch_id,
        source_id=source.id,
        payload_json=json.dumps({"source_id": source.id, "url": data.url}),
        progress_total=3,
        message="已加入队列",
    )
    job = _enqueue_or_503(db, job, source.id)
    return _batch_response(batch_id, [job], [source])


@router.post("/crawls", response_model=IngestionBatchRead)
def enqueue_crawl(data: WebCrawlRequest, db: Session = Depends(get_db)):
    batch_id = str(uuid4())
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    source = sources.create(SourceCreate(title=data.url, source_type="web_crawl", url=data.url))
    job = jobs.create(
        job_type="crawl",
        batch_id=batch_id,
        source_id=source.id,
        payload_json=json.dumps(data.model_dump()),
        progress_total=3,
        message="已加入队列",
    )
    job = _enqueue_or_503(db, job, source.id)
    return _batch_response(batch_id, [job], [source])


@router.post("/bookmarks", response_model=IngestionBatchRead)
def enqueue_bookmarks(data: BookmarkImportRequest, db: Session = Depends(get_db)):
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

    batch_id = str(uuid4())
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    created_jobs = []
    created_sources = []
    for bookmark in bookmarks:
        source = sources.create(SourceCreate(title=bookmark["title"], source_type="bookmark", url=bookmark["url"]))
        job = jobs.create(
            job_type="bookmark",
            batch_id=batch_id,
            source_id=source.id,
            payload_json=json.dumps({"source_id": source.id, "url": bookmark["url"]}),
            progress_total=3,
            message="已加入队列",
        )
        created_jobs.append(_enqueue_or_503(db, job, source.id))
        created_sources.append(source)
    return _batch_response(batch_id, created_jobs, created_sources)


@router.post("/sources/{source_id}/index", response_model=IngestionBatchRead)
def enqueue_source_index(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    batch_id = str(uuid4())
    jobs = IngestionJobRepository(db)
    job = jobs.create(
        job_type="index",
        batch_id=batch_id,
        source_id=source.id,
        payload_json=json.dumps({"source_id": source.id}),
        progress_total=3,
        message="已加入队列",
    )
    job = _enqueue_or_503(db, job, source.id)
    return _batch_response(batch_id, [job], [source])


@router.get("", response_model=list[IngestionJobRead])
def list_jobs(status: str | None = None, batch_id: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    bounded_limit = min(max(limit, 1), 100)
    jobs = IngestionJobRepository(db).list_recent(status=status, batch_id=batch_id, limit=bounded_limit)
    return [_job_read(job) for job in jobs]


@router.get("/batches/{batch_id}", response_model=IngestionBatchRead)
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    jobs = IngestionJobRepository(db).list_for_batch(batch_id)
    if not jobs:
        raise HTTPException(status_code=404, detail="Batch not found")
    sources = [job.source for job in jobs if job.source is not None]
    return _batch_response(batch_id, jobs, sources)


@router.get("/{job_id}", response_model=IngestionJobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = IngestionJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return _job_read(job)


@router.post("/{job_id}/cancel", response_model=IngestionJobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = IngestionJobRepository(db).cancel_queued(job_id)
    if job is None:
        existing = IngestionJobRepository(db).get(job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        raise HTTPException(status_code=409, detail="Only queued jobs can be canceled")
    return _job_read(job)


@router.post("/{job_id}/retry", response_model=IngestionBatchRead)
def retry_job(job_id: int, db: Session = Depends(get_db)):
    jobs = IngestionJobRepository(db)
    original = jobs.get(job_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    if original.status not in ("failed", "canceled"):
        raise HTTPException(status_code=409, detail="Only failed or canceled jobs can be retried")
    batch_id = str(uuid4())
    new_job = jobs.create(
        job_type=original.job_type,
        batch_id=batch_id,
        source_id=original.source_id,
        payload_json=original.payload_json,
        progress_total=original.progress_total,
        message="已加入队列",
    )
    new_job = _enqueue_or_503(db, new_job, original.source_id)
    sources = [new_job.source] if new_job.source is not None else []
    return _batch_response(batch_id, [new_job], sources)
