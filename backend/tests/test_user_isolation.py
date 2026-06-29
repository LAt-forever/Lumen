def test_sources_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")

    created = client.post(
        "/api/sources",
        json={"title": "Alice note", "source_type": "note", "content": "private alice source"},
        headers=alice,
    )

    assert created.status_code == 200
    assert client.get("/api/sources", headers=alice).json()[0]["title"] == "Alice note"
    assert client.get("/api/sources", headers=bob).json() == []
    assert client.get(f"/api/sources/{created.json()['id']}", headers=bob).status_code == 404


def test_memories_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")

    chat = client.post("/api/chat", json={"message": "我正在做 Alice 的私有项目。"}, headers=alice)
    assert chat.status_code == 200
    candidates = client.get("/api/memories/candidates", headers=alice).json()
    assert candidates
    assert client.get("/api/memories/candidates", headers=bob).json() == []

    confirmed = client.post(
        f"/api/memories/candidates/{candidates[0]['id']}/confirm",
        json={"text": candidates[0]["text"], "memory_type": candidates[0]["memory_type"]},
        headers=alice,
    )
    assert confirmed.status_code == 200
    assert client.get("/api/memories", headers=alice).json()
    assert client.get("/api/memories", headers=bob).json() == []
    assert client.patch(
        f"/api/memories/{confirmed.json()['id']}",
        json={"text": "Bob cannot edit this", "memory_type": "note"},
        headers=bob,
    ).status_code == 404


def test_chat_conversations_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")

    first = client.post("/api/chat", json={"message": "Alice conversation seed"}, headers=alice)
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    bob_attempt = client.post(
        "/api/chat",
        json={"message": "Bob tries to continue Alice chat", "conversation_id": conversation_id},
        headers=bob,
    )

    assert bob_attempt.status_code == 404


def test_ingestion_jobs_are_scoped_to_current_user(client, auth_headers, monkeypatch):
    class FakeAsyncResult:
        id = "task-user-scope"

    monkeypatch.setattr("service.api.ingestion_jobs.process_ingestion_job.delay", lambda job_id: FakeAsyncResult())
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")

    created = client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "Alice queued note", "source_type": "note", "content": "queued private"},
        headers=alice,
    )
    assert created.status_code == 200
    job_id = created.json()["jobs"][0]["id"]
    batch_id = created.json()["batch_id"]

    assert client.get("/api/ingestion-jobs", headers=alice).json()[0]["id"] == job_id
    assert client.get("/api/ingestion-jobs", headers=bob).json() == []
    assert client.get(f"/api/ingestion-jobs/{job_id}", headers=bob).status_code == 404
    assert client.get(f"/api/ingestion-jobs/batches/{batch_id}", headers=bob).status_code == 404
    assert client.post(f"/api/ingestion-jobs/{job_id}/cancel", headers=bob).status_code == 404


def test_tags_and_favorites_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    source = client.post(
        "/api/sources",
        json={"title": "Alice tagged source", "source_type": "note", "content": "tag private"},
        headers=alice,
    ).json()
    tag = client.post("/api/tags", json={"name": "私有", "color": "#2563eb"}, headers=alice).json()

    assignment = client.post(
        "/api/tags/assignments",
        json={"tag_id": tag["id"], "target_type": "source", "target_id": source["id"]},
        headers=alice,
    )
    favorite = client.post(
        "/api/favorites",
        json={"target_type": "source", "target_id": source["id"]},
        headers=alice,
    )

    assert assignment.status_code == 200
    assert favorite.status_code == 200
    assert client.get("/api/tags", headers=bob).json() == []
    assert client.get("/api/favorites", headers=bob).json() == []
    assert client.post(
        "/api/tags/assignments",
        json={"tag_id": tag["id"], "target_type": "source", "target_id": source["id"]},
        headers=bob,
    ).status_code == 404
    assert client.post(
        "/api/favorites",
        json={"target_type": "source", "target_id": source["id"]},
        headers=bob,
    ).status_code == 404


def test_model_and_agent_settings_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")

    provider = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Alice model",
            "provider": "openai-compatible",
            "base_url": "https://model.example/v1",
            "model": "gpt-alice",
            "api_key": "secret",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": True,
        },
        headers=alice,
    )
    agent = client.post(
        "/api/agent/profiles",
        json={
            "name": "Alice Agent",
            "instructions": "只读。",
            "enabled_tools": ["global_search"],
            "require_approval": True,
            "is_active": True,
        },
        headers=alice,
    )
    reranker = client.post(
        "/api/agent/reranker-profiles",
        json={
            "name": "Alice reranker",
            "provider": "openai-compatible",
            "base_url": "https://rerank.example/v1",
            "model": "rerank-alice",
            "api_key": "rerank-secret",
            "top_n": 10,
            "is_active": True,
        },
        headers=alice,
    )

    assert provider.status_code == 200
    assert agent.status_code == 200
    assert reranker.status_code == 200
    assert client.get("/api/settings/provider-profiles", headers=bob).json() == []
    assert client.get("/api/agent/reranker-profiles", headers=bob).json() == []
    assert all(profile["name"] != "Alice Agent" for profile in client.get("/api/agent/profiles", headers=bob).json())
    assert client.post(f"/api/settings/provider-profiles/{provider.json()['id']}/activate", headers=bob).status_code == 404
    assert client.post(f"/api/agent/profiles/{agent.json()['id']}/activate", headers=bob).status_code == 404
    assert client.post(f"/api/agent/reranker-profiles/{reranker.json()['id']}/activate", headers=bob).status_code == 404
