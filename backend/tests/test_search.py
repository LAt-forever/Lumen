def test_search_response_includes_local_retrieval_defaults(client, monkeypatch):
    monkeypatch.setenv("LUMEN_RETRIEVAL_BACKEND", "local")
    from service.config import get_settings

    get_settings.cache_clear()
    created = client.post(
        "/api/sources",
        json={"title": "Search Defaults", "source_type": "note", "content": "Retrieval defaults should remain local."},
    )
    assert created.status_code == 200
    indexed = client.post(f"/api/sources/{created.json()['id']}/index")
    assert indexed.status_code == 200

    response = client.get("/api/search", params={"q": "retrieval defaults"})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert results[0]["retrieval_mode"] == "local"
    assert results[0]["retrieval_source"] == "local"


def test_search_with_knowledge_base_id_only_returns_requested_kb_chunks(client, monkeypatch):
    monkeypatch.setenv("LUMEN_RETRIEVAL_BACKEND", "local")
    from service.config import get_settings

    get_settings.cache_clear()
    first_kb = client.post("/api/knowledge-bases", json={"name": "Search KB A"}).json()
    second_kb = client.post("/api/knowledge-bases", json={"name": "Search KB B"}).json()
    first = client.post(
        "/api/sources",
        json={
            "title": "Scoped Search A",
            "source_type": "note",
            "content": "CometScopedSearch alpha evidence.",
            "knowledge_base_id": first_kb["id"],
        },
    ).json()
    second = client.post(
        "/api/sources",
        json={
            "title": "Scoped Search B",
            "source_type": "note",
            "content": "CometScopedSearch beta evidence.",
            "knowledge_base_id": second_kb["id"],
        },
    ).json()
    assert client.post(f"/api/sources/{first['id']}/index").status_code == 200
    assert client.post(f"/api/sources/{second['id']}/index").status_code == 200

    response = client.get("/api/search", params={"q": "CometScopedSearch", "knowledge_base_id": first_kb["id"]})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert {result["source_id"] for result in results} == {first["id"]}
    assert all(result["retrieval_mode"] == "local" for result in results)
    assert all(result["retrieval_source"] == "local" for result in results)


def test_search_api_uses_runtime_retrieval_backend(client, monkeypatch):
    calls = []

    def fake_search(self, query, limit=5, backend=None):
        calls.append({"query": query, "limit": limit, "backend": backend})
        return []

    monkeypatch.setattr("service.api.search.RetrievalService.search", fake_search)

    response = client.get("/api/search", params={"q": "runtime backend"})

    assert response.status_code == 200
    assert calls == [{"query": "runtime backend", "limit": 5, "backend": None}]
