from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate, SourceRead

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(data)


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return SourceRepository(db).list()


@router.post("/{source_id}/index", response_model=SourceRead)
def index_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    knowledge.index_source(source_id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
