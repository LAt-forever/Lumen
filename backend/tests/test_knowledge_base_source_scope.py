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
