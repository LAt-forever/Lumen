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
            yield test_client
    finally:
        get_settings.cache_clear()
