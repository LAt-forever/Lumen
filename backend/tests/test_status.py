def test_status_summary_reports_runtime_sources_and_pending_tag_suggestions(client):
    source = client.post(
        "/api/sources",
        json={
            "title": "Phase15 状态面板资料",
            "source_type": "note",
            "content": "Phase15 状态面板需要展示资料索引和标签建议。",
        },
    ).json()
    client.post(f"/api/sources/{source['id']}/index")
    suggestions = client.get("/api/tag-suggestions").json()
    assert suggestions

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["runtime_source"] == "extractive"
    assert payload["source_counts"]["total"] == 1
    assert payload["source_counts"]["indexed"] == 1
    assert payload["ingestion_jobs"] == {
        "queued": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "canceled": 0,
    }
    assert payload["pending_tag_suggestion_count"] >= 1
    assert any("标签建议" in action["label"] for action in payload["suggested_actions"])


def test_source_retry_reindexes_failed_source_without_deleting_history(client, monkeypatch):
    from service.core.parsers.web_parser import WebParser

    calls = {"count": 0}

    async def fake_parse_link(self, source, **kwargs):
        from service.core.parsers.base import ParseResult

        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary link failure")
        return ParseResult(text="RetryMarker 链接重试后可以索引。")

    monkeypatch.setattr(WebParser, "_parse_link", fake_parse_link)
    failed = client.post("/api/sources/link", json={"url": "https://example.com/retry"}).json()
    assert failed["status"] == "failed"

    response = client.post(f"/api/sources/{failed['id']}/retry")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == failed["id"]
    assert detail["status"] == "indexed"
    assert detail["chunk_count"] >= 1
    search = client.get("/api/search", params={"q": "RetryMarker"})
    assert search.json()[0]["source_id"] == failed["id"]


def test_status_runtime_payload_does_not_leak_api_keys(client):
    client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Secret Profile",
            "provider": "openai-compatible",
            "base_url": "https://model.example/v1",
            "model": "gpt-secret",
            "api_key": "super-secret-status-key",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": True,
        },
    )

    response = client.get("/api/status")

    assert response.status_code == 200
    assert "super-secret-status-key" not in response.text
    payload = response.json()
    assert payload["runtime"]["active_profile_name"] == "Secret Profile"


def test_status_summary_reports_ingestion_job_counts(client, monkeypatch):
    class FakeAsyncResult:
        id = "task-status"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "Status queued", "source_type": "note", "content": "Status queued content."},
    )

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["ingestion_jobs"]["queued"] == 1


def test_status_summary_includes_platform_service_health(client, monkeypatch):
    from datetime import UTC, datetime

    from service.schemas import ServiceHealthRead

    def fake_collect_service_health(settings, db_session):
        return [
            ServiceHealthRead(
                name="postgres",
                label="PostgreSQL",
                status="ok",
                detail="SELECT 1 succeeded",
                latency_ms=1.2,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="redis",
                label="Redis",
                status="ok",
                detail="PING succeeded",
                latency_ms=2.3,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="elasticsearch",
                label="Elasticsearch",
                status="unavailable",
                detail="connection refused",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="neo4j",
                label="Neo4j",
                status="unavailable",
                detail="connection refused",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="worker",
                label="Celery Worker",
                status="unavailable",
                detail="no worker replied",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="beat",
                label="Celery Beat",
                status="unavailable",
                detail="heartbeat file not found",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
        ]

    monkeypatch.setattr("service.core.service_health.collect_service_health", fake_collect_service_health)

    response = client.get("/api/status")

    assert response.status_code == 200
    services = {item["name"]: item for item in response.json()["services"]}
    assert services["postgres"]["status"] == "ok"
    assert services["redis"]["label"] == "Redis"
    assert services["elasticsearch"]["status"] == "unavailable"
    assert services["neo4j"]["status"] == "unavailable"
    assert services["worker"]["detail"] == "no worker replied"
    assert services["beat"]["detail"] == "heartbeat file not found"
