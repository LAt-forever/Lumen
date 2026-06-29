from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.knowledge import KnowledgeService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_indexing_run_records_chunk_progress_after_source_index():
    db = make_session()
    sources = SourceRepository(db)
    chunks = ChunkRepository(db)
    runs = IndexingRunRepository(db)
    source = sources.create(
        SourceCreate(title="Run tracked", source_type="note", content="Tracked content should create chunks.")
    )

    KnowledgeService(sources, chunks, indexing_runs=runs).index_source(source.id)

    run = runs.list_for_source(source.id)[0]
    assert run.status == "succeeded"
    assert run.chunks_total >= 1
    assert run.chunks_embedded >= 1
