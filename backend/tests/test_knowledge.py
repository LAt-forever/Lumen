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


def test_failed_parse_marks_source_failed():
    db, service = make_service()
    source = service.sources.create(SourceCreate(title="Empty", source_type="note", content=""))

    service.index_source(source.id)
    db.refresh(source)

    assert source.status == "failed"
    assert source.error_message == "No text content found"
