def test_login_returns_access_token_and_current_user(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "admin@example.com"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})

    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


def test_login_rejects_bad_password(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )

    assert response.status_code == 401


def test_register_is_disabled_by_default(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "new-password"},
    )

    assert response.status_code == 403


def test_register_rejects_existing_email_when_enabled(client, monkeypatch):
    from service.config import get_settings

    monkeypatch.setenv("LUMEN_REGISTRATION_ENABLED", "true")
    get_settings.cache_clear()

    response = client.post(
        "/api/auth/register",
        json={"email": "admin@example.com", "password": "attacker-password"},
    )

    assert response.status_code == 409
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "attacker-password"},
    )
    assert bad_login.status_code == 401


def test_business_api_requires_access_token(anonymous_client):
    response = anonymous_client.get("/api/sources")

    assert response.status_code == 401
