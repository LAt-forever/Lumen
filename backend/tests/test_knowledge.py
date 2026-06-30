from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.knowledge import KnowledgeService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_service():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    return db, KnowledgeService(SourceRepository(db), ChunkRepository(db))


def test_index_source_creates_searchable_chunks():
    db, service = make_service()
    source = service.sources.create(SourceCreate(title="Lumen Note", source_type="note", content="Lumen remembers project context and cites sources."))

    service.index_source(source.id)
    db.refresh(source)

    results = service.search("project context", limit=5)
    assert source.status == "indexed"
    assert len(results) >= 1
    assert results[0].source_title == "Lumen Note"
    assert "project context" in results[0].text


def test_search_prioritizes_chinese_source_with_matching_terms():
    db, service = make_service()
    lumen_source = service.sources.create(
        SourceCreate(
            title="Lumen 简介",
            source_type="note",
            content="Lumen 是一个本地优先的个人 AI 知识库，用来保存资料、检索知识，并通过确认机制记住用户偏好。",
        )
    )
    unrelated_source = service.sources.create(
        SourceCreate(
            title="工作日报",
            source_type="note",
            content="2026年6月4日完成图片生产功能集成，整理 Worker 轮询出图流程。",
        )
    )

    service.index_source(lumen_source.id)
    service.index_source(unrelated_source.id)

    results = service.search("Lumen 是什么？", limit=2)

    assert results
    assert results[0].source_title == "Lumen 简介"
    assert "个人 AI 知识库" in results[0].text


def test_search_explains_chinese_term_matches():
    db, service = make_service()
    source = service.sources.create(
        SourceCreate(
            title="Lumen 日志",
            source_type="note",
            content="Lumen 检索需要展示引用原因。",
        )
    )
    service.index_source(source.id)

    results = service.search("Lumen 检索", limit=5)

    assert results
    assert results[0].matched_terms
    assert "匹配关键词" in results[0].match_reason


def test_search_explains_date_matches():
    db, service = make_service()
    source = service.sources.create(
        SourceCreate(
            title="日报",
            source_type="note",
            content="2026年6月1日 完成 Lumen 日期检索。",
        )
    )
    service.index_source(source.id)

    results = service.search("2026年6月1日 Lumen 做了什么", limit=5)

    assert results
    assert results[0].matched_date == "2026-06-01"
    assert "匹配日期 2026-06-01" in results[0].match_reason


def test_search_does_not_return_unrelated_date_when_no_terms_match():
    db, service = make_service()
    source = service.sources.create(
        SourceCreate(
            title="6月4日工作日报",
            source_type="note",
            content="2026年6月4日完成图片生产功能集成，整理 Worker 轮询出图流程，并检查 format 输出。",
        )
    )
    service.index_source(source.id)

    results = service.search("2026年6月1日做了什么工作？", limit=5)

    assert results == []


def test_failed_parse_marks_source_failed():
    db, service = make_service()
    source = service.sources.create(SourceCreate(title="Empty", source_type="note", content=""))

    service.index_source(source.id)
    db.refresh(source)

    assert source.status == "failed"
    assert source.error_message == "No text content found"


class BatchEmbeddingProvider:
    dimensions = 3
    profile_id = 42
    model_name = "text-embedding-test"
    is_remote = True

    def __init__(self):
        self.inputs = []

    def embed_many(self, texts):
        self.inputs.extend(texts)
        return [[1.0, 0.0, 0.0] for _text in texts]


def test_index_source_records_real_embedding_provider_metadata():
    db = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(db)
    session = sessionmaker(bind=db)()
    provider = BatchEmbeddingProvider()
    service = KnowledgeService(SourceRepository(session), ChunkRepository(session), embeddings=provider)
    source = service.sources.create(
        SourceCreate(title="Embedding Note", source_type="note", content="Real embedding metadata should be visible.")
    )

    service.index_source(source.id)

    chunks = ChunkRepository(session).list_all()
    runs = service.indexing_runs.list_for_source(source.id)
    assert provider.inputs == ["Real embedding metadata should be visible."]
    assert chunks[0].embedding_status == "embedded"
    assert chunks[0].embedding_provider_profile_id == 42
    assert chunks[0].embedding_model == "text-embedding-test"
    assert chunks[0].embedding_dimensions == 3
    assert chunks[0].index_status == "pending"
    assert runs[0].embedding_provider_profile_id == 42
    assert runs[0].embedding_model == "text-embedding-test"
    assert runs[0].embedding_dimensions == 3


class FailingBatchEmbeddingProvider(BatchEmbeddingProvider):
    def embed_many(self, texts):
        raise RuntimeError("embedding provider unavailable")


def test_index_source_marks_source_failed_when_embedding_provider_fails():
    db = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(db)
    session = sessionmaker(bind=db)()
    service = KnowledgeService(
        SourceRepository(session),
        ChunkRepository(session),
        embeddings=FailingBatchEmbeddingProvider(),
    )
    source = service.sources.create(SourceCreate(title="Broken Embedding", source_type="note", content="Needs embedding."))

    try:
        service.index_source(source.id)
    except RuntimeError:
        pass

    session.refresh(source)
    run = service.indexing_runs.list_for_source(source.id)[0]
    assert source.status == "failed"
    assert source.error_message == "embedding provider unavailable"
    assert run.status == "failed"
