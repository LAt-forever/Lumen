def _source(client, title: str, content: str) -> dict:
    created = client.post("/api/sources", json={"title": title, "source_type": "note", "content": content}).json()
    indexed = client.post(f"/api/sources/{created['id']}/index")
    assert indexed.status_code == 200
    return created


def _memory(client, message: str) -> dict:
    response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 200
    candidates = client.get("/api/memories/candidates").json()
    assert candidates
    confirmed = client.post(
        f"/api/memories/candidates/{candidates[0]['id']}/confirm",
        json={"text": candidates[0]["text"], "memory_type": candidates[0]["memory_type"]},
    )
    assert confirmed.status_code == 200
    return confirmed.json()


def _message(client, message: str) -> dict:
    response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 200
    return response.json()


def _tag(client, name: str) -> dict:
    response = client.post("/api/tags", json={"name": name, "color": "#2563eb"})
    assert response.status_code == 200
    return response.json()


def test_global_search_returns_sources_memories_and_messages(client):
    _source(client, "Phase15 全局搜索资料", "Phase15 资料片段记录统一搜索和质量信号。")
    _memory(client, "我的偏好是 Phase15 搜索结果需要清楚展示匹配原因。")
    message = _message(client, "请记住 Phase15 对话回答也应该能被找回。")

    response = client.get("/api/global-search", params={"q": "Phase15 搜索"})

    assert response.status_code == 200
    results = response.json()
    result_types = {result["result_type"] for result in results}
    assert {"source_chunk", "source", "memory", "message"}.issubset(result_types)
    assert any(result["target_id"] == message["message_id"] and result["result_type"] == "message" for result in results)
    assert all(result["match_reason"] for result in results)
    assert all("is_favorite" in result for result in results)
    assert all("tags" in result for result in results)


def test_global_search_filters_by_result_type(client):
    _source(client, "类型筛选资料", "TypeFilter 资料用于全局搜索类型筛选。")
    _memory(client, "我的偏好是 TypeFilter 记忆只在 memory 筛选中出现。")
    _message(client, "TypeFilter 对话消息用于 message 筛选。")

    response = client.get("/api/global-search", params={"q": "TypeFilter", "types": "memory"})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert {result["result_type"] for result in results} == {"memory"}


def test_global_search_filters_by_tag_and_favorite(client):
    source = _source(client, "TaggedFavorite 资料", "TaggedFavorite 资料用于标签和收藏过滤。")
    _source(client, "UntaggedFavorite 资料", "UntaggedFavorite 不应该出现在标签过滤结果里。")
    tag = _tag(client, "重点")
    client.post("/api/tags/assignments", json={"tag_id": tag["id"], "target_type": "source", "target_id": source["id"]})
    client.post("/api/favorites", json={"target_type": "source", "target_id": source["id"]})

    response = client.get("/api/global-search", params={"q": "Favorite", "tag": "重点", "favorite": "true"})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert {result["target_id"] for result in results if result["result_type"] == "source"} == {source["id"]}
    assert all(result["is_favorite"] for result in results)
    assert all(any(tag_item["name"] == "重点" for tag_item in result["tags"]) for result in results)


def test_retrieval_evaluation_date_project_preference_and_answer_cases(client):
    worklog = _source(
        client,
        "Phase15 工作日报",
        "时间 | 2026年6月9日 记录 | Phase15 完成全局搜索、标签收藏和状态面板设计。",
    )
    project_memory = _memory(client, "我正在做 Phase15 组织和全局搜索项目。")
    preference_memory = _memory(client, "我喜欢 Phase15 搜索结果显示中文匹配原因。")
    answer = _message(client, "Phase15 收藏回答应该能在以后搜索回来。")
    tag = _tag(client, "Phase15")
    client.post("/api/tags/assignments", json={"tag_id": tag["id"], "target_type": "source", "target_id": worklog["id"]})
    client.post("/api/favorites", json={"target_type": "message", "target_id": answer["message_id"]})

    cases = [
        ("2026年6月9日 Phase15 做了什么", "source_chunk", "匹配日期"),
        ("Phase15 组织和全局搜索项目", "memory", str(project_memory["id"])),
        ("Phase15 搜索结果显示中文匹配原因", "memory", str(preference_memory["id"])),
        ("Phase15 收藏回答", "message", str(answer["message_id"])),
    ]
    for query, result_type, expected_marker in cases:
        response = client.get("/api/global-search", params={"q": query})
        assert response.status_code == 200
        top_results = response.json()[:3]
        assert any(result["result_type"] == result_type for result in top_results)
        serialized = str(top_results)
        assert expected_marker in serialized

    tagged = client.get("/api/global-search", params={"q": "Phase15", "tag": "Phase15"}).json()
    assert any(result["target_id"] == worklog["id"] for result in tagged)

    favorited = client.get("/api/global-search", params={"q": "Phase15 收藏回答", "favorite": "true"}).json()
    assert favorited
    assert all(result["is_favorite"] for result in favorited)
