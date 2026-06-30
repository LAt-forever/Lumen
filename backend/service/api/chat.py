from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.config import Settings, get_settings
from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.llm import build_answer_provider, resolve_runtime_llm_config
from service.core.memory import MemoryService
from service.core.retrieval import RetrievalService
from service.core.runtime_embeddings import build_local_embedding_provider, build_user_embedding_provider
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.memories import MemoryRepository
from service.repositories.provider_profiles import ProviderProfileRepository
from service.models import User
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ScopedRetrieval:
    def __init__(self, retrieval: RetrievalService, knowledge_base_id: int):
        self.retrieval = retrieval
        self.knowledge_base_id = knowledge_base_id

    def search(self, query: str, limit: int = 5, knowledge_base_id: int | None = None):
        if knowledge_base_id is not None and knowledge_base_id != self.knowledge_base_id:
            raise ValueError(f"knowledge base {knowledge_base_id} not available in current retrieval scope")
        return self.retrieval.search(query, limit=limit)


def _raise_kb_http(exc: ValueError) -> None:
    message = str(exc)
    status_code = 404 if "not found" in message else 400
    raise HTTPException(status_code=status_code, detail=message) from exc


def _retrieval_service(db: Session, user_id: int, knowledge_base_id: int | None) -> ScopedRetrieval:
    try:
        knowledge_base = KnowledgeBaseRepository(db, user_id=user_id).require_active(knowledge_base_id)
    except ValueError as exc:
        _raise_kb_http(exc)
    sources = SourceRepository(db, user_id=user_id, knowledge_base_id=knowledge_base.id)
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=knowledge_base.id)
    return ScopedRetrieval(
        RetrievalService(
            KnowledgeService(sources, chunks, embeddings=build_local_embedding_provider()),
            chunks,
            embeddings=build_user_embedding_provider(db, user_id),
        ),
        knowledge_base.id,
    )


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    retrieval = _retrieval_service(db, current_user.id, data.knowledge_base_id)
    memories = MemoryService(MemoryRepository(db, user_id=current_user.id))
    conversations = ConversationRepository(db, user_id=current_user.id)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db, user_id=current_user.id).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    try:
        return ChatOrchestrator(conversations, retrieval, memories, answer_provider=answer_provider).ask(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stream")
def chat_stream(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    retrieval = _retrieval_service(db, current_user.id, data.knowledge_base_id)
    memories = MemoryService(MemoryRepository(db, user_id=current_user.id))
    conversations = ConversationRepository(db, user_id=current_user.id)
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db, user_id=current_user.id).active())
    answer_provider = build_answer_provider(settings, runtime_config)
    stream = ChatOrchestrator(conversations, retrieval, memories, answer_provider=answer_provider).stream(data)
    return StreamingResponse(stream, media_type="text/event-stream")
