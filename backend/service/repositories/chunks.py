from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from service.models import SourceChunk


class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db

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
        return list(self.db.scalars(select(SourceChunk).order_by(SourceChunk.id.asc())))
