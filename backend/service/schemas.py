from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceStatus = Literal["pending", "parsing", "indexed", "failed"]
SourceType = Literal["note", "markdown", "text", "pdf", "link"]
MemoryCandidateStatus = Literal["pending", "confirmed", "ignored", "merged"]
MemoryStatus = Literal["active", "edited", "forgotten", "merged"]
MemoryType = Literal["preference", "fact", "project", "relationship", "goal", "event", "note"]


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_type: SourceType
    content: str | None = None
    url: str | None = None
    filename: str | None = None


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


class ChunkRead(BaseModel):
    id: int
    source_id: int
    source_title: str
    text: str
    score: float


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: int | None = None


class CitationRead(BaseModel):
    source_id: int
    source_title: str
    chunk_id: int
    quote: str


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


class ReviewRead(BaseModel):
    sources_added: list[SourceRead]
    memories_confirmed: list[MemoryRead]
    pending_memories: list[MemoryCandidateRead]
    recent_questions: list[str]
    suggested_actions: list[str]
