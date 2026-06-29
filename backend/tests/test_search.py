def test_search_response_includes_local_retrieval_defaults(client):
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
