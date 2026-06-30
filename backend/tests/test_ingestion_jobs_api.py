def test_note_submission_creates_source_and_queued_job(client, monkeypatch):
    calls = []

    class FakeAsyncResult:
        id = "task-note"

    def fake_delay(job_id):
        calls.append(job_id)
        return FakeAsyncResult()

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", fake_delay)

    response = client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "Queued note", "source_type": "note", "content": "Queued content"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["queued"] == 1
    assert payload["jobs"][0]["job_type"] == "note"
    assert payload["jobs"][0]["status"] == "queued"
    assert payload["jobs"][0]["source_title"] == "Queued note"
    assert payload["sources"][0]["status"] == "pending"
    assert calls == [payload["jobs"][0]["id"]]


def test_note_submission_keeps_knowledge_base_on_source_job_and_payload(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-kb-note"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    kb = client.post("/api/knowledge-bases", json={"name": "Queued KB"}).json()

    response = client.post(
        "/api/ingestion-jobs/notes",
        json={
            "title": "Queued scoped note",
            "source_type": "note",
            "content": "Queued scoped content",
            "knowledge_base_id": kb["id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    source = payload["sources"][0]
    job = payload["jobs"][0]
    assert source["knowledge_base_id"] == kb["id"]
    assert source["knowledge_base_name"] == "Queued KB"
    assert job["knowledge_base_id"] == kb["id"]

    from service.db import SessionLocal
    from service.repositories.ingestion_jobs import IngestionJobRepository
    from service.repositories.sources import SourceRepository
    from service.core.ingestion import parse_payload

    with SessionLocal() as db:
        persisted_source = SourceRepository(db).get(source["id"])
        persisted_job = IngestionJobRepository(db).get(job["id"])
        assert persisted_source.knowledge_base_id == kb["id"]
        assert persisted_job.knowledge_base_id == kb["id"]
        assert parse_payload(persisted_job.payload_json)["knowledge_base_id"] == kb["id"]


def test_upload_submission_can_target_knowledge_base(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-upload-kb"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    kb = client.post("/api/knowledge-bases", json={"name": "Upload KB"}).json()

    response = client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={kb['id']}",
        files=[("files", ("scoped.txt", b"Scoped upload", "text/plain"))],
    )

    assert response.status_code == 200
    payload = response.json()
    source = payload["sources"][0]
    job = payload["jobs"][0]
    assert source["knowledge_base_id"] == kb["id"]
    assert source["knowledge_base_name"] == "Upload KB"
    assert job["knowledge_base_id"] == kb["id"]

    from service.core.ingestion import parse_payload
    from service.db import SessionLocal
    from service.repositories.ingestion_jobs import IngestionJobRepository

    with SessionLocal() as db:
        persisted_job = IngestionJobRepository(db).get(job["id"])
        assert parse_payload(persisted_job.payload_json)["knowledge_base_id"] == kb["id"]


def test_link_crawl_and_bookmark_submission_can_target_knowledge_base(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-non-note-kb"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    kb = client.post("/api/knowledge-bases", json={"name": "Capture KB"}).json()
    html = """
    <!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><p>
      <DT><A HREF="https://example.com/bookmark">Bookmark</A>
    </DL><p>
    """

    cases = [
        ("/api/ingestion-jobs/links", {"url": "https://example.com/link", "knowledge_base_id": kb["id"]}),
        ("/api/ingestion-jobs/crawls", {"url": "https://example.com/crawl", "knowledge_base_id": kb["id"]}),
        ("/api/ingestion-jobs/bookmarks", {"html_content": html, "knowledge_base_id": kb["id"]}),
    ]

    from service.core.ingestion import parse_payload
    from service.db import SessionLocal
    from service.repositories.ingestion_jobs import IngestionJobRepository

    job_ids = []
    for url, body in cases:
        response = client.post(url, json=body)
        assert response.status_code == 200
        payload = response.json()
        source = payload["sources"][0]
        job = payload["jobs"][0]
        assert source["knowledge_base_id"] == kb["id"]
        assert source["knowledge_base_name"] == "Capture KB"
        assert job["knowledge_base_id"] == kb["id"]
        job_ids.append(job["id"])

    with SessionLocal() as db:
        for job_id in job_ids:
            persisted_job = IngestionJobRepository(db).get(job_id)
            assert parse_payload(persisted_job.payload_json)["knowledge_base_id"] == kb["id"]


def test_upload_submission_creates_one_job_per_file_with_shared_batch(client, monkeypatch):
    class FakeAsyncResult:
        def __init__(self, task_id):
            self.id = task_id

    calls = []

    def fake_delay(job_id):
        calls.append(job_id)
        return FakeAsyncResult(f"task-{job_id}")

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", fake_delay)

    response = client.post(
        "/api/ingestion-jobs/uploads",
        files=[
            ("files", ("a.txt", b"First queued file", "text/plain")),
            ("files", ("b.txt", b"Second queued file", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["queued"] == 2
    assert len({job["batch_id"] for job in payload["jobs"]}) == 1
    assert [job["job_type"] for job in payload["jobs"]] == ["upload", "upload"]
    assert len(calls) == 2


def test_binary_upload_submission_persists_file_for_worker(client, monkeypatch, tmp_path):
    class FakeAsyncResult:
        id = "task-pdf"

    upload_root = tmp_path / "uploads"
    monkeypatch.setattr("service.core.storage.UPLOAD_ROOT", upload_root)
    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())

    response = client.post(
        "/api/ingestion-jobs/uploads",
        files=[("files", ("queued.pdf", b"%PDF-queued-binary", "application/pdf"))],
    )

    assert response.status_code == 200
    payload = response.json()
    source = payload["sources"][0]
    assert source["source_type"] == "pdf"
    assert source["filename"].startswith(f"{source['id']}/")
    assert (upload_root / source["filename"]).read_bytes() == b"%PDF-queued-binary"


def test_bookmark_submission_creates_jobs_without_fetching_pages(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-bookmark"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    html = """
    <!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><p>
      <DT><A HREF="https://example.com/one">One</A>
      <DT><A HREF="https://example.com/two">Two</A>
    </DL><p>
    """

    response = client.post("/api/ingestion-jobs/bookmarks", json={"html_content": html})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["queued"] == 2
    assert [source["source_type"] for source in payload["sources"]] == ["bookmark", "bookmark"]
    assert [job["job_type"] for job in payload["jobs"]] == ["bookmark", "bookmark"]


def test_cancel_running_job_returns_409_and_cancel_queued_succeeds(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-cancel"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    created = client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "Cancelable", "source_type": "note", "content": "Cancel content"},
    ).json()
    job_id = created["jobs"][0]["id"]

    cancel_response = client.post(f"/api/ingestion-jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"

    retry_response = client.post(f"/api/ingestion-jobs/{job_id}/retry")
    assert retry_response.status_code == 200
    running_job_id = retry_response.json()["jobs"][0]["id"]

    from service.db import SessionLocal
    from service.repositories.ingestion_jobs import IngestionJobRepository

    with SessionLocal() as db:
        IngestionJobRepository(db).mark_running(running_job_id)

    running_cancel = client.post(f"/api/ingestion-jobs/{running_job_id}/cancel")
    assert running_cancel.status_code == 409


def test_retry_job_rejects_archived_knowledge_base(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-archived-retry"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    kb = client.post("/api/knowledge-bases", json={"name": "Archived retry KB"}).json()
    created = client.post(
        "/api/ingestion-jobs/notes",
        json={
            "title": "Retry archived",
            "source_type": "note",
            "content": "Retry archived content",
            "knowledge_base_id": kb["id"],
        },
    ).json()
    job_id = created["jobs"][0]["id"]
    cancel_response = client.post(f"/api/ingestion-jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    archived = client.post(f"/api/knowledge-bases/{kb['id']}/archive")
    assert archived.status_code == 200

    response = client.post(f"/api/ingestion-jobs/{job_id}/retry")

    assert response.status_code == 400


def test_broker_unavailable_marks_job_failed_and_returns_503(client, monkeypatch):
    def fail_delay(job_id):
        raise RuntimeError("redis down")

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", fail_delay)

    response = client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "Queue down", "source_type": "note", "content": "Queue unavailable."},
    )

    assert response.status_code == 503
    assert "队列服务不可用" in response.text


def test_list_jobs_and_batch_detail(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-list"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    created = client.post(
        "/api/ingestion-jobs/links",
        json={"url": "https://example.com/list"},
    ).json()
    batch_id = created["batch_id"]

    list_response = client.get("/api/ingestion-jobs")
    assert list_response.status_code == 200
    assert any(job["batch_id"] == batch_id for job in list_response.json())

    batch_response = client.get(f"/api/ingestion-jobs/batches/{batch_id}")
    assert batch_response.status_code == 200
    batch = batch_response.json()
    assert batch["batch_id"] == batch_id
    assert batch["total"] == 1
    assert batch["queued"] == 1


def test_list_jobs_rejects_archived_knowledge_base_filter(client):
    kb = client.post("/api/knowledge-bases", json={"name": "Archived jobs KB"}).json()
    archived = client.post(f"/api/knowledge-bases/{kb['id']}/archive")
    assert archived.status_code == 200

    response = client.get(f"/api/ingestion-jobs?knowledge_base_id={kb['id']}")

    assert response.status_code == 400
