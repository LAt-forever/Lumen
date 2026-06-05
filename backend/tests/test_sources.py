from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.db import Base
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_source_lifecycle():
    db = make_session()
    repo = SourceRepository(db)

    source = repo.create(SourceCreate(title="Alpha Note", source_type="note", content="Alpha content"))
    assert source.id is not None
    assert source.status == "pending"

    repo.mark_parsing(source.id)
    db.refresh(source)
    assert source.status == "parsing"

    repo.mark_indexed(source.id)
    db.refresh(source)
    assert source.status == "indexed"


def test_source_failed_status_keeps_error_message():
    db = make_session()
    repo = SourceRepository(db)

    source = repo.create(SourceCreate(title="Bad Link", source_type="link", url="https://example.invalid"))
    repo.mark_failed(source.id, "Could not fetch URL")
    db.refresh(source)

    assert source.status == "failed"
    assert source.error_message == "Could not fetch URL"
