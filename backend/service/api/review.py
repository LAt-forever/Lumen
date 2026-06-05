from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.core.review import ReviewService
from service.db import get_db
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ReviewRead

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("", response_model=ReviewRead)
def review(db: Session = Depends(get_db)):
    return ReviewService(
        SourceRepository(db),
        MemoryRepository(db),
        ConversationRepository(db),
    ).recent()
