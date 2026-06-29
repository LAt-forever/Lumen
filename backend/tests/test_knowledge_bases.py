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
    from sqlalchemy import select

    from service.db import SessionLocal
    from service.models import User

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert user is not None
        repo = KnowledgeBaseRepository(db, user_id=user.id)
        default = repo.default()
        assert isinstance(default, KnowledgeBase)
        assert default.name == "默认知识库"
        assert default.is_default is True


def test_create_rename_archive_restore_and_delete_empty_knowledge_base(client):
    created = client.post(
        "/api/knowledge-bases",
        json={"name": "项目资料", "description": "Phase 2"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "active"
    assert body["is_default"] is False
    kb_id = body["id"]

    renamed = client.patch(
        f"/api/knowledge-bases/{kb_id}",
        json={"name": "项目资料归档", "description": "renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "项目资料归档"

    archived = client.post(f"/api/knowledge-bases/{kb_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    restored = client.post(f"/api/knowledge-bases/{kb_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    activated = client.post(f"/api/knowledge-bases/{kb_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["id"] == kb_id

    deleted = client.delete(f"/api/knowledge-bases/{kb_id}")
    assert deleted.status_code == 204


def test_default_knowledge_base_cannot_be_archived_or_deleted(client):
    default = client.get("/api/knowledge-bases").json()[0]

    archived = client.post(f"/api/knowledge-bases/{default['id']}/archive")
    assert archived.status_code == 400

    deleted = client.delete(f"/api/knowledge-bases/{default['id']}")
    assert deleted.status_code == 400


def test_archived_knowledge_base_cannot_be_activated(client):
    kb = client.post("/api/knowledge-bases", json={"name": "待归档知识库"}).json()
    archived = client.post(f"/api/knowledge-bases/{kb['id']}/archive")
    assert archived.status_code == 200

    activated = client.post(f"/api/knowledge-bases/{kb['id']}/activate")
    assert activated.status_code == 400


def test_cannot_delete_non_empty_knowledge_base(client):
    kb = client.post("/api/knowledge-bases", json={"name": "非空知识库"}).json()
    source = client.post(
        "/api/sources",
        json={
            "title": "非空资料",
            "source_type": "note",
            "content": "不能删除非空知识库",
            "knowledge_base_id": kb["id"],
        },
    )
    assert source.status_code == 200

    deleted = client.delete(f"/api/knowledge-bases/{kb['id']}")
    assert deleted.status_code == 400
