from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceStatus = Literal["pending", "parsing", "indexed", "failed"]
SourceType = Literal["note", "markdown", "text", "pdf", "link"]
MemoryCandidateStatus = Literal["pending", "confirmed", "ignored", "merged"]
MemoryStatus = Literal["active", "edited", "forgotten", "merged"]
MemoryType = Literal["preference", "fact", "project", "relationship", "goal", "event", "note"]
AnswerMode = Literal["extractive", "llm"]
ProviderProfileStatus = Literal["untested", "ready", "failed"]


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
