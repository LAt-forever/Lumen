from service.models import KnowledgeBase
from service.repositories.knowledge_bases import KnowledgeBaseRepository


def test_default_knowledge_base_exists_for_bootstrap_user(client):
    response = client.get("/api/knowledge-bases")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "默认知识库"
    assert rows[0]["is_default"] is True
    assert rows[0]["status"] == "active"


def test_user_cannot_see_other_users_knowledge_bases(client, auth_headers):
    other_headers = auth_headers("phase2-other@example.com")
    created = client.post(
        "/api/knowledge-bases",
        json={"name": "另一个用户的知识库", "description": "private"},
        headers=other_headers,
    )
    assert created.status_code == 200

    mine = client.get("/api/knowledge-bases")
    assert mine.status_code == 200
    assert all(row["name"] != "另一个用户的知识库" for row in mine.json())


def test_default_knowledge_base_is_created_by_repository(client):
    from service.db import SessionLocal
    from service.auth import get_user_by_email

    with SessionLocal() as db:
        user = get_user_by_email(db, "admin@example.com")
        assert user is not None
        repo = KnowledgeBaseRepository(db, user_id=user.id)
        default = repo.default()
        assert isinstance(default, KnowledgeBase)
        assert default.name == "默认知识库"
        assert default.is_default is True
