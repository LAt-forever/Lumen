from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.memories import MemoryRepository
from service.schemas import MemoryCandidateRead, MemoryDuplicateSuggestionRead, MemoryMerge, MemoryRead, MemoryUpdate

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


@router.get("/duplicate-suggestions", response_model=list[MemoryDuplicateSuggestionRead])
def duplicate_suggestions(db: Session = Depends(get_db)):
    return MemoryService(MemoryRepository(db)).duplicate_suggestions()


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(memory_id: int, data: MemoryUpdate, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    try:
        return service.edit(memory_id, text=data.text, memory_type=data.memory_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@router.post("/{memory_id}/forget", response_model=MemoryRead)
def forget_memory(memory_id: int, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    try:
        return service.forget(memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@router.post("/{memory_id}/merge", response_model=MemoryRead)
def merge_memory(memory_id: int, data: MemoryMerge, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    try:
        return service.merge(memory_id, target_memory_id=data.target_memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
