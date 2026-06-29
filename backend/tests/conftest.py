from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.config import Settings, get_settings
from service.db import configure_database, init_db


@pytest.fixture(autouse=True)
def isolate_settings_from_dotenv(monkeypatch):
    """Prevent the developer's backend/.env from leaking into tests.

    Settings is configured with ``env_file=".env"`` so manual runs can pick up
    real LLM credentials. Tests assume hermetic settings driven only by explicit
    environment variables, so we disable .env loading for the duration of each
    test and clear the cached settings around it.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LUMEN_BOOTSTRAP_USER_EMAIL", "admin@example.com")
    monkeypatch.setenv("LUMEN_BOOTSTRAP_USER_PASSWORD", "admin-password")
    monkeypatch.setenv("LUMEN_AUTH_SECRET_KEY", "test-auth-secret")
    monkeypatch.setenv("LUMEN_LLM_MODE", "extractive")
    monkeypatch.setenv("LUMEN_DATA_DIR", str(tmp_path / "data"))
    for env_var in (
        "LUMEN_LLM_PROVIDER",
        "LUMEN_LLM_BASE_URL",
        "LUMEN_LLM_MODEL",
        "LUMEN_LLM_API_KEY",
        "LUMEN_LLM_TIMEOUT_SECONDS",
        "LUMEN_LLM_FALLBACK_ENABLED",
    ):
        monkeypatch.delenv(env_var, raising=False)
    get_settings.cache_clear()
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    from service.main import app

    try:
        with TestClient(app) as test_client:
            login = test_client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": "admin-password"},
            )
            assert login.status_code == 200
            test_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
            get_settings.cache_clear()
            yield test_client
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def anonymous_client(client):
    original = client.headers.pop("Authorization", None)
    try:
        yield client
    finally:
        if original is not None:
            client.headers.update({"Authorization": original})


@pytest.fixture()
def auth_headers(client):
    def _headers(email: str, password: str = "test-password") -> dict[str, str]:
        from service.auth import create_user
        from service.db import SessionLocal

        with SessionLocal() as db:
            create_user(db, email=email, password=password)
        login = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    return _headers
