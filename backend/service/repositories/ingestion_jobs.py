from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from service.models import IngestionJob, KnowledgeBase, Source

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "canceled")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class IngestionJobRepository:
    def __init__(self, db: Session, user_id: int | None = None, knowledge_base_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.knowledge_base_id = knowledge_base_id

    def create(
        self,
        job_type: str,
        batch_id: str,
        source_id: int | None,
        payload_json: str,
        progress_total: int = 1,
        message: str | None = None,
        knowledge_base_id: int | None = None,
    ) -> IngestionJob:
        resolved_knowledge_base_id = self.knowledge_base_id if self.knowledge_base_id is not None else knowledge_base_id
        if source_id is not None and (self.user_id is not None or resolved_knowledge_base_id is not None):
            stmt = select(Source.id).where(Source.id == source_id)
            if self.user_id is not None:
                stmt = stmt.where(Source.user_id == self.user_id)
            if resolved_knowledge_base_id is not None:
                stmt = stmt.where(Source.knowledge_base_id == resolved_knowledge_base_id)
            if self.db.scalar(stmt) is None:
                raise ValueError(f"source {source_id} not found")
        job = IngestionJob(
            user_id=self.user_id,
            knowledge_base_id=resolved_knowledge_base_id,
            job_type=job_type,
            batch_id=batch_id,
            source_id=source_id,
            payload_json=payload_json,
            progress_total=progress_total,
            message=message,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _attach_source_knowledge_base_names(self, jobs: list[IngestionJob]) -> None:
        sources = [job.source for job in jobs if job.source is not None]
        knowledge_base_ids = {source.knowledge_base_id for source in sources if source.knowledge_base_id is not None}
        names = {}
        if knowledge_base_ids:
            rows = self.db.execute(
                select(KnowledgeBase.id, KnowledgeBase.name).where(KnowledgeBase.id.in_(knowledge_base_ids))
            )
            names = {kb_id: name for kb_id, name in rows}
        for source in sources:
            source.knowledge_base_name = names.get(source.knowledge_base_id)

    def get(self, job_id: int) -> IngestionJob | None:
        stmt = select(IngestionJob).options(selectinload(IngestionJob.source)).where(IngestionJob.id == job_id)
        if self.user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IngestionJob.knowledge_base_id == self.knowledge_base_id)
        job = self.db.scalars(stmt).first()
        if job is not None:
            self._attach_source_knowledge_base_names([job])
        return job

    def list_recent(self, status: str | None = None, batch_id: str | None = None, limit: int = 50) -> list[IngestionJob]:
        stmt = select(IngestionJob).options(selectinload(IngestionJob.source))
        if self.user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IngestionJob.knowledge_base_id == self.knowledge_base_id)
        if status:
            stmt = stmt.where(IngestionJob.status == status)
        if batch_id:
            stmt = stmt.where(IngestionJob.batch_id == batch_id)
        stmt = stmt.order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc()).limit(limit)
        jobs = list(self.db.scalars(stmt))
        self._attach_source_knowledge_base_names(jobs)
        return jobs

    def list_for_batch(self, batch_id: str) -> list[IngestionJob]:
        stmt = (
            select(IngestionJob)
            .options(selectinload(IngestionJob.source))
            .where(IngestionJob.batch_id == batch_id)
            .order_by(IngestionJob.id.asc())
        )
        if self.user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IngestionJob.knowledge_base_id == self.knowledge_base_id)
        jobs = list(self.db.scalars(stmt))
        self._attach_source_knowledge_base_names(jobs)
        return jobs

    def mark_queued(self, job_id: int, celery_task_id: str) -> IngestionJob:
        job = self._required(job_id)
        job.status = "queued"
        job.celery_task_id = celery_task_id
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_running(self, job_id: int, celery_task_id: str | None = None) -> IngestionJob:
        job = self._required(job_id)
        job.status = "running"
        if celery_task_id:
            job.celery_task_id = celery_task_id
        job.started_at = _utcnow()
        job.finished_at = None
        job.error_message = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_progress(self, job_id: int, current: int, total: int, message: str) -> IngestionJob:
        job = self._required(job_id)
        job.progress_current = current
        job.progress_total = total
        job.message = message
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_succeeded(self, job_id: int, message: str | None = None) -> IngestionJob:
        job = self._required(job_id)
        job.status = "succeeded"
        job.progress_current = job.progress_total
        if message:
            job.message = message
        job.error_message = None
        job.finished_at = _utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job_id: int, error_message: str) -> IngestionJob:
        job = self._required(job_id)
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = _utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def cancel_queued(self, job_id: int) -> IngestionJob | None:
        job = self._required(job_id)
        if job.status != "queued":
            return None
        job.status = "canceled"
        job.message = "已取消"
        job.finished_at = _utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def stale_running_jobs(self) -> list[IngestionJob]:
        stmt = select(IngestionJob).where(IngestionJob.status == "running")
        if self.user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IngestionJob.knowledge_base_id == self.knowledge_base_id)
        stmt = stmt.order_by(IngestionJob.id.asc())
        return list(self.db.scalars(stmt))

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in JOB_STATUSES}
        stmt = select(IngestionJob)
        if self.user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IngestionJob.knowledge_base_id == self.knowledge_base_id)
        for job in self.db.scalars(stmt):
            if job.status in counts:
                counts[job.status] += 1
        return counts

    def refresh(self, job_id: int) -> IngestionJob:
        job = self._required(job_id)
        self.db.refresh(job)
        return job

    def _required(self, job_id: int) -> IngestionJob:
        job = self.get(job_id)
        if job is None:
            raise ValueError(f"ingestion job {job_id} not found")
        return job
