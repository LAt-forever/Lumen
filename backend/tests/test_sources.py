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


def test_source_detail_includes_chunk_count(client):
    source = client.post(
        "/api/sources",
        json={"title": "Detail source", "source_type": "note", "content": "Chunk count visible."},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    response = client.get(f"/api/sources/{source['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == source["id"]
    assert detail["chunk_count"] >= 1


def test_delete_source_removes_it_from_future_search(client):
    source = client.post(
        "/api/sources",
        json={"title": "Delete me", "source_type": "note", "content": "DeleteMarker searchable content."},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    assert client.get("/api/search", params={"q": "DeleteMarker"}).json()
    response = client.delete(f"/api/sources/{source['id']}")

    assert response.status_code == 204
    assert client.get("/api/search", params={"q": "DeleteMarker"}).json() == []


def test_delete_missing_source_returns_404(client):
    response = client.delete("/api/sources/9999")

    assert response.status_code == 404


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
    from service.core.parsers.web_parser import WebParser

    async def fake_parse_link(self, source, **kwargs):
        from service.core.parsers.base import ParseResult

        return ParseResult(
            text="Lumen link capture should be searchable.",
            title="Lumen Link",
        )

    monkeypatch.setattr(WebParser, "_parse_link", fake_parse_link)

    response = client.post("/api/sources/link", json={"url": "https://example.com/lumen"})

    assert response.status_code == 200
    source = response.json()
    assert source["title"] == "https://example.com/lumen"
    assert source["source_type"] == "link"
    assert source["status"] == "indexed"

    search_response = client.get("/api/search", params={"q": "link capture searchable"})
    assert search_response.json()[0]["source_title"] == "https://example.com/lumen"


def test_capture_link_fetch_failure_creates_failed_source(client, monkeypatch):
    from service.core.parsers.web_parser import WebParser

    async def fail_parse_link(self, source, **kwargs):
        raise RuntimeError("Could not fetch URL")

    monkeypatch.setattr(WebParser, "_parse_link", fail_parse_link)

    response = client.post("/api/sources/link", json={"url": "https://example.invalid"})

    assert response.status_code == 200
    source = response.json()
    assert source["source_type"] == "link"
    assert source["url"] == "https://example.invalid"
    assert source["status"] == "failed"
    assert source["error_message"] == "Could not fetch URL"
