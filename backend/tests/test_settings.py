import pytest

from service.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_runtime_settings_omits_api_key(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "secret-value")
    monkeypatch.setenv("LUMEN_LLM_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("LUMEN_EMBEDDING_MODE", "hash")

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "llm_mode": "llm",
        "llm_provider": "openai-compatible",
        "llm_model": "gpt-test",
        "llm_configured": True,
        "llm_fallback_enabled": True,
        "embedding_mode": "hash",
        "configuration_hint": None,
        "latest_fallback_reason": None,
    }
    assert "secret-value" not in response.text


def test_runtime_settings_defaults_to_extractive(client, monkeypatch):
    monkeypatch.delenv("LUMEN_LLM_MODE", raising=False)
    monkeypatch.delenv("LUMEN_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("LUMEN_LLM_FALLBACK_ENABLED", raising=False)
    monkeypatch.delenv("LUMEN_EMBEDDING_MODE", raising=False)

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data["llm_mode"] == "extractive"
    assert data["llm_provider"] == "openai-compatible"
    assert data["llm_model"] is None
    assert data["llm_configured"] is False
    assert data["llm_fallback_enabled"] is True
    assert data["embedding_mode"] == "hash"
    assert data["configuration_hint"] is None
    assert data["latest_fallback_reason"] is None


def test_runtime_settings_reports_missing_llm_configuration_hint(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data["llm_configured"] is False
    assert data["configuration_hint"] == "LLM 模式已开启，但模型名称或 API key 未配置。"
    assert data["latest_fallback_reason"] is None
    assert "api_key" not in data
