from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Source
from service.schemas import SourceCreate


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: SourceCreate) -> Source:
        source = Source(**data.model_dump())
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get(self, source_id: int) -> Source | None:
        return self.db.get(Source, source_id)

    def exists(self, source_id: int) -> bool:
        return self.db.get(Source, source_id) is not None

    def list(self) -> list[Source]:
        return list(self.db.scalars(select(Source).order_by(Source.created_at.desc(), Source.id.desc())))

    def list_all(self) -> list[Source]:
        return list(self.db.scalars(select(Source).order_by(Source.id.asc())))

    def delete(self, source_id: int) -> None:
        source = self.db.get(Source, source_id)
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
        source = self.db.get(Source, source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.status = status
        source.error_message = error_message
        self.db.commit()
