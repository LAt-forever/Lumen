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


def test_chat_does_not_ground_answer_on_unrelated_hash_collision():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(
            title="6月4日工作日报",
            source_type="note",
            content="2026年6月4日完成图片生产功能集成，整理 Worker 轮询出图流程，并检查 format 输出。",
        )
    )
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="2026年6月1日做了什么工作？"))

    assert response.confidence == "weak"
    assert response.citations == []
    assert "还没有足够证据" in response.answer


def test_chat_focuses_citation_on_matching_date_inside_chunk():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(
            title="连续工作日报",
            source_type="note",
            content=(
                "时间 | 2026年6月4日 记录 | 兰贺征 "
                "今日工作内容：完成图片生产功能集成，整理 Worker 轮询出图流程。 "
                "时间 | 2026年6月1日 记录 | 兰贺征 "
                "今日工作内容：完成总控中心功能组件添加，优化登录页和侧边栏。"
            ),
        )
    )
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="2026年6月1日做了什么工作？"))

    assert response.confidence == "grounded"
    assert "完成总控中心功能组件添加" in response.answer
    assert "完成图片生产功能集成" not in response.answer
    assert response.citations[0].quote.startswith("时间 | 2026年6月1日")


def test_chat_deduplicates_identical_source_matches():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    content = "Lumen 是一个本地优先的个人 AI 知识库，用来保存资料、检索知识。"
    first = sources.create(SourceCreate(title="Lumen A", source_type="note", content=content))
    second = sources.create(SourceCreate(title="Lumen B", source_type="note", content=content))
    knowledge.index_source(first.id)
    knowledge.index_source(second.id)

    response = chat.ask(ChatRequest(message="Lumen 是什么？"))

    assert response.answer.count("本地优先的个人 AI 知识库") == 1
    assert len(response.citations) == 1


def test_chat_creates_pending_memory_candidate():
    _db, _sources, _knowledge, memories, chat = make_orchestrator()

    response = chat.ask(ChatRequest(message="我正在做 Lumen 这个个人 AI 知识库项目。"))
    pending = memories.memories.pending_candidates()

    assert response.conversation_id > 0
    assert len(pending) == 1
    assert pending[0].memory_type == "project"
