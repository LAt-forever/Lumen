from service.config import Settings
from service.core.llm import resolve_runtime_llm_config
from service.core.tagging import TagSuggestionService
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.provider_profiles import ProviderProfileRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    FailedSourceRead,
    RuntimeSettingsRead,
    SourceCountsRead,
    StatusActionRead,
    StatusSummaryRead,
)


class StatusService:
    def __init__(
        self,
        settings: Settings,
        sources: SourceRepository,
        memories: MemoryRepository,
        conversations: ConversationRepository,
        organization: OrganizationRepository,
        provider_profiles: ProviderProfileRepository,
    ):
        self.settings = settings
        self.sources = sources
        self.memories = memories
        self.conversations = conversations
        self.organization = organization
        self.provider_profiles = provider_profiles

    def summary(self) -> StatusSummaryRead:
        TagSuggestionService(self.sources, self.memories, self.conversations, self.organization).ensure_suggestions_for_existing()
        runtime = self._runtime()
        counts = SourceCountsRead(**self.sources.status_counts())
        failed_sources = [
            FailedSourceRead(
                id=source.id,
                title=source.title,
                source_type=source.source_type,
                error_message=source.error_message,
                created_at=source.created_at,
            )
            for source in self.sources.failed_sources()
        ]
        pending_count = self.organization.pending_suggestion_count()
        return StatusSummaryRead(
            runtime=runtime,
            source_counts=counts,
            failed_sources=failed_sources,
            pending_tag_suggestion_count=pending_count,
            latest_fallback_reason=runtime.latest_fallback_reason,
            suggested_actions=self._actions(runtime, counts, failed_sources, pending_count),
        )

    def _runtime(self) -> RuntimeSettingsRead:
        runtime_config = resolve_runtime_llm_config(self.settings, self.provider_profiles.active())
        llm_configured = bool(runtime_config.api_key and runtime_config.model)
        configuration_hint = None
        if runtime_config.mode == "llm" and not llm_configured:
            configuration_hint = "LLM 模式已开启，但模型名称或 API key 未配置。"
        runtime_source = runtime_config.runtime_source
        if runtime_config.mode == "extractive" and runtime_source == "environment":
            runtime_source = "extractive"
        return RuntimeSettingsRead(
            llm_mode=runtime_config.mode,
            llm_provider=runtime_config.provider,
            llm_model=runtime_config.model,
            llm_configured=llm_configured,
            llm_fallback_enabled=runtime_config.fallback_enabled,
            embedding_mode=self.settings.embedding_mode,
            configuration_hint=configuration_hint,
            latest_fallback_reason=None,
            runtime_source=runtime_source,
            active_profile_id=runtime_config.active_profile_id,
            active_profile_name=runtime_config.active_profile_name,
        )

    def _actions(
        self,
        runtime: RuntimeSettingsRead,
        counts: SourceCountsRead,
        failed_sources: list[FailedSourceRead],
        pending_count: int,
    ) -> list[StatusActionRead]:
        actions: list[StatusActionRead] = []
        if runtime.configuration_hint:
            actions.append(StatusActionRead(label="检查模型设置", target_view="settings"))
        if failed_sources:
            actions.append(StatusActionRead(label=f"重试 {counts.failed} 个失败资料", target_view="library"))
        if pending_count:
            actions.append(StatusActionRead(label=f"确认 {pending_count} 个标签建议", target_view="status"))
        return actions
