from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Memory, MemoryCandidate


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

    def active_memories(self) -> list[Memory]:
        stmt = select(Memory).where(Memory.status.in_(["active", "edited"])).order_by(Memory.updated_at.desc(), Memory.id.desc())
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
        self.db.commit()
        self.db.refresh(target)
        return target
