from sqlalchemy import func, select
from sqlalchemy.orm import Session

from service.models import Memory, MemoryCandidate, MemoryRelation


class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_candidate(self, text: str, memory_type: str, source_kind: str, source_ref: str, confidence: int) -> MemoryCandidate:
        candidate = MemoryCandidate(
            text=text,
            memory_type=memory_type,
            source_kind=source_kind,
            source_ref=source_ref,
            confidence=confidence,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def pending_candidates(self) -> list[MemoryCandidate]:
        stmt = select(MemoryCandidate).where(MemoryCandidate.status == "pending").order_by(MemoryCandidate.created_at.desc(), MemoryCandidate.id.desc())
        return list(self.db.scalars(stmt))

    def confirm(self, candidate_id: int, text: str | None = None, memory_type: str | None = None) -> Memory:
        candidate = self.db.get(MemoryCandidate, candidate_id)
        if candidate is None:
            raise ValueError(f"candidate {candidate_id} not found")
        candidate.status = "confirmed"
        memory = Memory(
            text=text or candidate.text,
            memory_type=memory_type or candidate.memory_type,
            provenance=f"{candidate.source_kind}:{candidate.source_ref}",
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def ignore(self, candidate_id: int) -> None:
        candidate = self.db.get(MemoryCandidate, candidate_id)
        if candidate is None:
            raise ValueError(f"candidate {candidate_id} not found")
        candidate.status = "ignored"
        self.db.commit()

    def get(self, memory_id: int) -> Memory | None:
        return self.db.get(Memory, memory_id)

    def exists_active(self, memory_id: int) -> bool:
        memory = self.db.get(Memory, memory_id)
        return memory is not None and memory.status in ["active", "edited"]

    def active_memories(self) -> list[Memory]:
        stmt = select(Memory).where(Memory.status.in_(["active", "edited"])).order_by(Memory.updated_at.desc(), Memory.id.desc())
        return list(self.db.scalars(stmt))

    def create_relation(
        self,
        source_memory_id: int,
        target_memory_id: int,
        relation_type: str,
        provenance: str,
        strength: int,
    ) -> MemoryRelation:
        if source_memory_id == target_memory_id:
            raise ValueError("source and target memories must be different")
        source = self.db.get(Memory, source_memory_id)
        target = self.db.get(Memory, target_memory_id)
        if source is None or target is None:
            raise ValueError("memory not found")
        if source.status not in ["active", "edited"] or target.status not in ["active", "edited"]:
            raise ValueError("both memories must be active or edited")
        existing = self.db.scalar(
            select(MemoryRelation).where(
                MemoryRelation.source_memory_id == source_memory_id,
                MemoryRelation.target_memory_id == target_memory_id,
                MemoryRelation.relation_type == relation_type,
            )
        )
        if existing is not None:
            raise ValueError("relation already exists")
        relation = MemoryRelation(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type=relation_type,
            provenance=provenance,
            strength=strength,
        )
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def get_relation(self, relation_id: int) -> MemoryRelation | None:
        return self.db.get(MemoryRelation, relation_id)

    def list_relations_for_memory(self, memory_id: int) -> list[MemoryRelation]:
        stmt = (
            select(MemoryRelation)
            .where(
                (MemoryRelation.source_memory_id == memory_id) | (MemoryRelation.target_memory_id == memory_id),
                MemoryRelation.status == "active",
            )
            .order_by(MemoryRelation.created_at.desc(), MemoryRelation.id.desc())
        )
        return list(self.db.scalars(stmt))

    def list_active_relations(self) -> list[MemoryRelation]:
        stmt = select(MemoryRelation).where(MemoryRelation.status == "active").order_by(MemoryRelation.id.asc())
        return list(self.db.scalars(stmt))

    def top_memories_by_relation_count(self, limit: int) -> list[Memory]:
        active_statuses = ("active", "edited")
        rel = MemoryRelation
        endpoint_ids = (
            select(rel.source_memory_id.label("mid"))
            .where(rel.status == "active")
            .union_all(
                select(rel.target_memory_id.label("mid")).where(rel.status == "active")
            )
            .subquery()
        )
        counts = (
            select(endpoint_ids.c.mid, func.count().label("deg"))
            .group_by(endpoint_ids.c.mid)
            .subquery()
        )
        stmt = (
            select(Memory)
            .join(counts, counts.c.mid == Memory.id)
            .where(Memory.status.in_(active_statuses))
            .order_by(counts.c.deg.desc(), Memory.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def recent_active_memories(self, limit: int) -> list[Memory]:
        active_statuses = ("active", "edited")
        stmt = (
            select(Memory)
            .where(Memory.status.in_(active_statuses))
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def forget_relation(self, relation_id: int) -> MemoryRelation:
        relation = self.db.get(MemoryRelation, relation_id)
        if relation is None:
            raise ValueError(f"relation {relation_id} not found")
        relation.status = "forgotten"
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def list_active_for_search(self) -> list[Memory]:
        stmt = select(Memory).where(Memory.status.in_(["active", "edited"])).order_by(Memory.id.asc())
        return list(self.db.scalars(stmt))

    def update(self, memory_id: int, text: str, memory_type: str) -> Memory:
        memory = self.db.get(Memory, memory_id)
        if memory is None:
            raise ValueError(f"memory {memory_id} not found")
        memory.text = text
        memory.memory_type = memory_type
        memory.status = "edited"
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def forget(self, memory_id: int) -> Memory:
        memory = self.db.get(Memory, memory_id)
        if memory is None:
            raise ValueError(f"memory {memory_id} not found")
        memory.status = "forgotten"
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def merge(self, source_memory_id: int, target_memory_id: int) -> Memory:
        if source_memory_id == target_memory_id:
            raise ValueError("source and target memories must be different")
        source = self.db.get(Memory, source_memory_id)
        target = self.db.get(Memory, target_memory_id)
        if source is None:
            raise ValueError(f"memory {source_memory_id} not found")
        if target is None:
            raise ValueError(f"memory {target_memory_id} not found")
        if source.status not in ["active", "edited"] or target.status not in ["active", "edited"]:
            raise ValueError("only active memories can be merged")
        if source.text not in target.text:
            target.text = f"{target.text.rstrip()} {source.text.strip()}"
        target.status = "edited"
        source.status = "merged"
        merged_relation = MemoryRelation(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="merged_into",
            provenance="system:merge",
            strength=100,
        )
        self.db.add(merged_relation)
        self.db.commit()
        self.db.refresh(target)
        return target
