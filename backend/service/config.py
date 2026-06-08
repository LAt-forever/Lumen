from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lumen"
    database_url: str = "sqlite:///./lumen.db"
    data_dir: Path = Path("./data")
    llm_mode: str = "extractive"
    llm_provider: str = "openai-compatible"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_fallback_enabled: bool = True
    embedding_mode: str = "hash"

    model_config = SettingsConfigDict(env_prefix="LUMEN_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
