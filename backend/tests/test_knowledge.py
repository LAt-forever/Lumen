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
