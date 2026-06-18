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
        "runtime_source": "environment",
        "active_profile_id": None,
        "active_profile_name": None,
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
    assert data["runtime_source"] == "environment"
    assert data["active_profile_id"] is None
    assert data["active_profile_name"] is None


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
    assert data["runtime_source"] == "environment"
    assert data["active_profile_id"] is None
    assert data["active_profile_name"] is None
    assert "api_key" not in data


def test_provider_profile_responses_omit_raw_api_key(client):
    created = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Local OpenAI",
            "provider": "openai-compatible",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key": "secret-key",
            "timeout_seconds": 12,
            "fallback_enabled": True,
            "is_active": True,
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["api_key_configured"] is True
    assert "api_key" not in payload
    assert "secret-key" not in created.text

    listed = client.get("/api/settings/provider-profiles")
    assert listed.status_code == 200
    assert listed.json()[0]["api_key_configured"] is True
    assert "secret-key" not in listed.text


def test_provider_profile_api_key_is_encrypted_at_rest(client):
    from service.db import SessionLocal
    from service.models import LLMProviderProfile

    created = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Encrypted",
            "provider": "openai-compatible",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key": "stored-secret-key",
            "timeout_seconds": 12,
            "fallback_enabled": True,
            "is_active": True,
        },
    )

    assert created.status_code == 200
    with SessionLocal() as db:
        profile = db.get(LLMProviderProfile, created.json()["id"])
        assert profile is not None
        assert profile.api_key is not None
        assert profile.api_key.startswith("lumen:v1:")
        assert "stored-secret-key" not in profile.api_key


def test_provider_profile_update_preserves_or_clears_key(client):
    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Primary",
            "provider": "openai-compatible",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key": "secret-key",
            "timeout_seconds": 12,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    preserved = client.patch(
        f"/api/settings/provider-profiles/{profile['id']}",
        json={"name": "Renamed", "model": "gpt-renamed"},
    ).json()
    assert preserved["name"] == "Renamed"
    assert preserved["model"] == "gpt-renamed"
    assert preserved["api_key_configured"] is True

    cleared = client.patch(
        f"/api/settings/provider-profiles/{profile['id']}",
        json={"clear_api_key": True},
    ).json()
    assert cleared["api_key_configured"] is False


def test_provider_profile_activation_and_active_delete_guard(client):
    first = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "First",
            "provider": "openai-compatible",
            "base_url": "https://first.test/v1",
            "model": "gpt-first",
            "api_key": "first-key",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": True,
        },
    ).json()
    second = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Second",
            "provider": "openai-compatible",
            "base_url": "https://second.test/v1",
            "model": "gpt-second",
            "api_key": "second-key",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    activated = client.post(f"/api/settings/provider-profiles/{second['id']}/activate").json()
    profiles = client.get("/api/settings/provider-profiles").json()

    assert activated["is_active"] is True
    assert {profile["id"]: profile["is_active"] for profile in profiles} == {
        first["id"]: False,
        second["id"]: True,
    }
    assert client.delete(f"/api/settings/provider-profiles/{second['id']}").status_code == 400
    assert client.delete(f"/api/settings/provider-profiles/{first['id']}").status_code == 204


def test_runtime_settings_prefers_active_database_profile(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "env-model")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "env-key")

    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "DB Profile",
            "provider": "openai-compatible",
            "base_url": "https://db.test/v1",
            "model": "db-model",
            "api_key": "db-key",
            "timeout_seconds": 8,
            "fallback_enabled": False,
            "is_active": True,
        },
    ).json()

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    runtime = response.json()
    assert runtime["runtime_source"] == "database-profile"
    assert runtime["active_profile_id"] == profile["id"]
    assert runtime["active_profile_name"] == "DB Profile"
    assert runtime["llm_model"] == "db-model"
    assert runtime["llm_configured"] is True
    assert "db-key" not in response.text
    assert "env-key" not in response.text


def test_runtime_settings_uses_environment_without_active_profile(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "env-model")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "env-key")

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    runtime = response.json()
    assert runtime["runtime_source"] == "environment"
    assert runtime["active_profile_id"] is None
    assert runtime["active_profile_name"] is None
    assert runtime["llm_model"] == "env-model"
    assert runtime["llm_configured"] is True
    assert "env-key" not in response.text


def test_provider_profile_connection_test_marks_ready(client, monkeypatch):
    import service.api.settings as settings_api

    monkeypatch.setattr(settings_api, "_test_provider_profile", lambda profile: None)
    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Ready Profile",
            "provider": "openai-compatible",
            "base_url": "https://ready.test/v1",
            "model": "gpt-ready",
            "api_key": "ready-secret",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    response = client.post(f"/api/settings/provider-profiles/{profile['id']}/test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["last_error"] is None
    assert "ready-secret" not in response.text


def test_provider_profile_connection_test_marks_failed_without_secret(client, monkeypatch):
    import service.api.settings as settings_api

    def fail_test(profile):
        raise RuntimeError(f"provider rejected {profile.api_key}")

    monkeypatch.setattr(settings_api, "_test_provider_profile", fail_test)
    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Failed Profile",
            "provider": "openai-compatible",
            "base_url": "https://failed.test/v1",
            "model": "gpt-failed",
            "api_key": "failed-secret",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    response = client.post(f"/api/settings/provider-profiles/{profile['id']}/test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert "provider rejected" in payload["last_error"]
    assert "failed-secret" not in response.text
