from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from service.auth import get_current_user
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
from service.models import User
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    sources = SourceRepository(db, user_id=current_user.id)
    knowledge = KnowledgeService(sources, ChunkRepository(db, user_id=current_user.id))
    memories = MemoryService(MemoryRepository(db, user_id=current_user.id))
    conversations = ConversationRepository(db, user_id=current_user.id)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db, user_id=current_user.id).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    try:
        return ChatOrchestrator(conversations, knowledge, memories, answer_provider=answer_provider).ask(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stream")
def chat_stream(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    sources = SourceRepository(db, user_id=current_user.id)
    knowledge = KnowledgeService(sources, ChunkRepository(db, user_id=current_user.id))
    memories = MemoryService(MemoryRepository(db, user_id=current_user.id))
    conversations = ConversationRepository(db, user_id=current_user.id)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db, user_id=current_user.id).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    stream = ChatOrchestrator(conversations, knowledge, memories, answer_provider=answer_provider).stream(data)
    return StreamingResponse(stream, media_type="text/event-stream")
