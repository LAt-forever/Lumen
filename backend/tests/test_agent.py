from service.models import RerankerProfile


def test_agent_profile_activation_and_tool_run_logs(client):
    created = client.post(
        "/api/agent/profiles",
        json={
            "name": "Read-only Agent",
            "instructions": "只读工具，证据优先。",
            "enabled_tools": ["global_search", "memory_search"],
            "require_approval": True,
            "is_active": True,
        },
    )
    assert created.status_code == 200
    profile = created.json()
    assert profile["enabled_tools"] == ["global_search", "memory_search"]
    assert profile["is_active"] is True

    source = client.post(
        "/api/sources",
        json={"title": "Agent 资料", "source_type": "note", "content": "Agent 可以读取资料并记录工具日志。"},
    ).json()
    assert client.post(f"/api/sources/{source['id']}/index").status_code == 200

    run = client.post("/api/agent/runs", json={"message": "Agent 工具日志"})
    assert run.status_code == 200
    payload = run.json()
    assert "global_search" in payload["used_tools"]
    assert payload["tool_logs"]
    assert "工具" in payload["answer"]

    logs = client.get("/api/agent/tool-logs").json()
    assert any(log["tool_name"] == "global_search" for log in logs)


def test_reranker_profile_encrypts_api_key_and_activates(client):
    created = client.post(
        "/api/agent/reranker-profiles",
        json={
            "name": "External Reranker",
            "provider": "openai-compatible",
            "base_url": "https://rerank.test/v1",
            "model": "rerank-test",
            "api_key": "reranker-secret-key",
            "top_n": 30,
            "is_active": True,
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["api_key_configured"] is True
    assert payload["is_active"] is True
    assert "reranker-secret-key" not in created.text

    from service import db as dbmod

    with dbmod.SessionLocal() as db:
        profile = db.get(RerankerProfile, payload["id"])
        assert profile is not None
        assert profile.api_key is not None
        assert profile.api_key.startswith("lumen:v1:")
        assert "reranker-secret-key" not in profile.api_key
