from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.llm import OpenAICompatibleAnswerProvider
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


def test_chat_response_includes_extractive_answer_metadata():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Lumen Mode", source_type="note", content="Lumen uses grounded evidence to answer questions.")
    )
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="What does Lumen use to answer questions?"))

    assert response.confidence == "grounded"
    assert response.answer_mode == "extractive"
    assert response.fallback_reason is None


class FakeChatCompletionClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return "这是基于资料生成的中文总结。"


def test_chat_uses_llm_provider_when_evidence_is_grounded():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Lumen Evidence", source_type="note", content="Lumen must answer only from retrieved evidence.")
    )
    knowledge.index_source(source.id)
    fake_client = FakeChatCompletionClient()
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=fake_client,
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="How must Lumen answer?"))

    assert response.answer == "这是基于资料生成的中文总结。"
    assert response.answer_mode == "llm"
    assert response.confidence == "grounded"
    assert response.fallback_reason is None
    assert fake_client.calls
    assert "retrieved evidence" in fake_client.calls[0][1]["content"]


def test_llm_provider_does_not_run_without_evidence():
    _db, _sources, _knowledge, _memories, chat = make_orchestrator()
    fake_client = FakeChatCompletionClient()
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=fake_client,
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="Tell me something unsupported."))

    assert response.confidence == "weak"
    assert response.answer_mode == "extractive"
    assert response.fallback_reason == "证据不足，已使用摘录模式。"
    assert fake_client.calls == []


class FailingChatCompletionClient:
    def complete(self, messages):
        raise RuntimeError("provider down")


def test_llm_provider_falls_back_when_client_fails():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Fallback Evidence", source_type="note", content="Fallback should preserve the existing extractive answer.")
    )
    knowledge.index_source(source.id)
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=FailingChatCompletionClient(),
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="What should fallback preserve?"))

    assert response.answer_mode == "extractive"
    assert response.fallback_reason == "LLM 请求失败，已使用摘录模式。"
    assert "Fallback should preserve" in response.answer
