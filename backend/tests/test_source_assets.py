from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.knowledge import KnowledgeService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.source_assets import SourceAssetRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


class RemoteEmbeddingProvider:
    dimensions = 3
    model_name = "text-embedding-test"
    profile_id = 42
    is_remote = True

    def embed(self, _text):
        return [1.0, 0.0, 0.0]

    def embed_many(self, texts):
        return [[1.0, 0.0, 0.0] for _text in texts]


class RecordingProjection:
    def __init__(self):
        self.ensure_calls = 0
        self.documents = []

    def ensure_index(self):
        self.ensure_calls += 1

    def index_chunk(self, document):
        self.documents.append(document)


class FailingProjection(RecordingProjection):
    def index_chunk(self, document):
        super().index_chunk(document)
        raise RuntimeError("es projection down")


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _stub_enqueue(monkeypatch, task_id: str = "task-phase3"):
    class FakeAsyncResult:
        id = task_id

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())


def test_remote_embedding_indexes_image_chunks_into_elasticsearch_projection():
    db = _make_session()
    sources = SourceRepository(db, user_id=7, knowledge_base_id=11)
    chunks = ChunkRepository(db, user_id=7, knowledge_base_id=11)
    assets = SourceAssetRepository(db, user_id=7, knowledge_base_id=11)
    runs = IndexingRunRepository(db, user_id=7, knowledge_base_id=11)
    projection = RecordingProjection()
    source = sources.create(
        SourceCreate(
            title="diagram.png",
            source_type="image",
            content="OCR text says Phoenix launch window.",
            filename="13/diagram.png",
        )
    )
    assets.create_for_source(
        source.id,
        filename="diagram.png",
        asset_type="image",
        mime_type="image/png",
        byte_size=128,
        storage_path="13/diagram.png",
    )

    KnowledgeService(
        sources,
        chunks,
        indexing_runs=runs,
        source_assets=assets,
        embeddings=RemoteEmbeddingProvider(),
        projection=projection,
    ).index_source(source.id)

    indexed_chunk = chunks.list_for_source(source.id)[0]
    asset = assets.list_for_source(source.id)[0]
    run = runs.list_for_source(source.id)[0]
    assert projection.ensure_calls == 1
    assert [document.chunk_id for document in projection.documents] == [indexed_chunk.id]
    assert projection.documents[0].source_title == "diagram.png"
    assert projection.documents[0].text == "OCR text says Phoenix launch window."
    assert indexed_chunk.embedding_status == "embedded"
    assert indexed_chunk.index_status == "indexed"
    assert asset.embedding_status == "embedded"
    assert asset.index_status == "indexed"
    assert run.status == "succeeded"
    assert run.chunks_embedded == 1
    assert run.chunks_indexed == 1


def test_elasticsearch_projection_failure_marks_only_index_status_failed():
    db = _make_session()
    sources = SourceRepository(db, user_id=7, knowledge_base_id=11)
    chunks = ChunkRepository(db, user_id=7, knowledge_base_id=11)
    assets = SourceAssetRepository(db, user_id=7, knowledge_base_id=11)
    runs = IndexingRunRepository(db, user_id=7, knowledge_base_id=11)
    source = sources.create(
        SourceCreate(
            title="broken-diagram.png",
            source_type="image",
            content="OCR text still embedded before ES fails.",
            filename="13/broken-diagram.png",
        )
    )
    assets.create_for_source(
        source.id,
        filename="broken-diagram.png",
        asset_type="image",
        mime_type="image/png",
        byte_size=128,
        storage_path="13/broken-diagram.png",
    )

    try:
        KnowledgeService(
            sources,
            chunks,
            indexing_runs=runs,
            source_assets=assets,
            embeddings=RemoteEmbeddingProvider(),
            projection=FailingProjection(),
        ).index_source(source.id)
    except RuntimeError as exc:
        assert "es projection down" in str(exc)
    else:
        raise AssertionError("projection failure should be visible to the ingestion job")

    source_after = sources.get(source.id)
    indexed_chunk = chunks.list_for_source(source.id)[0]
    asset = assets.list_for_source(source.id)[0]
    run = runs.list_for_source(source.id)[0]
    assert source_after.status == "failed"
    assert indexed_chunk.embedding_status == "embedded"
    assert indexed_chunk.index_status == "failed"
    assert "es projection down" in indexed_chunk.index_error
    assert asset.embedding_status == "embedded"
    assert asset.index_status == "failed"
    assert "es projection down" in asset.index_error
    assert run.status == "failed"
    assert run.chunks_embedded == 1
    assert run.chunks_indexed == 0


def test_image_parsed_text_is_searchable_and_citable(client, monkeypatch, tmp_path):
    from service.core.parsers.base import ParseResult
    from service.core.parsers.image_parser import ImageParser

    monkeypatch.setattr("service.core.storage.UPLOAD_ROOT", tmp_path / "uploads")

    async def fake_parse(self, source, **kwargs):
        return ParseResult(text="图片 OCR 结果包含可搜索的 CrimsonDiagram 结论。", title=source.title)

    monkeypatch.setattr(ImageParser, "parse", fake_parse)

    upload = client.post(
        "/api/sources/upload",
        files=[("files", ("diagram.png", b"\x89PNG\r\n\x1a\nimage", "image/png"))],
    )

    assert upload.status_code == 200
    source = upload.json()["sources"][0]

    search = client.get("/api/search", params={"q": "CrimsonDiagram 结论"})
    chat = client.post("/api/chat", json={"message": "CrimsonDiagram 结论是什么？"})

    assert search.status_code == 200
    assert search.json()[0]["source_id"] == source["id"]
    assert "CrimsonDiagram" in search.json()[0]["text"]
    assert chat.status_code == 200
    assert chat.json()["citations"][0]["source_id"] == source["id"]
    assert "CrimsonDiagram" in chat.json()["citations"][0]["quote"]


def test_image_detail_and_library_return_tags_and_favorite(client, monkeypatch, tmp_path):
    _stub_enqueue(monkeypatch, "task-image-organization")
    monkeypatch.setattr("service.core.storage.UPLOAD_ROOT", tmp_path / "uploads")
    upload = client.post(
        "/api/ingestion-jobs/uploads",
        files=[("files", ("tagged.png", b"\x89PNG\r\n\x1a\nimage", "image/png"))],
    )
    source = upload.json()["sources"][0]
    tag = client.post("/api/tags", json={"name": "视觉资料", "color": "#2563eb"}).json()
    client.post("/api/tags/assignments", json={"tag_id": tag["id"], "target_type": "source", "target_id": source["id"]})
    client.post("/api/favorites", json={"target_type": "source", "target_id": source["id"]})

    detail = client.get(f"/api/sources/{source['id']}")
    images = client.get("/api/sources/images")

    assert detail.status_code == 200
    assert detail.json()["is_favorite"] is True
    assert [item["name"] for item in detail.json()["tags"]] == ["视觉资料"]
    assert images.status_code == 200
    assert images.json()[0]["is_favorite"] is True
    assert [item["name"] for item in images.json()[0]["tags"]] == ["视觉资料"]


def test_enqueue_web_source_refresh_creates_retry_job(client, monkeypatch):
    _stub_enqueue(monkeypatch, "task-refresh-web")
    source = client.post(
        "/api/sources",
        json={"title": "网页资料", "source_type": "link", "url": "https://example.com/page"},
    ).json()

    response = client.post(f"/api/ingestion-jobs/sources/{source['id']}/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["queued"] == 1
    assert payload["jobs"][0]["job_type"] == "retry"
    assert payload["jobs"][0]["source_id"] == source["id"]
    assert payload["sources"][0]["id"] == source["id"]


def test_upload_image_records_asset_metadata_and_detail_status(client, monkeypatch, tmp_path):
    _stub_enqueue(monkeypatch, "task-image-asset")
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr("service.core.storage.UPLOAD_ROOT", upload_root)

    png_bytes = b"\x89PNG\r\n\x1a\n" + (b"0" * 128)
    response = client.post(
        "/api/ingestion-jobs/uploads",
        files=[("files", ("diagram.png", png_bytes, "image/png"))],
    )

    assert response.status_code == 200
    source = response.json()["sources"][0]
    source_id = source["id"]
    assert source["source_type"] == "image"

    detail = client.get(f"/api/sources/{source_id}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["source_type"] == "image"
    assert body["chunk_count"] == 0
    assert body["embedding_status"] == "pending"
    assert body["index_status"] == "pending"
    assert body["graph_status"] == "pending"
    assert body["can_retry"] is False
    assert body["tags"] == []
    assert body["is_favorite"] is False
    assert body["indexing_runs"] == []

    asset = body["assets"][0]
    assert asset["filename"] == "diagram.png"
    assert asset["source_id"] == source_id
    assert asset["asset_type"] == "image"
    assert asset["mime_type"] == "image/png"
    assert asset["byte_size"] == len(png_bytes)
    assert asset["storage_path"] == source["filename"]
    assert asset["parse_status"] == "pending"
    assert asset["embedding_status"] == "pending"
    assert asset["index_status"] == "pending"
    assert asset["graph_status"] == "pending"
    assert asset["parse_error"] is None
    assert asset["index_error"] is None


def test_image_library_lists_only_images_in_active_knowledge_base(client, monkeypatch, tmp_path):
    _stub_enqueue(monkeypatch, "task-image-library")
    monkeypatch.setattr("service.core.storage.UPLOAD_ROOT", tmp_path / "uploads")
    first = client.post("/api/knowledge-bases", json={"name": "Images A"}).json()
    second = client.post("/api/knowledge-bases", json={"name": "Images B"}).json()

    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={first['id']}",
        files=[("files", ("alpha.png", b"\x89PNG\r\n\x1a\nalpha", "image/png"))],
    )
    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={second['id']}",
        files=[("files", ("beta.png", b"\x89PNG\r\n\x1a\nbeta", "image/png"))],
    )
    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={first['id']}",
        files=[("files", ("notes.txt", b"not an image", "text/plain"))],
    )

    response = client.get(f"/api/sources/images?knowledge_base_id={first['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert [item["title"] for item in payload] == ["alpha.png"]
    assert payload[0]["knowledge_base_id"] == first["id"]
    assert payload[0]["asset"]["filename"] == "alpha.png"
    assert payload[0]["asset"]["parse_status"] == "pending"
    assert payload[0]["is_favorite"] is False
    assert payload[0]["tags"] == []
