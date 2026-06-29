from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import IndexingRun, Source


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class IndexingRunRepository:
    def __init__(self, db: Session, user_id: int | None = None, knowledge_base_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.knowledge_base_id = knowledge_base_id

    def create(
        self,
        run_type: str,
        source_id: int | None,
        knowledge_base_id: int | None,
        job_id: int | None,
        embedding_provider_profile_id: int | None,
        embedding_model: str | None,
        embedding_dimensions: int | None,
    ) -> IndexingRun:
        source = self._source(source_id) if source_id is not None else None
        resolved_knowledge_base_id = self.knowledge_base_id
        if resolved_knowledge_base_id is None:
            resolved_knowledge_base_id = source.knowledge_base_id if source is not None else knowledge_base_id
        run = IndexingRun(
            user_id=self.user_id if self.user_id is not None else (source.user_id if source is not None else None),
            knowledge_base_id=resolved_knowledge_base_id,
            source_id=source_id,
            job_id=job_id,
            run_type=run_type,
            embedding_provider_profile_id=embedding_provider_profile_id,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_running(self, run_id: int) -> IndexingRun:
        run = self._required(run_id)
        run.status = "running"
        run.started_at = _utcnow()
        run.finished_at = None
        run.error_message = None
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_progress(
        self,
        run_id: int,
        *,
        chunks_total: int | None = None,
        chunks_embedded: int | None = None,
        chunks_indexed: int | None = None,
    ) -> IndexingRun:
        run = self._required(run_id)
        if chunks_total is not None:
            run.chunks_total = chunks_total
        if chunks_embedded is not None:
            run.chunks_embedded = chunks_embedded
        if chunks_indexed is not None:
            run.chunks_indexed = chunks_indexed
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_succeeded(
        self,
        run_id: int,
        *,
        chunks_total: int | None = None,
        chunks_embedded: int | None = None,
        chunks_indexed: int | None = None,
    ) -> IndexingRun:
        run = self.update_progress(
            run_id,
            chunks_total=chunks_total,
            chunks_embedded=chunks_embedded,
            chunks_indexed=chunks_indexed,
        )
        run.status = "succeeded"
        run.error_message = None
        run.finished_at = _utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_failed(self, run_id: int, error_message: str) -> IndexingRun:
        run = self._required(run_id)
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = _utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_for_source(self, source_id: int) -> list[IndexingRun]:
        stmt = select(IndexingRun).where(IndexingRun.source_id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(IndexingRun.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IndexingRun.knowledge_base_id == self.knowledge_base_id)
        stmt = stmt.order_by(IndexingRun.created_at.desc(), IndexingRun.id.desc())
        return list(self.db.scalars(stmt))

    def _source(self, source_id: int) -> Source | None:
        stmt = select(Source).where(Source.id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(Source.knowledge_base_id == self.knowledge_base_id)
        source = self.db.scalar(stmt)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        return source

    def _required(self, run_id: int) -> IndexingRun:
        stmt = select(IndexingRun).where(IndexingRun.id == run_id)
        if self.user_id is not None:
            stmt = stmt.where(IndexingRun.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(IndexingRun.knowledge_base_id == self.knowledge_base_id)
        run = self.db.scalar(stmt)
        if run is None:
            raise ValueError(f"indexing run {run_id} not found")
        return run
