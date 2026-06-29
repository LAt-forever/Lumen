from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from service.models import Citation, Source, SourceChunk


class ChunkRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def replace_for_source(self, source_id: int, chunks: list[tuple[str, str]]) -> list[SourceChunk]:
        self.db.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        rows = [
            SourceChunk(source_id=source_id, chunk_index=index, text=text, embedding_json=embedding_json)
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
            stmt = stmt.where(Source.user_id == self.user_id)
        return list(self.db.scalars(stmt.order_by(SourceChunk.id.asc())))

    def count_for_source(self, source_id: int) -> int:
        stmt = select(SourceChunk.id).join(Source).where(SourceChunk.source_id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        return len(list(self.db.scalars(stmt)))

    def delete_for_source(self, source_id: int) -> None:
        self.db.execute(delete(Citation).where(Citation.source_id == source_id))
        self.db.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        self.db.commit()
