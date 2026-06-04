from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lumen"
    database_url: str = "sqlite:///./lumen.db"
    data_dir: Path = Path("./data")
    llm_mode: str = "extractive"
    embedding_mode: str = "hash"

    model_config = SettingsConfigDict(env_prefix="LUMEN_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
