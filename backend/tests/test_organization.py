def _create_source(client, title: str = "组织资料") -> dict:
    return client.post(
        "/api/sources",
        json={"title": title, "source_type": "note", "content": f"{title} 用来测试标签和收藏。"},
    ).json()


def _create_memory(client) -> dict:
    chat_response = client.post("/api/chat", json={"message": "我正在做 Lumen 这个个人知识库项目。"})
    assert chat_response.status_code == 200
    candidates = client.get("/api/memories/candidates").json()
    assert candidates
    confirm_response = client.post(
        f"/api/memories/candidates/{candidates[0]['id']}/confirm",
        json={"text": candidates[0]["text"], "memory_type": candidates[0]["memory_type"]},
    )
    assert confirm_response.status_code == 200
    return confirm_response.json()


def _create_message(client) -> dict:
    response = client.post("/api/chat", json={"message": "请记录这个可以收藏的回答。"})
    assert response.status_code == 200
    return response.json()


def test_tag_creation_normalizes_duplicate_names(client):
    first = client.post("/api/tags", json={"name": " Lumen ", "color": "#2563eb"})
    second = client.post("/api/tags", json={"name": "lumen", "color": "#16a34a"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["name"] == "Lumen"

    tags = client.get("/api/tags").json()
    assert len(tags) == 1
    assert tags[0]["color"] == "#2563eb"


def test_tag_assignment_supports_source_memory_and_message_targets(client):
    source = _create_source(client)
    memory = _create_memory(client)
    message = _create_message(client)
    tag = client.post("/api/tags", json={"name": "项目", "color": "#0f766e"}).json()

    targets = [
        ("source", source["id"]),
        ("memory", memory["id"]),
        ("message", message["message_id"]),
    ]
    for target_type, target_id in targets:
        response = client.post(
            "/api/tags/assignments",
            json={"tag_id": tag["id"], "target_type": target_type, "target_id": target_id},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["target_type"] == target_type
        assert payload["target_id"] == target_id
        assert payload["tag"]["name"] == "项目"
        assert payload["source"] == "user"

    duplicate = client.post(
        "/api/tags/assignments",
        json={"tag_id": tag["id"], "target_type": "source", "target_id": source["id"]},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["target_type"] == "source"


def test_favorite_create_and_delete_are_idempotent(client):
    source = _create_source(client, title="收藏资料")
    payload = {"target_type": "source", "target_id": source["id"]}

    first = client.post("/api/favorites", json=payload)
    second = client.post("/api/favorites", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert client.get("/api/favorites").json()[0]["target_id"] == source["id"]

    first_delete = client.delete(f"/api/favorites/source/{source['id']}")
    second_delete = client.delete(f"/api/favorites/source/{source['id']}")

    assert first_delete.status_code == 204
    assert second_delete.status_code == 204
    assert client.get("/api/favorites").json() == []
