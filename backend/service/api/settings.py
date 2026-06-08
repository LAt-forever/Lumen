from fastapi import APIRouter, Depends

from service.config import Settings, get_settings
from service.schemas import RuntimeSettingsRead

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/runtime", response_model=RuntimeSettingsRead)
def runtime_settings(settings: Settings = Depends(get_settings)) -> RuntimeSettingsRead:
    llm_configured = bool(settings.llm_api_key and settings.llm_model)
    return RuntimeSettingsRead(
        llm_mode=settings.llm_mode,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_configured=llm_configured,
        llm_fallback_enabled=settings.llm_fallback_enabled,
        embedding_mode=settings.embedding_mode,
    )
