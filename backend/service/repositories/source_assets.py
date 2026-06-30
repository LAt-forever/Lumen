from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Source, SourceAsset


def asset_type_for_source_type(source_type: str) -> str:
    if source_type == "image":
        return "image"
    if source_type in {"pdf", "docx", "epub", "text", "markdown"}:
        return "document"
    if source_type in {"link", "bookmark", "web_crawl"}:
        return "web"
    return "source"


class SourceAssetRepository:
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

    def create_for_source(
        self,
        source_id: int,
        *,
        filename: str,
        asset_type: str,
        mime_type: str | None,
        byte_size: int,
        storage_path: str | None,
    ) -> SourceAsset:
        source = self._source(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        asset = SourceAsset(
            source_id=source.id,
            user_id=source.user_id,
            knowledge_base_id=source.knowledge_base_id,
            asset_type=asset_type,
            filename=filename,
            mime_type=mime_type,
            byte_size=byte_size,
            storage_path=storage_path,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def list_for_source(self, source_id: int) -> list[SourceAsset]:
        stmt = select(SourceAsset).join(Source).where(SourceAsset.source_id == source_id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id, SourceAsset.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(
                Source.knowledge_base_id == self.knowledge_base_id,
                SourceAsset.knowledge_base_id == self.knowledge_base_id,
            )
        return list(self.db.scalars(stmt.order_by(SourceAsset.created_at.asc(), SourceAsset.id.asc())))

    def list_images(self) -> list[tuple[Source, SourceAsset]]:
        stmt = (
            select(Source, SourceAsset)
            .join(SourceAsset, SourceAsset.source_id == Source.id)
            .where(Source.source_type == "image", SourceAsset.asset_type == "image")
        )
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id, SourceAsset.user_id == self.user_id)
        if self.knowledge_base_id is not None:
            stmt = stmt.where(
                Source.knowledge_base_id == self.knowledge_base_id,
                SourceAsset.knowledge_base_id == self.knowledge_base_id,
            )
        stmt = stmt.order_by(Source.created_at.desc(), Source.id.desc(), SourceAsset.id.asc())
        rows = [(source, asset) for source, asset in self.db.execute(stmt)]
        self._attach_knowledge_base_names([source for source, _asset in rows])
        return rows

    def mark_parse_running(self, source_id: int) -> None:
        self._update_status(source_id, "parse_status", "parsing", error_field="parse_error", error_message=None)

    def mark_parse_succeeded(self, source_id: int) -> None:
        self._update_status(source_id, "parse_status", "parsed", error_field="parse_error", error_message=None)

    def mark_parse_failed(self, source_id: int, error_message: str) -> None:
        self._update_status(source_id, "parse_status", "failed", error_field="parse_error", error_message=error_message)

    def mark_embedding_status(self, source_id: int, status: str, error_message: str | None = None) -> None:
        self._update_status(source_id, "embedding_status", status, error_field="embedding_error", error_message=error_message)

    def mark_index_status(self, source_id: int, status: str, error_message: str | None = None) -> None:
        self._update_status(source_id, "index_status", status, error_field="index_error", error_message=error_message)

    def _update_status(
        self,
        source_id: int,
        field_name: str,
        status: str,
        *,
        error_field: str,
        error_message: str | None,
    ) -> None:
        assets = self.list_for_source(source_id)
        for asset in assets:
            setattr(asset, field_name, status)
            setattr(asset, error_field, error_message)
        if assets:
            self.db.commit()

    def _attach_knowledge_base_names(self, sources: list[Source]) -> None:
        knowledge_base_ids = {source.knowledge_base_id for source in sources if source.knowledge_base_id is not None}
        if not knowledge_base_ids:
            return
        from service.models import KnowledgeBase

        rows = self.db.execute(select(KnowledgeBase.id, KnowledgeBase.name).where(KnowledgeBase.id.in_(knowledge_base_ids)))
        names = {kb_id: name for kb_id, name in rows}
        for source in sources:
            source.knowledge_base_name = names.get(source.knowledge_base_id)
