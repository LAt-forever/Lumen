from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.knowledge import KnowledgeService
from service.core.retrieval import RetrievalService
from service.core.runtime_embeddings import build_local_embedding_provider, build_user_embedding_provider
from service.db import get_db
from service.models import User
from service.repositories.chunks import ChunkRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead

router = APIRouter(prefix="/api/search", tags=["search"])


def _retrieval_service(db: Session, user_id: int, knowledge_base_id: int | None) -> RetrievalService:
    try:
        knowledge_base = KnowledgeBaseRepository(db, user_id=user_id).require_active(knowledge_base_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    sources = SourceRepository(db, user_id=user_id, knowledge_base_id=knowledge_base.id)
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=knowledge_base.id)
    return RetrievalService(
        KnowledgeService(sources, chunks, embeddings=build_local_embedding_provider()),
        chunks,
        embeddings=build_user_embedding_provider(db, user_id),
    )


@router.get("", response_model=list[ChunkRead])
def search(
    q: str = Query(min_length=1),
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    retrieval = _retrieval_service(db, current_user.id, knowledge_base_id)
    return retrieval.search(q)
