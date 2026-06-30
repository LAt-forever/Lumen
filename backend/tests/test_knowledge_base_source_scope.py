def test_sources_are_assigned_to_default_knowledge_base(client):
    source = client.post(
        "/api/sources",
        json={"title": "Phase 2 note", "source_type": "note", "content": "知识库归属测试"},
    )
    assert source.status_code == 200
    body = source.json()
    assert body["knowledge_base_id"] is not None
    assert body["knowledge_base_name"] == "默认知识库"

    listed = client.get("/api/sources")
    assert listed.status_code == 200
    assert listed.json()[0]["knowledge_base_id"] == body["knowledge_base_id"]


def test_source_list_filters_by_knowledge_base_id(client):
    first_kb = client.post("/api/knowledge-bases", json={"name": "Project Alpha"}).json()
    second_kb = client.post("/api/knowledge-bases", json={"name": "Project Beta"}).json()

    first_source = client.post(
        "/api/sources",
        json={
            "title": "Alpha note",
            "source_type": "note",
            "content": "Alpha content",
            "knowledge_base_id": first_kb["id"],
        },
    ).json()
    client.post(
        "/api/sources",
        json={
            "title": "Beta note",
            "source_type": "note",
            "content": "Beta content",
            "knowledge_base_id": second_kb["id"],
        },
    )

    listed = client.get(f"/api/sources?knowledge_base_id={first_kb['id']}")

    assert listed.status_code == 200
    assert [source["id"] for source in listed.json()] == [first_source["id"]]
    assert listed.json()[0]["knowledge_base_name"] == "Project Alpha"


def test_rejects_creating_source_in_another_users_knowledge_base(client, auth_headers):
    other_headers = auth_headers("other@example.com")
    other_kb = client.post(
        "/api/knowledge-bases",
        json={"name": "Other user's KB"},
        headers=other_headers,
    ).json()

    response = client.post(
        "/api/sources",
        json={
            "title": "Intrusion",
            "source_type": "note",
            "content": "Should not be accepted",
            "knowledge_base_id": other_kb["id"],
        },
    )

    assert response.status_code == 404


def test_rejects_creating_source_in_archived_knowledge_base(client):
    kb = client.post("/api/knowledge-bases", json={"name": "Archive target"}).json()
    archived = client.post(f"/api/knowledge-bases/{kb['id']}/archive")
    assert archived.status_code == 200

    response = client.post(
        "/api/sources",
        json={
            "title": "Archived note",
            "source_type": "note",
            "content": "Should not be accepted",
            "knowledge_base_id": kb["id"],
        },
    )

    assert response.status_code == 400
