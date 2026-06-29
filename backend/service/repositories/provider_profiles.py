from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from service.core.security import encrypt_secret
from service.models import LLMProviderProfile
from service.schemas import LLMProviderProfileCreate, LLMProviderProfileUpdate


class ProviderProfileRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _scoped(self, stmt):
        if self.user_id is not None:
            return stmt.where(LLMProviderProfile.user_id == self.user_id)
        return stmt

    def create(self, data: LLMProviderProfileCreate) -> LLMProviderProfile:
        payload = data.model_dump()
        payload["api_key"] = self._normalize_key(payload.get("api_key"))
        payload["user_id"] = self.user_id
        profile = LLMProviderProfile(**payload)
        if profile.is_active:
            self._deactivate_others()
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def list(self) -> list[LLMProviderProfile]:
        stmt = self._scoped(select(LLMProviderProfile)).order_by(
            LLMProviderProfile.is_active.desc(),
            LLMProviderProfile.updated_at.desc(),
            LLMProviderProfile.id.desc(),
        )
        return list(self.db.scalars(stmt))

    def get(self, profile_id: int) -> LLMProviderProfile | None:
        if self.user_id is None:
            return self.db.get(LLMProviderProfile, profile_id)
        return self.db.scalar(select(LLMProviderProfile).where(LLMProviderProfile.id == profile_id, LLMProviderProfile.user_id == self.user_id))

    def active(self) -> LLMProviderProfile | None:
        stmt = (
            select(LLMProviderProfile)
            .where(LLMProviderProfile.is_active.is_(True))
            .order_by(LLMProviderProfile.updated_at.desc(), LLMProviderProfile.id.desc())
        )
        stmt = self._scoped(stmt)
        return self.db.scalars(stmt).first()

    def update(self, profile_id: int, data: LLMProviderProfileUpdate) -> LLMProviderProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise ValueError(f"provider profile {profile_id} not found")

        payload = data.model_dump(exclude_unset=True)
        clear_api_key = bool(payload.pop("clear_api_key", False))
        if clear_api_key:
            profile.api_key = None
            payload.pop("api_key", None)
        elif "api_key" in payload:
            profile.api_key = self._normalize_key(payload.pop("api_key"))

        activate = payload.get("is_active") is True
        if activate:
            self._deactivate_others(except_id=profile.id)

        for field, value in payload.items():
            setattr(profile, field, value)

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def activate(self, profile_id: int) -> LLMProviderProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise ValueError(f"provider profile {profile_id} not found")
        self._deactivate_others(except_id=profile.id)
        profile.is_active = True
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete(self, profile_id: int) -> None:
        profile = self.get(profile_id)
        if profile is None:
            raise ValueError(f"provider profile {profile_id} not found")
        if profile.is_active:
            raise ValueError("active provider profile cannot be deleted")
        self.db.delete(profile)
        self.db.commit()

    def mark_test_result(self, profile_id: int, status: str, last_error: str | None) -> LLMProviderProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise ValueError(f"provider profile {profile_id} not found")
        profile.status = status
        profile.last_error = last_error
        profile.last_checked_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def _deactivate_others(self, except_id: int | None = None) -> None:
        stmt = select(LLMProviderProfile).where(LLMProviderProfile.is_active.is_(True))
        stmt = self._scoped(stmt)
        for profile in self.db.scalars(stmt):
            if except_id is not None and profile.id == except_id:
                continue
            profile.is_active = False

    def _normalize_key(self, api_key: str | None) -> str | None:
        if api_key is None:
            return None
        stripped = api_key.strip()
        return encrypt_secret(stripped) if stripped else None
