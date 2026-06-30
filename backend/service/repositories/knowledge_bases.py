from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from service.models import KnowledgeBase, Source
from service.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate

DEFAULT_KNOWLEDGE_BASE_NAME = "默认知识库"


class KnowledgeBaseRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _scoped(self, stmt):
        if self.user_id is not None:
            stmt = stmt.where(KnowledgeBase.user_id == self.user_id)
        return stmt

    def _get_or_raise(self, kb_id: int) -> KnowledgeBase:
        knowledge_base = self.get(kb_id)
        if knowledge_base is None:
            raise ValueError(f"knowledge base {kb_id} not found")
        return knowledge_base

    def _name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        stmt = self._scoped(select(KnowledgeBase.id).where(KnowledgeBase.name == name))
        if exclude_id is not None:
            stmt = stmt.where(KnowledgeBase.id != exclude_id)
        return self.db.scalar(stmt.limit(1)) is not None

    def ensure_default(self) -> KnowledgeBase:
        stmt = self._scoped(select(KnowledgeBase).where(KnowledgeBase.is_default.is_(True))).order_by(
            KnowledgeBase.id.asc()
        )
        default = self.db.scalar(stmt)
        if default is not None:
            if default.status != "active":
                default.status = "active"
                self.db.commit()
                self.db.refresh(default)
            return default

        named_default = self.db.scalar(
            self._scoped(select(KnowledgeBase).where(KnowledgeBase.name == DEFAULT_KNOWLEDGE_BASE_NAME)).order_by(
                KnowledgeBase.id.asc()
            )
        )
        if named_default is not None:
            named_default.status = "active"
            named_default.is_default = True
            self.db.commit()
            self.db.refresh(named_default)
            return named_default

        default = KnowledgeBase(
            user_id=self.user_id,
            name=DEFAULT_KNOWLEDGE_BASE_NAME,
            status="active",
            is_default=True,
        )
        self.db.add(default)
        self.db.commit()
        self.db.refresh(default)
        return default

    def default(self) -> KnowledgeBase:
        return self.ensure_default()

    def list(self) -> list[KnowledgeBase]:
        self.ensure_default()
        stmt = self._scoped(select(KnowledgeBase)).order_by(
            KnowledgeBase.is_default.desc(), KnowledgeBase.created_at.asc(), KnowledgeBase.id.asc()
        )
        return list(self.db.scalars(stmt))

    def get(self, kb_id: int) -> KnowledgeBase | None:
        if self.user_id is None:
            return self.db.get(KnowledgeBase, kb_id)
        return self.db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == self.user_id))

    def create(self, data: KnowledgeBaseCreate) -> KnowledgeBase:
        if self._name_exists(data.name):
            raise ValueError("knowledge base name already exists")
        knowledge_base = KnowledgeBase(
            user_id=self.user_id,
            name=data.name,
            description=data.description,
            status="active",
            is_default=False,
        )
        self.db.add(knowledge_base)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("knowledge base name already exists") from exc
        self.db.refresh(knowledge_base)
        return knowledge_base

    def update(self, kb_id: int, data: KnowledgeBaseUpdate) -> KnowledgeBase:
        knowledge_base = self._get_or_raise(kb_id)
        updates = data.model_dump(exclude_unset=True)
        name = updates.get("name")
        if name is not None and name != knowledge_base.name and self._name_exists(name, exclude_id=kb_id):
            raise ValueError("knowledge base name already exists")
        for key, value in updates.items():
            setattr(knowledge_base, key, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("knowledge base name already exists") from exc
        self.db.refresh(knowledge_base)
        return knowledge_base

    def archive(self, kb_id: int) -> KnowledgeBase:
        knowledge_base = self._get_or_raise(kb_id)
        if knowledge_base.is_default:
            raise ValueError("default knowledge base cannot be archived")
        knowledge_base.status = "archived"
        self.db.commit()
        self.db.refresh(knowledge_base)
        return knowledge_base

    def restore(self, kb_id: int) -> KnowledgeBase:
        knowledge_base = self._get_or_raise(kb_id)
        knowledge_base.status = "active"
        self.db.commit()
        self.db.refresh(knowledge_base)
        return knowledge_base

    def delete_empty(self, kb_id: int) -> None:
        knowledge_base = self._get_or_raise(kb_id)
        if knowledge_base.is_default:
            raise ValueError("default knowledge base cannot be deleted")

        stmt = select(func.count()).select_from(Source).where(Source.knowledge_base_id == knowledge_base.id)
        if self.user_id is not None:
            stmt = stmt.where(Source.user_id == self.user_id)
        if int(self.db.scalar(stmt) or 0) > 0:
            raise ValueError("knowledge base is not empty")

        self.db.delete(knowledge_base)
        self.db.commit()

    def require_active(self, kb_id: int | None) -> KnowledgeBase:
        knowledge_base = self.default() if kb_id is None else self._get_or_raise(kb_id)
        if knowledge_base.status != "active":
            raise ValueError("knowledge base is not active")
        return knowledge_base
