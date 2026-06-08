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


def test_upload_text_file_can_be_indexed_and_searched(client):
    response = client.post(
        "/api/sources/upload",
        files={"file": ("notes.txt", b"Lumen file upload should become searchable.", "text/plain")},
    )

    assert response.status_code == 200
    source = response.json()
    assert source["title"] == "notes.txt"
    assert source["source_type"] == "text"
    assert source["status"] == "pending"

    index_response = client.post(f"/api/sources/{source['id']}/index")
    assert index_response.status_code == 200
    assert index_response.json()["status"] == "indexed"

    search_response = client.get("/api/search", params={"q": "file upload searchable"})
    assert search_response.status_code == 200
    assert search_response.json()[0]["source_title"] == "notes.txt"


def test_upload_unsupported_file_creates_failed_source(client):
    response = client.post(
        "/api/sources/upload",
        files={"file": ("archive.zip", b"not text", "application/zip")},
    )

    assert response.status_code == 200
    source = response.json()
    assert source["title"] == "archive.zip"
    assert source["status"] == "failed"
    assert "Unsupported file type" in source["error_message"]


def test_capture_link_extracts_html_text(client, monkeypatch):
    import service.api.sources as sources_api

    monkeypatch.setattr(
        sources_api,
        "_fetch_url_html",
        lambda url: "<html><head><title>Lumen Link</title></head><body><script>ignored()</script><main>Lumen link capture should be searchable.</main></body></html>",
        raising=False,
    )

    response = client.post("/api/sources/link", json={"url": "https://example.com/lumen"})

    assert response.status_code == 200
    source = response.json()
    assert source["title"] == "https://example.com/lumen"
    assert source["source_type"] == "link"
    assert source["status"] == "pending"

    client.post(f"/api/sources/{source['id']}/index")
    search_response = client.get("/api/search", params={"q": "link capture searchable"})
    assert search_response.json()[0]["source_title"] == "https://example.com/lumen"


def test_capture_link_fetch_failure_creates_failed_source(client, monkeypatch):
    import service.api.sources as sources_api

    def fail_fetch(_url: str) -> str:
        raise RuntimeError("Could not fetch URL")

    monkeypatch.setattr(sources_api, "_fetch_url_html", fail_fetch, raising=False)

    response = client.post("/api/sources/link", json={"url": "https://example.invalid"})

    assert response.status_code == 200
    source = response.json()
    assert source["source_type"] == "link"
    assert source["url"] == "https://example.invalid"
    assert source["status"] == "failed"
    assert source["error_message"] == "Could not fetch URL"
