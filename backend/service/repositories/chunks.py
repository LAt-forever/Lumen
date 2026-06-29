import hashlib
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from service.models import Citation, Source, SourceChunk


class ChunkRepository:
    def __init__(self, db: Session, user_id: int | None = None, knowledge_base_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.knowledge_base_id = knowledge_base_id

    def _source(self, source_id: int) -> Source | None:
        stmt = select(Source).where(Source.id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(Source.knowledge_base_id == self.knowledge_base_id)
        return self.db.scalar(stmt)

    def replace_for_source(
        self,
        source_id: int,
        chunks: list[tuple[str, str]],
        *,
        embedding_status: str,
        embedding_model: str | None,
        embedding_dimensions: int | None,
        index_status: str,
    ) -> list[SourceChunk]:
        source = self._source(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        now = datetime.now(UTC).replace(tzinfo=None)
        self.db.execute(delete(Citation).where(Citation.source_id == source_id))
        self.db.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        rows = [
            SourceChunk(
                source_id=source_id,
                user_id=source.user_id,
                knowledge_base_id=source.knowledge_base_id,
                chunk_index=index,
                text=text,
                embedding_json=embedding_json,
                content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                token_count=max(1, len(text) // 4),
                embedding_status=embedding_status,
                embedding_model=embedding_model,
                embedding_dimensions=embedding_dimensions,
                embedded_at=now if embedding_status == "embedded" else None,
                index_status=index_status,
                indexed_at=now if index_status == "indexed" else None,
            )
            for index, (text, embedding_json) in enumerate(chunks)
        ]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def list_all(self) -> list[SourceChunk]:
        stmt = select(SourceChunk).join(Source)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id, SourceChunk.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(
                Source.knowledge_base_id == self.knowledge_base_id,
                SourceChunk.knowledge_base_id == self.knowledge_base_id,
            )
        return list(self.db.scalars(stmt.order_by(SourceChunk.id.asc())))

    def count_for_source(self, source_id: int) -> int:
        stmt = select(SourceChunk.id).join(Source).where(SourceChunk.source_id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id, SourceChunk.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(
                Source.knowledge_base_id == self.knowledge_base_id,
                SourceChunk.knowledge_base_id == self.knowledge_base_id,
            )
        return len(list(self.db.scalars(stmt)))

    def delete_for_source(self, source_id: int) -> None:
        source = self._source(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        self.db.execute(delete(Citation).where(Citation.source_id == source_id))
        self.db.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        self.db.commit()
