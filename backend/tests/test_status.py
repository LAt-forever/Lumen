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
    assert payload["pending_tag_suggestion_count"] >= 1
    assert any("标签建议" in action["label"] for action in payload["suggested_actions"])


def test_source_retry_reindexes_failed_source_without_deleting_history(client, monkeypatch):
    import service.api.sources as sources_api

    calls = {"count": 0}

    def fake_fetch(_url: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary link failure")
        return "<html><main>RetryMarker 链接重试后可以索引。</main></html>"

    monkeypatch.setattr(sources_api, "_fetch_url_html", fake_fetch, raising=False)
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
