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
