from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.config import get_settings
from service.db import configure_database, init_db


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "extractive")
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
