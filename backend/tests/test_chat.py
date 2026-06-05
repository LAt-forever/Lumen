from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.memory import MemoryService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, SourceCreate


def make_orchestrator():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    conversations = ConversationRepository(db)
    return db, sources, knowledge, memories, ChatOrchestrator(conversations, knowledge, memories)


def test_chat_answer_includes_citation():
    db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(SourceCreate(title="Lumen Principles", source_type="note", content="Lumen answers should show clear citations."))
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="What should Lumen answers show?"))

    assert response.conversation_id > 0
    assert "citations" in response.answer.lower()
    assert len(response.citations) == 1
    assert response.citations[0].source_title == "Lumen Principles"


def test_chat_creates_pending_memory_candidate():
    _db, _sources, _knowledge, memories, chat = make_orchestrator()

    response = chat.ask(ChatRequest(message="我正在做 Lumen 这个个人 AI 知识库项目。"))
    pending = memories.memories.pending_candidates()

    assert response.conversation_id > 0
    assert len(pending) == 1
    assert pending[0].memory_type == "project"
