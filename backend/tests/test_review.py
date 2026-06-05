def test_core_api_loop(client):
    created = client.post(
        "/api/sources",
        json={
            "title": "Source A",
            "source_type": "note",
            "content": "Lumen gives answers with citations.",
        },
    )
    assert created.status_code == 200
    source_id = created.json()["id"]

    indexed = client.post(f"/api/sources/{source_id}/index")
    assert indexed.status_code == 200
    assert indexed.json()["status"] == "indexed"

    answer = client.post("/api/chat", json={"message": "What does Lumen give?"})
    assert answer.status_code == 200
    assert len(answer.json()["citations"]) >= 1

    review = client.get("/api/review")
    assert review.status_code == 200
    assert len(review.json()["sources_added"]) >= 1
