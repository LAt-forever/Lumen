from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from service.config import Settings, get_settings
from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.llm import build_answer_provider, resolve_runtime_llm_config
from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.provider_profiles import ProviderProfileRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    conversations = ConversationRepository(db)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    return ChatOrchestrator(conversations, knowledge, memories, answer_provider=answer_provider).ask(data)


@router.post("/stream")
def chat_stream(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    conversations = ConversationRepository(db)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    stream = ChatOrchestrator(conversations, knowledge, memories, answer_provider=answer_provider).stream(data)
    return StreamingResponse(stream, media_type="text/event-stream")
