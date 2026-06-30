from __future__ import annotations

from sqlalchemy.orm import Session

from service.config import Settings, get_settings
from service.core.embeddings import HashEmbeddingProvider, build_embedding_provider
from service.repositories.provider_profiles import ProviderProfileRepository


def build_local_embedding_provider(settings: Settings | None = None):
    runtime_settings = settings or get_settings()
    return HashEmbeddingProvider(dimensions=runtime_settings.embedding_dimensions)


def build_user_embedding_provider(db: Session, user_id: int | None, settings: Settings | None = None):
    runtime_settings = settings or get_settings()
    if user_id is None:
        return build_embedding_provider(runtime_settings, None)
    active_profile = ProviderProfileRepository(db, user_id=user_id).active()
    return build_embedding_provider(runtime_settings, active_profile)
