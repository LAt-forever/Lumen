from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from service.core.security import encrypt_secret
from service.models import AgentProfile, AgentToolLog, RerankerProfile
from service.schemas import AgentProfileCreate, AgentProfileUpdate, RerankerProfileCreate, RerankerProfileUpdate

DEFAULT_AGENT_TOOLS = ["global_search", "memory_search"]


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_profiles(self) -> list[AgentProfile]:
        stmt = select(AgentProfile).order_by(AgentProfile.is_active.desc(), AgentProfile.updated_at.desc(), AgentProfile.id.desc())
        return list(self.db.scalars(stmt))

    def active_or_default(self) -> AgentProfile:
        profile = self.active_profile()
        if profile is not None:
            return profile
        return self.create_profile(
            AgentProfileCreate(
                name="默认 Agent",
                instructions="只使用已授权的只读工具；证据不足时说明不知道。",
                enabled_tools=DEFAULT_AGENT_TOOLS,
                require_approval=True,
                is_active=True,
            )
        )

    def active_profile(self) -> AgentProfile | None:
        stmt = select(AgentProfile).where(AgentProfile.is_active.is_(True)).order_by(AgentProfile.updated_at.desc(), AgentProfile.id.desc())
        return self.db.scalars(stmt).first()

    def get_profile(self, profile_id: int) -> AgentProfile | None:
        return self.db.get(AgentProfile, profile_id)

    def create_profile(self, data: AgentProfileCreate) -> AgentProfile:
        profile = AgentProfile(
            name=data.name,
            instructions=data.instructions,
            enabled_tools_json=json.dumps(data.enabled_tools, ensure_ascii=False),
            require_approval=data.require_approval,
            is_active=data.is_active,
        )
        if profile.is_active:
            self._deactivate_agent_profiles()
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update_profile(self, profile_id: int, data: AgentProfileUpdate) -> AgentProfile:
        profile = self._required_profile(profile_id)
        payload = data.model_dump(exclude_unset=True)
        if "enabled_tools" in payload:
            profile.enabled_tools_json = json.dumps(payload.pop("enabled_tools") or [], ensure_ascii=False)
        if payload.get("is_active") is True:
            self._deactivate_agent_profiles(except_id=profile.id)
        for field, value in payload.items():
            setattr(profile, field, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def activate_profile(self, profile_id: int) -> AgentProfile:
        profile = self._required_profile(profile_id)
        self._deactivate_agent_profiles(except_id=profile.id)
        profile.is_active = True
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def enabled_tools(self, profile: AgentProfile) -> list[str]:
        try:
            tools = json.loads(profile.enabled_tools_json or "[]")
        except json.JSONDecodeError:
            return []
        return [tool for tool in tools if isinstance(tool, str)]

    def create_tool_log(
        self,
        profile_id: int | None,
        tool_name: str,
        action: str,
        input_json: str,
        result_summary: str | None = None,
        status: str = "succeeded",
        error_message: str | None = None,
    ) -> AgentToolLog:
        log = AgentToolLog(
            profile_id=profile_id,
            tool_name=tool_name,
            action=action,
            input_json=input_json,
            result_summary=result_summary,
            status=status,
            error_message=error_message,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_tool_logs(self, limit: int = 50) -> list[AgentToolLog]:
        stmt = select(AgentToolLog).order_by(AgentToolLog.created_at.desc(), AgentToolLog.id.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def list_reranker_profiles(self) -> list[RerankerProfile]:
        stmt = select(RerankerProfile).order_by(RerankerProfile.is_active.desc(), RerankerProfile.updated_at.desc(), RerankerProfile.id.desc())
        return list(self.db.scalars(stmt))

    def create_reranker_profile(self, data: RerankerProfileCreate) -> RerankerProfile:
        profile = RerankerProfile(
            name=data.name,
            provider=data.provider,
            base_url=data.base_url,
            model=data.model,
            api_key=encrypt_secret(data.api_key),
            top_n=data.top_n,
            is_active=data.is_active,
        )
        if profile.is_active:
            self._deactivate_reranker_profiles()
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update_reranker_profile(self, profile_id: int, data: RerankerProfileUpdate) -> RerankerProfile:
        profile = self._required_reranker_profile(profile_id)
        payload = data.model_dump(exclude_unset=True)
        clear_api_key = bool(payload.pop("clear_api_key", False))
        if clear_api_key:
            profile.api_key = None
            payload.pop("api_key", None)
        elif "api_key" in payload:
            profile.api_key = encrypt_secret(payload.pop("api_key"))
        if payload.get("is_active") is True:
            self._deactivate_reranker_profiles(except_id=profile.id)
        for field, value in payload.items():
            setattr(profile, field, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def activate_reranker_profile(self, profile_id: int) -> RerankerProfile:
        profile = self._required_reranker_profile(profile_id)
        self._deactivate_reranker_profiles(except_id=profile.id)
        profile.is_active = True
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def _deactivate_agent_profiles(self, except_id: int | None = None) -> None:
        for profile in self.db.scalars(select(AgentProfile).where(AgentProfile.is_active.is_(True))):
            if except_id is not None and profile.id == except_id:
                continue
            profile.is_active = False

    def _deactivate_reranker_profiles(self, except_id: int | None = None) -> None:
        for profile in self.db.scalars(select(RerankerProfile).where(RerankerProfile.is_active.is_(True))):
            if except_id is not None and profile.id == except_id:
                continue
            profile.is_active = False

    def _required_profile(self, profile_id: int) -> AgentProfile:
        profile = self.db.get(AgentProfile, profile_id)
        if profile is None:
            raise ValueError(f"agent profile {profile_id} not found")
        return profile

    def _required_reranker_profile(self, profile_id: int) -> RerankerProfile:
        profile = self.db.get(RerankerProfile, profile_id)
        if profile is None:
            raise ValueError(f"reranker profile {profile_id} not found")
        return profile
