from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(data: ChatRequest, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    conversations = ConversationRepository(db)
    return ChatOrchestrator(conversations, knowledge, memories).ask(data)
