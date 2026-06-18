from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from service.config import Settings, get_settings
from service.core.security import decrypt_secret, redact_text
from service.core.llm import ChatCompletionError, HttpxChatCompletionClient, resolve_runtime_llm_config
from service.db import get_db
from service.models import LLMProviderProfile
from service.repositories.provider_profiles import ProviderProfileRepository
from service.schemas import (
    LLMProviderProfileCreate,
    LLMProviderProfileRead,
    LLMProviderProfileUpdate,
    RuntimeSettingsRead,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/runtime", response_model=RuntimeSettingsRead)
def runtime_settings(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> RuntimeSettingsRead:
    runtime_config = resolve_runtime_llm_config(settings, ProviderProfileRepository(db).active())
    llm_configured = bool(runtime_config.api_key and runtime_config.model)
    configuration_hint = None
    if runtime_config.mode == "llm" and not llm_configured:
        configuration_hint = "LLM 模式已开启，但模型名称或 API key 未配置。"
    return RuntimeSettingsRead(
        llm_mode=runtime_config.mode,
        llm_provider=runtime_config.provider,
        llm_model=runtime_config.model,
        llm_configured=llm_configured,
        llm_fallback_enabled=runtime_config.fallback_enabled,
        embedding_mode=settings.embedding_mode,
        configuration_hint=configuration_hint,
        latest_fallback_reason=None,
        runtime_source=runtime_config.runtime_source,
        active_profile_id=runtime_config.active_profile_id,
        active_profile_name=runtime_config.active_profile_name,
    )


@router.get("/provider-profiles", response_model=list[LLMProviderProfileRead])
def list_provider_profiles(db: Session = Depends(get_db)) -> list[LLMProviderProfileRead]:
    profiles = ProviderProfileRepository(db).list()
    return [_read_profile(profile) for profile in profiles]


@router.post("/provider-profiles", response_model=LLMProviderProfileRead)
def create_provider_profile(
    data: LLMProviderProfileCreate,
    db: Session = Depends(get_db),
) -> LLMProviderProfileRead:
    profile = ProviderProfileRepository(db).create(data)
    return _read_profile(profile)


@router.patch("/provider-profiles/{profile_id}", response_model=LLMProviderProfileRead)
def update_provider_profile(
    profile_id: int,
    data: LLMProviderProfileUpdate,
    db: Session = Depends(get_db),
) -> LLMProviderProfileRead:
    repo = ProviderProfileRepository(db)
    try:
        profile = repo.update(profile_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _read_profile(profile)


@router.post("/provider-profiles/{profile_id}/activate", response_model=LLMProviderProfileRead)
def activate_provider_profile(
    profile_id: int,
    db: Session = Depends(get_db),
) -> LLMProviderProfileRead:
    repo = ProviderProfileRepository(db)
    try:
        profile = repo.activate(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _read_profile(profile)


@router.post("/provider-profiles/{profile_id}/test", response_model=LLMProviderProfileRead)
def test_provider_profile(
    profile_id: int,
    db: Session = Depends(get_db),
) -> LLMProviderProfileRead:
    repo = ProviderProfileRepository(db)
    profile = repo.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"provider profile {profile_id} not found")
    try:
        _test_provider_profile(profile)
    except Exception as exc:
        profile = repo.mark_test_result(profile_id, "failed", _sanitize_provider_error(exc, profile))
    else:
        profile = repo.mark_test_result(profile_id, "ready", None)
    return _read_profile(profile)


@router.delete("/provider-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_profile(
    profile_id: int,
    db: Session = Depends(get_db),
) -> Response:
    repo = ProviderProfileRepository(db)
    profile = repo.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"provider profile {profile_id} not found")
    if profile.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="active provider profile cannot be deleted")
    repo.delete(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _read_profile(profile: LLMProviderProfile) -> LLMProviderProfileRead:
    return LLMProviderProfileRead(
        id=profile.id,
        name=profile.name,
        provider=profile.provider,
        base_url=profile.base_url,
        model=profile.model,
        api_key_configured=bool(profile.api_key),
        timeout_seconds=profile.timeout_seconds,
        fallback_enabled=profile.fallback_enabled,
        is_active=profile.is_active,
        status=profile.status,
        last_error=profile.last_error,
        last_checked_at=profile.last_checked_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _test_provider_profile(profile: LLMProviderProfile) -> None:
    if profile.provider != "openai-compatible":
        raise ChatCompletionError(f"unsupported provider: {profile.provider}")
    api_key = decrypt_secret(profile.api_key)
    if not api_key:
        raise ChatCompletionError("API key 未配置。")
    client = HttpxChatCompletionClient(
        base_url=profile.base_url,
        model=profile.model,
        api_key=api_key,
        timeout_seconds=profile.timeout_seconds,
    )
    client.complete([{"role": "user", "content": "请只回复 OK。"}])


def _sanitize_provider_error(exc: Exception, profile: LLMProviderProfile) -> str:
    message = str(exc) or exc.__class__.__name__
    return redact_text(message, [profile.api_key, decrypt_secret(profile.api_key)])[:500]
