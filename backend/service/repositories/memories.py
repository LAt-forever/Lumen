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

    def active_memories(self) -> list[Memory]:
        stmt = select(Memory).where(Memory.status.in_(["active", "edited"])).order_by(Memory.updated_at.desc(), Memory.id.desc())
        return list(self.db.scalars(stmt))
