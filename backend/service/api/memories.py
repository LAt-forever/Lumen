from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.memories import MemoryRepository
from service.schemas import MemoryCandidateRead, MemoryRead, MemoryUpdate

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("/candidates", response_model=list[MemoryCandidateRead])
def list_candidates(db: Session = Depends(get_db)):
    return MemoryRepository(db).pending_candidates()


@router.post("/candidates/{candidate_id}/confirm", response_model=MemoryRead)
def confirm_candidate(candidate_id: int, data: MemoryUpdate | None = None, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    try:
        return service.confirm(
            candidate_id,
            text=data.text if data else None,
            memory_type=data.memory_type if data else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory candidate not found") from exc


@router.post("/candidates/{candidate_id}/ignore")
def ignore_candidate(candidate_id: int, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    try:
        service.ignore(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory candidate not found") from exc
    return {"status": "ignored"}


@router.get("", response_model=list[MemoryRead])
def list_memories(db: Session = Depends(get_db)):
    return MemoryRepository(db).active_memories()
