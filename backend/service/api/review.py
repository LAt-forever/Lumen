from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.review import ReviewService
from service.db import get_db
from service.models import User
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ReviewRead

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("", response_model=ReviewRead)
def review(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ReviewService(
        SourceRepository(db, user_id=current_user.id),
        MemoryRepository(db, user_id=current_user.id),
        ConversationRepository(db, user_id=current_user.id),
    ).recent()
