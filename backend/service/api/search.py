from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.knowledge import KnowledgeService
from service.db import get_db
from service.models import User
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[ChunkRead])
def search(q: str = Query(min_length=1), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    knowledge = KnowledgeService(SourceRepository(db, user_id=current_user.id), ChunkRepository(db, user_id=current_user.id))
    return knowledge.search(q)
