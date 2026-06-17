from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.signals import worker_ready

from service import db as dbmod
from service.config import get_settings
from service.core.ingestion import IngestionService, parse_payload
from service.repositories.chunks import ChunkRepository
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.sources import SourceRepository
from service.schemas import WebCrawlRequest

logger = logging.getLogger(__name__)

settings = get_settings()
celery_app = Celery(
    "lumen",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=False,
)


def mark_stale_running_jobs_failed() -> None:
    dbmod.init_db()
    with dbmod.SessionLocal() as db:
        jobs = IngestionJobRepository(db)
        for job in jobs.stale_running_jobs():
            jobs.mark_failed(job.id, "The ingestion worker stopped before finishing this job.")


@worker_ready.connect
def _worker_ready(**_kwargs) -> None:
    mark_stale_running_jobs_failed()


@celery_app.task(name="service.worker.process_ingestion_job")
def process_ingestion_job(job_id: int) -> None:
    run_ingestion_job(job_id)


def run_ingestion_job(job_id: int) -> None:
    dbmod.init_db()
    with dbmod.SessionLocal() as db:
        jobs = IngestionJobRepository(db)
        sources = SourceRepository(db)
        chunks = ChunkRepository(db)
        job = jobs.get(job_id)
        if job is None:
            logger.warning("Ingestion job %s not found", job_id)
            return
        if job.status == "canceled":
            return
        if job.status not in ("queued", "running"):
            return

        try:
            jobs.mark_running(job.id)
            if job.source_id is not None:
                sources.mark_parsing(job.source_id)
            jobs.update_progress(job.id, 1, job.progress_total, "正在解析资料")

            service = IngestionService(sources, chunks)
            payload = parse_payload(job.payload_json)
            asyncio.run(_dispatch_job(service, job.job_type, job.source_id, payload))

            jobs.update_progress(job.id, max(job.progress_total - 1, 1), job.progress_total, "正在建立索引")
            if job.source_id is not None:
                service.index_existing_source(job.source_id)
                sources.mark_indexed(job.source_id)
            jobs.mark_succeeded(job.id, "索引完成")
        except Exception as exc:
            message = str(exc)
            if job.source_id is not None:
                try:
                    sources.mark_failed(job.source_id, message)
                except Exception:
                    logger.exception("Could not mark source %s failed", job.source_id)
            jobs.mark_failed(job.id, message)


async def _dispatch_job(
    service: IngestionService,
    job_type: str,
    source_id: int | None,
    payload: dict,
) -> None:
    if source_id is None:
        raise ValueError("Ingestion job is missing source_id")
    if job_type == "note":
        source = service._source(source_id)
        if not (source.content or "").strip():
            raise ValueError("No text content found")
        return
    if job_type == "upload":
        await service.parse_existing_source(source_id)
        return
    if job_type == "link":
        await service.parse_link_source(source_id)
        return
    if job_type == "crawl":
        request = WebCrawlRequest(
            url=str(payload.get("url") or ""),
            max_depth=int(payload.get("max_depth") or 2),
            max_pages=int(payload.get("max_pages") or 10),
            same_domain_only=bool(payload.get("same_domain_only", True)),
        )
        await service.parse_crawl_source(source_id, request)
        return
    if job_type == "bookmark":
        await service.parse_bookmark_source(source_id)
        return
    if job_type in ("index", "retry"):
        await service.retry_source(source_id)
        return
    raise ValueError(f"Unsupported ingestion job type: {job_type}")
