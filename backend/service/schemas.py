from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceStatus = Literal["pending", "parsing", "indexed", "failed"]
SourceType = Literal["note", "markdown", "text", "pdf", "link", "image", "docx", "epub", "bookmark", "web_crawl"]
MemoryCandidateStatus = Literal["pending", "confirmed", "ignored", "merged"]
MemoryStatus = Literal["active", "edited", "forgotten", "merged"]
MemoryType = Literal["preference", "fact", "project", "relationship", "goal", "event", "note"]
RelationType = Literal["related_to", "part_of", "caused_by", "supports", "contradicts", "merged_into"]
RelationStatus = Literal["active", "forgotten"]
AnswerMode = Literal["extractive", "llm"]
ProviderProfileStatus = Literal["untested", "ready", "failed"]
TargetType = Literal["source", "memory", "message"]
TagAssignmentSource = Literal["user", "ai-confirmed"]
TagSuggestionStatus = Literal["pending", "confirmed", "ignored"]
GlobalSearchResultType = Literal["source_chunk", "source", "memory", "message"]
IngestionJobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]
IngestionJobType = Literal["note", "upload", "link", "crawl", "bookmark", "index", "retry"]


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_type: SourceType
    content: str | None = None
    url: str | None = None
    filename: str | None = None


class LinkCapture(BaseModel):
    url: str = Field(min_length=1, max_length=1000)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_type: str
    status: str
    url: str | None
    filename: str | None
    error_message: str | None
    created_at: datetime


class SourceDetailRead(SourceRead):
    chunk_count: int


class ChunkRead(BaseModel):
    id: int
    source_id: int
    source_title: str
    text: str
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    matched_date: str | None = None
    match_reason: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: int | None = None


class CitationRead(BaseModel):
    source_id: int
    source_title: str
    chunk_id: int
    quote: str
    matched_terms: list[str] = Field(default_factory=list)
    matched_date: str | None = None
    match_reason: str = ""


class UsedMemoryRead(BaseModel):
    id: int
    text: str
    memory_type: str


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    citations: list[CitationRead]
    memories: list[UsedMemoryRead]
    confidence: str
    answer_mode: AnswerMode = "extractive"
    fallback_reason: str | None = None


class MemoryCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    memory_type: str
    source_kind: str
    source_ref: str
    confidence: int
    status: str
    created_at: datetime


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    memory_type: str
    provenance: str
    status: str
    created_at: datetime


class MemoryUpdate(BaseModel):
    text: str = Field(min_length=1)
    memory_type: MemoryType


class MemoryMerge(BaseModel):
    target_memory_id: int


class MemoryRelationCreate(BaseModel):
    target_memory_id: int
    relation_type: RelationType
    provenance: str = "user"
    strength: int = Field(default=70, ge=0, le=100)


class MemoryRelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_memory_id: int
    target_memory_id: int
    relation_type: str
    provenance: str
    strength: int
    status: str
    created_at: datetime


class MemoryGraphNode(BaseModel):
    id: int
    text: str
    memory_type: str
    status: str


class MemoryGraphEdge(BaseModel):
    id: int
    source_memory_id: int
    target_memory_id: int
    relation_type: str
    provenance: str
    strength: int
    status: str


class MemoryGraphRead(BaseModel):
    center_memory_id: int
    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None
    created_at: datetime


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=40)


class TagAssignmentCreate(BaseModel):
    tag_id: int
    target_type: TargetType
    target_id: int


class TagAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag: TagRead
    target_type: TargetType
    target_id: int
    source: TagAssignmentSource
    created_at: datetime


class TagSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    target_type: TargetType
    target_id: int
    reason: str
    confidence: int
    status: TagSuggestionStatus
    created_at: datetime


class FavoriteCreate(BaseModel):
    target_type: TargetType
    target_id: int


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: TargetType
    target_id: int
    created_at: datetime


class GlobalSearchResultRead(BaseModel):
    result_type: GlobalSearchResultType
    target_id: int
    title: str
    snippet: str
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    matched_date: str | None = None
    match_reason: str
    tags: list[TagRead] = Field(default_factory=list)
    is_favorite: bool = False
    created_at: datetime


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: str
    source_id: int | None
    source_title: str | None = None
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    message: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class IngestionJobCountsRead(BaseModel):
    queued: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    canceled: int = 0


class IngestionBatchRead(BaseModel):
    batch_id: str
    total: int
    queued: int
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    canceled: int = 0
    jobs: list[IngestionJobRead] = Field(default_factory=list)
    sources: list[SourceRead] = Field(default_factory=list)


class SourceCountsRead(BaseModel):
    total: int
    indexed: int
    failed: int
    pending: int
    parsing: int


class FailedSourceRead(BaseModel):
    id: int
    title: str
    source_type: str
    error_message: str | None
    created_at: datetime


class StatusActionRead(BaseModel):
    label: str
    target_view: str
    target_id: int | None = None


class StatusSummaryRead(BaseModel):
    runtime: RuntimeSettingsRead
    source_counts: SourceCountsRead
    ingestion_jobs: IngestionJobCountsRead = Field(default_factory=IngestionJobCountsRead)
    failed_sources: list[FailedSourceRead] = Field(default_factory=list)
    pending_tag_suggestion_count: int
    latest_fallback_reason: str | None = None
    suggested_actions: list[StatusActionRead] = Field(default_factory=list)


class MemoryDuplicateSuggestionRead(BaseModel):
    source_memory_id: int
    target_memory_id: int
    source_text: str
    target_text: str
    overlap_score: float


class ReviewRead(BaseModel):
    sources_added: list[SourceRead]
    memories_confirmed: list[MemoryRead]
    pending_memories: list[MemoryCandidateRead]
    recent_questions: list[str]
    suggested_actions: list[str]


class RuntimeSettingsRead(BaseModel):
    llm_mode: str
    llm_provider: str
    llm_model: str | None
    llm_configured: bool
    llm_fallback_enabled: bool
    embedding_mode: str
    configuration_hint: str | None = None
    latest_fallback_reason: str | None = None
    runtime_source: str = "environment"
    active_profile_id: int | None = None
    active_profile_name: str | None = None


class LLMProviderProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(default="openai-compatible", min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0)
    fallback_enabled: bool = True
    is_active: bool = False


class LLMProviderProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: str | None = Field(default=None, min_length=1, max_length=80)
    base_url: str | None = Field(default=None, min_length=1, max_length=1000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    api_key: str | None = None
    clear_api_key: bool = False
    timeout_seconds: float | None = Field(default=None, gt=0)
    fallback_enabled: bool | None = None
    is_active: bool | None = None


class LLMProviderProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    base_url: str
    model: str
    api_key_configured: bool
    timeout_seconds: float
    fallback_enabled: bool
    is_active: bool
    status: ProviderProfileStatus
    last_error: str | None
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BulkUploadResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    sources: list[SourceRead]


class WebCrawlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1000)
    max_depth: int = Field(default=2, ge=1, le=3)
    max_pages: int = Field(default=10, ge=1, le=50)
    same_domain_only: bool = True


class BookmarkImportRequest(BaseModel):
    html_content: str = Field(min_length=1)
