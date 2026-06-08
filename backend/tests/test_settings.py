from service.config import get_settings


def test_runtime_settings_omits_api_key(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "secret-value")
    monkeypatch.setenv("LUMEN_LLM_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()

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
    }
    assert "secret-value" not in response.text


def test_runtime_settings_defaults_to_extractive(client, monkeypatch):
    monkeypatch.delenv("LUMEN_LLM_MODE", raising=False)
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)
    get_settings.cache_clear()

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data["llm_mode"] == "extractive"
    assert data["llm_provider"] == "openai-compatible"
    assert data["llm_model"] is None
    assert data["llm_configured"] is False
    assert data["llm_fallback_enabled"] is True
