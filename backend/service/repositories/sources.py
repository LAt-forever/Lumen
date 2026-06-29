from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Source
from service.schemas import SourceCreate


class SourceRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _owned_select(self):
        stmt = select(Source)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        return stmt

    def _owned_get(self, source_id: int) -> Source | None:
        if self.user_id is None:
            return self.db.get(Source, source_id)
        return self.db.scalar(select(Source).where(Source.id == source_id, Source.user_id == self.user_id))

    def create(self, data: SourceCreate) -> Source:
        source = Source(**data.model_dump(), user_id=self.user_id)
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get(self, source_id: int) -> Source | None:
        return self._owned_get(source_id)

    def exists(self, source_id: int) -> bool:
        return self._owned_get(source_id) is not None

    def list(self) -> list[Source]:
        return list(self.db.scalars(self._owned_select().order_by(Source.created_at.desc(), Source.id.desc())))

    def list_all(self) -> list[Source]:
        return list(self.db.scalars(self._owned_select().order_by(Source.id.asc())))

    def failed_sources(self, limit: int = 10) -> list[Source]:
        stmt = (
            select(Source)
            .where(Source.status == "failed")
            .order_by(Source.updated_at.desc(), Source.id.desc())
            .limit(limit)
        )
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        return list(self.db.scalars(stmt))

    def status_counts(self) -> dict[str, int]:
        counts = {"total": 0, "indexed": 0, "failed": 0, "pending": 0, "parsing": 0}
        for source in self.list_all():
            counts["total"] += 1
            if source.status in counts:
                counts[source.status] += 1
        return counts

    def update_content(self, source_id: int, content: str) -> Source:
        source = self._owned_get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.content = content
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_title(self, source_id: int, title: str) -> Source:
        source = self._owned_get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.title = title
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_filename(self, source_id: int, filename: str) -> Source:
        source = self._owned_get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.filename = filename
        self.db.commit()
        self.db.refresh(source)
        return source

    def delete(self, source_id: int) -> None:
        source = self._owned_get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        self.db.delete(source)
        self.db.commit()

    def mark_parsing(self, source_id: int) -> None:
        self._set_status(source_id, "parsing", None)

    def mark_indexed(self, source_id: int) -> None:
        self._set_status(source_id, "indexed", None)

    def mark_failed(self, source_id: int, message: str) -> None:
        self._set_status(source_id, "failed", message)

    def _set_status(self, source_id: int, status: str, error_message: str | None) -> None:
        source = self._owned_get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.status = status
        source.error_message = error_message
        self.db.commit()
