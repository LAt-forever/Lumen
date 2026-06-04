# Lumen Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Lumen's first usable vertical loop: capture sources, index knowledge, ask with citations, create controllable memory candidates, retrieve confirmed memories, and review recent activity.

**Architecture:** Monorepo with a FastAPI backend and React/Vite frontend. The backend is local-first with SQLite, FTS5 keyword search, JSON-stored vectors, provider interfaces for LLM and embeddings, and deterministic offline providers for tests and first-run use. The frontend is a workbench-first app with a center ask/capture area, right-side source and memory context, and secondary Library, Memory, Search, Review, and Settings views.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2, Pydantic, pytest, httpx, pypdf, beautifulsoup4, React 18, TypeScript, Vite, TanStack Query, React Router, Vitest, Testing Library, lucide-react.

---

## Scope Check

This plan implements Phase 1 from `docs/superpowers/specs/2026-06-04-lumen-design.md`. It does not implement image library, graph visualization, tags, favorites, model configuration UI, Agent configuration UI, queue dashboard, or Docker deployment. The file and API boundaries below leave room for those Comet parity features without forcing heavy infrastructure into the first build.

## File Structure

Create this structure:

```text
.
├── README.md
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── service/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── sources.py
│   │   │   ├── chat.py
│   │   │   ├── memories.py
│   │   │   ├── search.py
│   │   │   └── review.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── chunking.py
│   │   │   ├── parsing.py
│   │   │   ├── embeddings.py
│   │   │   ├── llm.py
│   │   │   ├── knowledge.py
│   │   │   ├── memory.py
│   │   │   ├── chat.py
│   │   │   └── review.py
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── sources.py
│   │       ├── chunks.py
│   │       ├── conversations.py
│   │       ├── memories.py
│   │       └── review.py
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_sources.py
│       ├── test_knowledge.py
│       ├── test_chat.py
│       ├── test_memories.py
│       └── test_review.py
└── frontend/
    ├── package.json
    ├── index.html
    ├── tsconfig.json
    ├── tsconfig.node.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/client.ts
        ├── api/types.ts
        ├── api/hooks.ts
        ├── styles.css
        ├── components/
        │   ├── AppShell.tsx
        │   ├── CapturePanel.tsx
        │   ├── ChatPanel.tsx
        │   ├── ContextPanel.tsx
        │   ├── MemoryInbox.tsx
        │   ├── SourceList.tsx
        │   └── ReviewPanel.tsx
        └── test/
            ├── setup.ts
            └── workbench.test.tsx
```

## Task 1: Backend Foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/service/__init__.py`
- Create: `backend/service/config.py`
- Create: `backend/service/db.py`
- Create: `backend/service/main.py`
- Create: `backend/service/api/__init__.py`
- Create: `backend/service/api/router.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

Create `backend/tests/test_health.py`:

```python
def test_healthz_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Add backend package metadata**

Create `backend/pyproject.toml`:

```toml
[project]
name = "lumen-backend"
version = "0.1.0"
description = "Lumen personal AI knowledge base and memory assistant backend"
requires-python = ">=3.12"
dependencies = [
  "beautifulsoup4>=4.12.3",
  "fastapi>=0.115.0",
  "httpx>=0.27.2",
  "pydantic-settings>=2.5.2",
  "pypdf>=5.0.0",
  "python-multipart>=0.0.12",
  "sqlalchemy>=2.0.35",
  "uvicorn[standard]>=0.30.6",
]

[dependency-groups]
dev = [
  "pytest>=8.3.3",
  "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Install backend dependencies**

Run:

```bash
cd backend
uv sync
```

Expected: dependencies resolve and a `.venv` is created under `backend/`.

- [ ] **Step 4: Run the health test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/test_health.py -v
```

Expected: FAIL with an import error because `service.main` does not exist yet.

- [ ] **Step 5: Add backend app foundation**

Create `backend/service/__init__.py`:

```python
"""Lumen backend service."""
```

Create `backend/service/config.py`:

```python
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
```

Create `backend/service/db.py`:

```python
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from service.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine: Engine
SessionLocal: sessionmaker[Session]


def configure_database(database_url: str | None = None) -> None:
    global engine, SessionLocal

    url = database_url or get_settings().database_url
    engine = create_engine(url, connect_args=_connect_args(url))
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


configure_database()


def init_db() -> None:
    from service import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `backend/service/api/__init__.py`:

```python
"""API routers for Lumen."""
```

Create `backend/service/api/router.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

Create `backend/service/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service.api.router import router
from service.db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Lumen API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    return app


app = create_app()
```

Create `backend/tests/conftest.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.db import configure_database, init_db


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    from service.main import app

    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 6: Run health test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit backend foundation**

```bash
git add backend/pyproject.toml backend/service backend/tests
git commit -m "feat: add backend foundation"
```

## Task 2: Domain Models And Repositories

**Files:**
- Create: `backend/service/models.py`
- Create: `backend/service/schemas.py`
- Create: `backend/service/repositories/__init__.py`
- Create: `backend/service/repositories/sources.py`
- Create: `backend/service/repositories/chunks.py`
- Create: `backend/service/repositories/conversations.py`
- Create: `backend/service/repositories/memories.py`
- Test: `backend/tests/test_sources.py`

- [ ] **Step 1: Write repository tests for source lifecycle**

Create `backend/tests/test_sources.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.db import Base
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_source_lifecycle():
    db = make_session()
    repo = SourceRepository(db)

    source = repo.create(SourceCreate(title="Alpha Note", source_type="note", content="Alpha content"))
    assert source.id is not None
    assert source.status == "pending"

    repo.mark_parsing(source.id)
    db.refresh(source)
    assert source.status == "parsing"

    repo.mark_indexed(source.id)
    db.refresh(source)
    assert source.status == "indexed"


def test_source_failed_status_keeps_error_message():
    db = make_session()
    repo = SourceRepository(db)

    source = repo.create(SourceCreate(title="Bad Link", source_type="link", url="https://example.invalid"))
    repo.mark_failed(source.id, "Could not fetch URL")
    db.refresh(source)

    assert source.status == "failed"
    assert source.error_message == "Could not fetch URL"
```

- [ ] **Step 2: Run source tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_sources.py -v
```

Expected: FAIL because models and repositories are not defined.

- [ ] **Step 3: Add SQLAlchemy models**

Create `backend/service/models.py`:

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from service.db import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped[Source] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("source_chunks.id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)


class MemoryCandidate(Base):
    __tablename__ = "memory_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 4: Add Pydantic schemas**

Create `backend/service/schemas.py`:

```python
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
```

- [ ] **Step 5: Add repositories**

Create `backend/service/repositories/__init__.py`:

```python
"""Storage repositories for Lumen."""
```

Create `backend/service/repositories/sources.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Source
from service.schemas import SourceCreate


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: SourceCreate) -> Source:
        source = Source(**data.model_dump())
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get(self, source_id: int) -> Source | None:
        return self.db.get(Source, source_id)

    def list(self) -> list[Source]:
        return list(self.db.scalars(select(Source).order_by(Source.created_at.desc(), Source.id.desc())))

    def mark_parsing(self, source_id: int) -> None:
        self._set_status(source_id, "parsing", None)

    def mark_indexed(self, source_id: int) -> None:
        self._set_status(source_id, "indexed", None)

    def mark_failed(self, source_id: int, message: str) -> None:
        self._set_status(source_id, "failed", message)

    def _set_status(self, source_id: int, status: str, error_message: str | None) -> None:
        source = self.db.get(Source, source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        source.status = status
        source.error_message = error_message
        self.db.commit()
```

Create `backend/service/repositories/chunks.py`:

```python
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from service.models import SourceChunk


class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_for_source(self, source_id: int, chunks: list[tuple[str, str]]) -> list[SourceChunk]:
        self.db.execute(delete(SourceChunk).where(SourceChunk.source_id == source_id))
        rows = [
            SourceChunk(source_id=source_id, chunk_index=index, text=text, embedding_json=embedding_json)
            for index, (text, embedding_json) in enumerate(chunks)
        ]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def list_all(self) -> list[SourceChunk]:
        return list(self.db.scalars(select(SourceChunk).order_by(SourceChunk.id.asc())))
```

Create `backend/service/repositories/conversations.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Citation, Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, conversation_id: int | None, title: str) -> Conversation:
        if conversation_id is not None:
            conversation = self.db.get(Conversation, conversation_id)
            if conversation is not None:
                return conversation
        conversation = Conversation(title=title[:300])
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def add_citation(self, message_id: int, source_id: int, chunk_id: int, quote: str) -> Citation:
        citation = Citation(message_id=message_id, source_id=source_id, chunk_id=chunk_id, quote=quote)
        self.db.add(citation)
        self.db.commit()
        self.db.refresh(citation)
        return citation

    def recent_user_questions(self, limit: int = 5) -> list[str]:
        stmt = select(Message.content).where(Message.role == "user").order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        return list(self.db.scalars(stmt))
```

Create `backend/service/repositories/memories.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Memory, MemoryCandidate


class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_candidate(self, text: str, memory_type: str, source_kind: str, source_ref: str, confidence: int) -> MemoryCandidate:
        candidate = MemoryCandidate(
            text=text,
            memory_type=memory_type,
            source_kind=source_kind,
            source_ref=source_ref,
            confidence=confidence,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def pending_candidates(self) -> list[MemoryCandidate]:
        stmt = select(MemoryCandidate).where(MemoryCandidate.status == "pending").order_by(MemoryCandidate.created_at.desc(), MemoryCandidate.id.desc())
        return list(self.db.scalars(stmt))

    def confirm(self, candidate_id: int, text: str | None = None, memory_type: str | None = None) -> Memory:
        candidate = self.db.get(MemoryCandidate, candidate_id)
        if candidate is None:
            raise ValueError(f"candidate {candidate_id} not found")
        candidate.status = "confirmed"
        memory = Memory(
            text=text or candidate.text,
            memory_type=memory_type or candidate.memory_type,
            provenance=f"{candidate.source_kind}:{candidate.source_ref}",
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def ignore(self, candidate_id: int) -> None:
        candidate = self.db.get(MemoryCandidate, candidate_id)
        if candidate is None:
            raise ValueError(f"candidate {candidate_id} not found")
        candidate.status = "ignored"
        self.db.commit()

    def active_memories(self) -> list[Memory]:
        stmt = select(Memory).where(Memory.status.in_(["active", "edited"])).order_by(Memory.updated_at.desc(), Memory.id.desc())
        return list(self.db.scalars(stmt))
```

- [ ] **Step 6: Run repository tests**

Run:

```bash
cd backend
uv run pytest tests/test_sources.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit domain models**

```bash
git add backend/service backend/tests/test_sources.py
git commit -m "feat: add domain models and repositories"
```

## Task 3: Knowledge Parsing, Chunking, Embeddings, And Search

**Files:**
- Create: `backend/service/core/parsing.py`
- Create: `backend/service/core/chunking.py`
- Create: `backend/service/core/embeddings.py`
- Create: `backend/service/core/knowledge.py`
- Test: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write knowledge service tests**

Create `backend/tests/test_knowledge.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.knowledge import KnowledgeService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_service():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    return db, KnowledgeService(SourceRepository(db), ChunkRepository(db))


def test_index_source_creates_searchable_chunks():
    db, service = make_service()
    source = service.sources.create(SourceCreate(title="Lumen Note", source_type="note", content="Lumen remembers project context and cites sources."))

    service.index_source(source.id)
    db.refresh(source)

    results = service.search("project context", limit=5)
    assert source.status == "indexed"
    assert len(results) >= 1
    assert results[0].source_title == "Lumen Note"
    assert "project context" in results[0].text


def test_failed_parse_marks_source_failed():
    db, service = make_service()
    source = service.sources.create(SourceCreate(title="Empty", source_type="note", content=""))

    service.index_source(source.id)
    db.refresh(source)

    assert source.status == "failed"
    assert source.error_message == "No text content found"
```

- [ ] **Step 2: Run knowledge tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_knowledge.py -v
```

Expected: FAIL because `KnowledgeService` is not defined.

- [ ] **Step 3: Add parser and chunker**

Create `backend/service/core/__init__.py`:

```python
"""Core Lumen application services."""
```

Create `backend/service/core/parsing.py`:

```python
from bs4 import BeautifulSoup
from pypdf import PdfReader


def parse_note(content: str | None) -> str:
    return (content or "").strip()


def parse_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def parse_pdf(path: str) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(page.strip() for page in pages if page.strip())
```

Create `backend/service/core/chunking.py`:

```python
def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks
```

- [ ] **Step 4: Add deterministic embedding provider**

Create `backend/service/core/embeddings.py`:

```python
import hashlib
import json
import math
import re

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class HashEmbeddingProvider:
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def dumps_embedding(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def loads_embedding(payload: str) -> list[float]:
    data = json.loads(payload)
    return [float(value) for value in data]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
```

- [ ] **Step 5: Add knowledge service**

Create `backend/service/core/knowledge.py`:

```python
from dataclasses import dataclass

from service.core.chunking import chunk_text
from service.core.embeddings import HashEmbeddingProvider, cosine, dumps_embedding, loads_embedding
from service.models import SourceChunk
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead


@dataclass
class RankedChunk:
    chunk: SourceChunk
    score: float


class KnowledgeService:
    def __init__(
        self,
        sources: SourceRepository,
        chunks: ChunkRepository,
        embeddings: HashEmbeddingProvider | None = None,
    ):
        self.sources = sources
        self.chunks = chunks
        self.embeddings = embeddings or HashEmbeddingProvider()

    def index_source(self, source_id: int) -> None:
        source = self.sources.get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        self.sources.mark_parsing(source_id)
        text = (source.content or "").strip()
        chunks = chunk_text(text)
        if not chunks:
            self.sources.mark_failed(source_id, "No text content found")
            return
        indexed = [(chunk, dumps_embedding(self.embeddings.embed(chunk))) for chunk in chunks]
        self.chunks.replace_for_source(source_id, indexed)
        self.sources.mark_indexed(source_id)

    def search(self, query: str, limit: int = 5) -> list[ChunkRead]:
        query_vector = self.embeddings.embed(query)
        query_terms = {term.lower() for term in query.split() if term.strip()}
        ranked: list[RankedChunk] = []
        for chunk in self.chunks.list_all():
            vector_score = cosine(query_vector, loads_embedding(chunk.embedding_json))
            keyword_score = sum(1.0 for term in query_terms if term in chunk.text.lower())
            score = vector_score + keyword_score
            if score > 0:
                ranked.append(RankedChunk(chunk=chunk, score=score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return [
            ChunkRead(
                id=item.chunk.id,
                source_id=item.chunk.source_id,
                source_title=item.chunk.source.title,
                text=item.chunk.text,
                score=item.score,
            )
            for item in ranked[:limit]
        ]
```

- [ ] **Step 6: Run knowledge tests**

Run:

```bash
cd backend
uv run pytest tests/test_knowledge.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit knowledge service**

```bash
git add backend/service/core backend/tests/test_knowledge.py
git commit -m "feat: add local knowledge indexing"
```

## Task 4: Memory Service

**Files:**
- Create: `backend/service/core/memory.py`
- Test: `backend/tests/test_memories.py`

- [ ] **Step 1: Write memory lifecycle tests**

Create `backend/tests/test_memories.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.memory import MemoryService
from service.db import Base
from service.repositories.memories import MemoryRepository


def make_service():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    return MemoryService(MemoryRepository(db))


def test_extracts_project_memory_candidate():
    service = make_service()

    candidates = service.extract_candidates("我正在做 Lumen 这个个人 AI 知识库项目。", source_kind="message", source_ref="1")

    assert len(candidates) == 1
    assert candidates[0].memory_type == "project"
    assert "Lumen" in candidates[0].text


def test_confirm_candidate_creates_active_memory():
    service = make_service()
    candidate = service.extract_candidates("我喜欢引用清楚的回答。", source_kind="message", source_ref="1")[0]

    memory = service.confirm(candidate.id, text="用户喜欢引用清楚的回答。", memory_type="preference")

    assert memory.status == "active"
    assert memory.memory_type == "preference"
    assert memory.text == "用户喜欢引用清楚的回答。"
```

- [ ] **Step 2: Run memory tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_memories.py -v
```

Expected: FAIL because `MemoryService` is not defined.

- [ ] **Step 3: Add memory service**

Create `backend/service/core/memory.py`:

```python
from service.models import Memory, MemoryCandidate
from service.repositories.memories import MemoryRepository


class MemoryService:
    def __init__(self, memories: MemoryRepository):
        self.memories = memories

    def extract_candidates(self, text: str, source_kind: str, source_ref: str) -> list[MemoryCandidate]:
        stripped = text.strip()
        if not stripped:
            return []
        lowered = stripped.lower()
        memory_type = self._classify(stripped, lowered)
        if memory_type is None:
            return []
        candidate_text = self._normalize(stripped, memory_type)
        return [
            self.memories.create_candidate(
                text=candidate_text,
                memory_type=memory_type,
                source_kind=source_kind,
                source_ref=source_ref,
                confidence=72,
            )
        ]

    def confirm(self, candidate_id: int, text: str | None = None, memory_type: str | None = None) -> Memory:
        return self.memories.confirm(candidate_id, text=text, memory_type=memory_type)

    def ignore(self, candidate_id: int) -> None:
        self.memories.ignore(candidate_id)

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, Memory]] = []
        for memory in self.memories.active_memories():
            score = sum(1 for term in terms if term in memory.text.lower())
            if score > 0 or not terms:
                scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def _classify(self, text: str, lowered: str) -> str | None:
        if any(marker in text for marker in ["正在做", "项目", "project"]):
            return "project"
        if any(marker in text for marker in ["喜欢", "偏好", "prefer", "like"]):
            return "preference"
        if any(marker in text for marker in ["目标", "希望", "想要"]):
            return "goal"
        return None

    def _normalize(self, text: str, memory_type: str) -> str:
        if text.endswith("。"):
            return text
        if text.endswith("."):
            return text
        return f"{text}。"
```

- [ ] **Step 4: Run memory tests**

Run:

```bash
cd backend
uv run pytest tests/test_memories.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit memory service**

```bash
git add backend/service/core/memory.py backend/tests/test_memories.py
git commit -m "feat: add memory candidate lifecycle"
```

## Task 5: Chat Orchestrator With Citations And Memories

**Files:**
- Create: `backend/service/core/llm.py`
- Create: `backend/service/core/chat.py`
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Write chat tests**

Create `backend/tests/test_chat.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.memory import MemoryService
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, SourceCreate


def make_orchestrator():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    sources = SourceRepository(db)
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    conversations = ConversationRepository(db)
    return db, sources, knowledge, memories, ChatOrchestrator(conversations, knowledge, memories)


def test_chat_answer_includes_citation():
    db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(SourceCreate(title="Lumen Principles", source_type="note", content="Lumen answers should show clear citations."))
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="What should Lumen answers show?"))

    assert response.conversation_id > 0
    assert "citations" in response.answer.lower()
    assert len(response.citations) == 1
    assert response.citations[0].source_title == "Lumen Principles"


def test_chat_creates_pending_memory_candidate():
    _db, _sources, _knowledge, memories, chat = make_orchestrator()

    response = chat.ask(ChatRequest(message="我正在做 Lumen 这个个人 AI 知识库项目。"))
    pending = memories.memories.pending_candidates()

    assert response.conversation_id > 0
    assert len(pending) == 1
    assert pending[0].memory_type == "project"
```

- [ ] **Step 2: Run chat tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py -v
```

Expected: FAIL because `ChatOrchestrator` is not defined.

- [ ] **Step 3: Add extractive LLM provider**

Create `backend/service/core/llm.py`:

```python
from service.schemas import ChunkRead


class ExtractiveAnswerProvider:
    def answer(self, question: str, chunks: list[ChunkRead], memories: list[str]) -> tuple[str, str]:
        if chunks:
            source_bits = " ".join(chunk.text for chunk in chunks[:2])
            memory_bits = f" Relevant confirmed memories: {' '.join(memories)}" if memories else ""
            return f"Based on your sources, {source_bits}{memory_bits}", "grounded"
        if memories:
            return f"I found relevant confirmed memories: {' '.join(memories)}", "memory-only"
        return "I do not have enough evidence in Lumen yet. Add a source or confirm a relevant memory first.", "weak"
```

- [ ] **Step 4: Add chat orchestrator**

Create `backend/service/core/chat.py`:

```python
from service.core.knowledge import KnowledgeService
from service.core.llm import ExtractiveAnswerProvider
from service.core.memory import MemoryService
from service.repositories.conversations import ConversationRepository
from service.schemas import ChatRequest, ChatResponse, CitationRead, UsedMemoryRead


class ChatOrchestrator:
    def __init__(
        self,
        conversations: ConversationRepository,
        knowledge: KnowledgeService,
        memories: MemoryService,
        answer_provider: ExtractiveAnswerProvider | None = None,
    ):
        self.conversations = conversations
        self.knowledge = knowledge
        self.memories = memories
        self.answer_provider = answer_provider or ExtractiveAnswerProvider()

    def ask(self, request: ChatRequest) -> ChatResponse:
        title = request.message[:60] or "New conversation"
        conversation = self.conversations.get_or_create(request.conversation_id, title)
        user_message = self.conversations.add_message(conversation.id, "user", request.message)

        chunks = self.knowledge.search(request.message, limit=4)
        memory_rows = self.memories.search(request.message, limit=4)
        answer, confidence = self.answer_provider.answer(request.message, chunks, [memory.text for memory in memory_rows])

        assistant_message = self.conversations.add_message(conversation.id, "assistant", answer)
        citations: list[CitationRead] = []
        for chunk in chunks[:3]:
            self.conversations.add_citation(assistant_message.id, chunk.source_id, chunk.id, chunk.text[:300])
            citations.append(CitationRead(source_id=chunk.source_id, source_title=chunk.source_title, chunk_id=chunk.id, quote=chunk.text[:300]))

        self.memories.extract_candidates(request.message, source_kind="message", source_ref=str(user_message.id))

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            answer=answer,
            citations=citations,
            memories=[UsedMemoryRead(id=memory.id, text=memory.text, memory_type=memory.memory_type) for memory in memory_rows],
            confidence=confidence,
        )
```

- [ ] **Step 5: Run chat tests**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit chat orchestrator**

```bash
git add backend/service/core/llm.py backend/service/core/chat.py backend/tests/test_chat.py
git commit -m "feat: add cited chat orchestrator"
```

## Task 6: Backend API Routes

**Files:**
- Create: `backend/service/api/sources.py`
- Create: `backend/service/api/chat.py`
- Create: `backend/service/api/memories.py`
- Create: `backend/service/api/search.py`
- Create: `backend/service/api/review.py`
- Modify: `backend/service/api/router.py`
- Test: `backend/tests/test_review.py`

- [ ] **Step 1: Write API integration tests**

Create `backend/tests/test_review.py`:

```python
def test_core_api_loop(client):
    created = client.post("/api/sources", json={"title": "Source A", "source_type": "note", "content": "Lumen gives answers with citations."})
    assert created.status_code == 200
    source_id = created.json()["id"]

    indexed = client.post(f"/api/sources/{source_id}/index")
    assert indexed.status_code == 200
    assert indexed.json()["status"] == "indexed"

    answer = client.post("/api/chat", json={"message": "What does Lumen give?"})
    assert answer.status_code == 200
    assert len(answer.json()["citations"]) >= 1

    review = client.get("/api/review")
    assert review.status_code == 200
    assert len(review.json()["sources_added"]) >= 1
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/test_review.py -v
```

Expected: FAIL because `/api/sources` does not exist.

- [ ] **Step 3: Add source, chat, memory, search, and review routes**

Create `backend/service/api/sources.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate, SourceRead

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _service(db: Session) -> KnowledgeService:
    return KnowledgeService(SourceRepository(db), ChunkRepository(db))


@router.post("", response_model=SourceRead)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(payload)


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return SourceRepository(db).list()


@router.post("/{source_id}/index", response_model=SourceRead)
def index_source(source_id: int, db: Session = Depends(get_db)):
    service = _service(db)
    service.index_source(source_id)
    source = service.sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
```

Create `backend/service/api/chat.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.core.chat import ChatOrchestrator
from service.core.knowledge import KnowledgeService
from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def ask(payload: ChatRequest, db: Session = Depends(get_db)):
    knowledge = KnowledgeService(SourceRepository(db), ChunkRepository(db))
    memories = MemoryService(MemoryRepository(db))
    orchestrator = ChatOrchestrator(ConversationRepository(db), knowledge, memories)
    return orchestrator.ask(payload)
```

Create `backend/service/api/memories.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.core.memory import MemoryService
from service.db import get_db
from service.repositories.memories import MemoryRepository
from service.schemas import MemoryCandidateRead, MemoryRead, MemoryUpdate

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("/candidates", response_model=list[MemoryCandidateRead])
def pending_candidates(db: Session = Depends(get_db)):
    return MemoryRepository(db).pending_candidates()


@router.post("/candidates/{candidate_id}/confirm", response_model=MemoryRead)
def confirm_candidate(candidate_id: int, payload: MemoryUpdate | None = None, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    return service.confirm(
        candidate_id,
        text=payload.text if payload else None,
        memory_type=payload.memory_type if payload else None,
    )


@router.post("/candidates/{candidate_id}/ignore")
def ignore_candidate(candidate_id: int, db: Session = Depends(get_db)):
    MemoryService(MemoryRepository(db)).ignore(candidate_id)
    return {"status": "ignored"}


@router.get("", response_model=list[MemoryRead])
def list_memories(db: Session = Depends(get_db)):
    return MemoryRepository(db).active_memories()
```

Create `backend/service/api/search.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[ChunkRead])
def search(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    return KnowledgeService(SourceRepository(db), ChunkRepository(db)).search(q)
```

Create `backend/service/api/review.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.core.review import ReviewService
from service.db import get_db
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ReviewRead

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("", response_model=ReviewRead)
def review(db: Session = Depends(get_db)):
    return ReviewService(SourceRepository(db), MemoryRepository(db), ConversationRepository(db)).recent()
```

- [ ] **Step 4: Add review service**

Create `backend/service/core/review.py`:

```python
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ReviewRead


class ReviewService:
    def __init__(self, sources: SourceRepository, memories: MemoryRepository, conversations: ConversationRepository):
        self.sources = sources
        self.memories = memories
        self.conversations = conversations

    def recent(self) -> ReviewRead:
        pending = self.memories.pending_candidates()
        active = self.memories.active_memories()
        suggestions = []
        if pending:
            suggestions.append(f"Review {len(pending)} pending memory candidate(s).")
        if not active:
            suggestions.append("Confirm a memory so Lumen can personalize future answers.")
        if not suggestions:
            suggestions.append("Ask Lumen a follow-up question using your confirmed memories.")
        return ReviewRead(
            sources_added=self.sources.list()[:5],
            memories_confirmed=active[:5],
            pending_memories=pending[:5],
            recent_questions=self.conversations.recent_user_questions(),
            suggested_actions=suggestions,
        )
```

- [ ] **Step 5: Wire API router**

Modify `backend/service/api/router.py`:

```python
from fastapi import APIRouter

from service.api import chat, memories, review, search, sources

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(sources.router)
router.include_router(chat.router)
router.include_router(memories.router)
router.include_router(search.router)
router.include_router(review.router)
```

- [ ] **Step 6: Run backend test suite**

Run:

```bash
cd backend
uv run pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 7: Commit API routes**

```bash
git add backend/service/api backend/service/core/review.py backend/tests/test_review.py
git commit -m "feat: expose core Lumen API"
```

## Task 7: Frontend Foundation And Workbench Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/test/setup.ts`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Add frontend package**

Create `frontend/package.json`:

```json
{
  "name": "lumen-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.16",
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.3",
    "jsdom": "^25.0.1",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Lumen</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 2: Install frontend dependencies**

Run:

```bash
cd frontend
npm install
```

Expected: `node_modules` and `package-lock.json` are created.

- [ ] **Step 3: Write failing shell test**

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

Create `frontend/src/test/workbench.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../App'

describe('Lumen workbench', () => {
  it('renders the workbench-first home screen', () => {
    render(<App />)

    expect(screen.getByText('Lumen')).toBeInTheDocument()
    expect(screen.getByText('Ask or capture')).toBeInTheDocument()
    expect(screen.getByText('Memory Inbox')).toBeInTheDocument()
    expect(screen.getByText('Context Now')).toBeInTheDocument()
  })
})
```

- [ ] **Step 4: Run frontend test to verify it fails**

Run:

```bash
cd frontend
npm run test -- src/test/workbench.test.tsx
```

Expected: FAIL because `src/App.tsx` does not exist.

- [ ] **Step 5: Add app shell**

Create `frontend/src/main.tsx`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'

import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

Create `frontend/src/App.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BookOpen, Brain, Home, MessageSquare, Search, Settings, Sparkles } from 'lucide-react'

import { AppShell } from './components/AppShell'

const queryClient = new QueryClient()

const navItems = [
  { label: 'Today', icon: Home },
  { label: 'Ask', icon: MessageSquare },
  { label: 'Library', icon: BookOpen },
  { label: 'Memory', icon: Brain },
  { label: 'Search', icon: Search },
  { label: 'Review', icon: Sparkles },
  { label: 'Settings', icon: Settings },
]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell navItems={navItems} />
    </QueryClientProvider>
  )
}
```

Create `frontend/src/components/AppShell.tsx`:

```tsx
import type { LucideIcon } from 'lucide-react'

type NavItem = {
  label: string
  icon: LucideIcon
}

type AppShellProps = {
  navItems: NavItem[]
}

export function AppShell({ navItems }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Lumen</div>
        <nav aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button className="nav-item" key={item.label} type="button">
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </aside>
      <main className="workbench">
        <section className="hero-strip">
          <p className="eyebrow">Continue where you left off</p>
          <h1>Ask, capture, and trust what Lumen remembers.</h1>
        </section>
        <section className="center-panel" aria-label="Ask or capture">
          <h2>Ask or capture</h2>
          <label className="field-label" htmlFor="ask-lumen">Ask a question, write a note, or paste a link</label>
          <textarea id="ask-lumen" aria-label="Ask Lumen" />
          <div className="action-row">
            <button type="button">Ask Lumen</button>
            <button type="button" className="secondary">Add source</button>
          </div>
        </section>
        <aside className="context-column">
          <section>
            <h2>Memory Inbox</h2>
            <p>No pending memories yet.</p>
          </section>
          <section>
            <h2>Context Now</h2>
            <p>Sources and recalled memories will appear here.</p>
          </section>
        </aside>
      </main>
    </div>
  )
}
```

Create `frontend/src/styles.css`:

```css
:root {
  color: #182026;
  background: #f5f7f8;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 232px 1fr;
}

.sidebar {
  border-right: 1px solid #d8dee2;
  background: #ffffff;
  padding: 20px 14px;
}

.brand {
  font-size: 22px;
  font-weight: 700;
  margin: 4px 10px 24px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  color: #4b5c68;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}

.nav-item:hover {
  background: #eef3f5;
  color: #182026;
}

.workbench {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) 360px;
  gap: 18px;
  padding: 22px;
}

.hero-strip,
.center-panel,
.context-column section {
  background: #ffffff;
  border: 1px solid #d8dee2;
  border-radius: 8px;
}

.hero-strip {
  grid-column: 1 / -1;
  padding: 20px 22px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #5d6f7a;
  font-size: 13px;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

.center-panel {
  padding: 18px;
}

.center-panel textarea {
  width: 100%;
  min-height: 180px;
  resize: vertical;
  border: 1px solid #c8d2d8;
  border-radius: 8px;
  padding: 14px;
}

.field-label {
  display: block;
  color: #4b5c68;
  margin-bottom: 8px;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.action-row button {
  border: 0;
  border-radius: 8px;
  padding: 10px 14px;
  background: #185c67;
  color: white;
  cursor: pointer;
}

.action-row .secondary {
  background: #e6eef0;
  color: #185c67;
}

.context-column {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.context-column section {
  padding: 18px;
}
```

- [ ] **Step 6: Run frontend test**

Run:

```bash
cd frontend
npm run test -- src/test/workbench.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit frontend foundation**

```bash
git add frontend
git commit -m "feat: add Lumen workbench shell"
```

## Task 8: Frontend API Integration And Core Panels

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/hooks.ts`
- Create: `frontend/src/components/CapturePanel.tsx`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/ContextPanel.tsx`
- Create: `frontend/src/components/MemoryInbox.tsx`
- Create: `frontend/src/components/SourceList.tsx`
- Create: `frontend/src/components/ReviewPanel.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Add frontend API types**

Create `frontend/src/api/types.ts`:

```ts
export type SourceRead = {
  id: number
  title: string
  source_type: string
  status: string
  url: string | null
  filename: string | null
  error_message: string | null
  created_at: string
}

export type ChatResponse = {
  conversation_id: number
  message_id: number
  answer: string
  citations: Array<{ source_id: number; source_title: string; chunk_id: number; quote: string }>
  memories: Array<{ id: number; text: string; memory_type: string }>
  confidence: string
}

export type MemoryCandidateRead = {
  id: number
  text: string
  memory_type: string
  source_kind: string
  source_ref: string
  confidence: number
  status: string
  created_at: string
}

export type MemoryRead = {
  id: number
  text: string
  memory_type: string
  provenance: string
  status: string
  created_at: string
}

export type ReviewRead = {
  sources_added: SourceRead[]
  memories_confirmed: MemoryRead[]
  pending_memories: MemoryCandidateRead[]
  recent_questions: string[]
  suggested_actions: string[]
}
```

- [ ] **Step 2: Add API client and hooks**

Create `frontend/src/api/client.ts`:

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

export const api = {
  listSources: () => request('/api/sources'),
  createSource: (payload: { title: string; source_type: 'note'; content: string }) =>
    request('/api/sources', { method: 'POST', body: JSON.stringify(payload) }),
  indexSource: (sourceId: number) => request(`/api/sources/${sourceId}/index`, { method: 'POST' }),
  ask: (message: string, conversationId?: number) =>
    request('/api/chat', { method: 'POST', body: JSON.stringify({ message, conversation_id: conversationId }) }),
  pendingMemories: () => request('/api/memories/candidates'),
  confirmMemory: (candidateId: number, payload: { text: string; memory_type: string }) =>
    request(`/api/memories/candidates/${candidateId}/confirm`, { method: 'POST', body: JSON.stringify(payload) }),
  ignoreMemory: (candidateId: number) =>
    request(`/api/memories/candidates/${candidateId}/ignore`, { method: 'POST' }),
  review: () => request('/api/review'),
}
```

Create `frontend/src/api/hooks.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { ChatResponse, MemoryCandidateRead, ReviewRead, SourceRead } from './types'

export function useSources() {
  return useQuery<SourceRead[]>({ queryKey: ['sources'], queryFn: () => api.listSources() as Promise<SourceRead[]> })
}

export function useCreateSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.createSource,
    onSuccess: async (source: unknown) => {
      const created = source as SourceRead
      await api.indexSource(created.id)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useAskLumen() {
  const queryClient = useQueryClient()
  return useMutation<ChatResponse, Error, string>({
    mutationFn: (message) => api.ask(message) as Promise<ChatResponse>,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'pending'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function usePendingMemories() {
  return useQuery<MemoryCandidateRead[]>({
    queryKey: ['memories', 'pending'],
    queryFn: () => api.pendingMemories() as Promise<MemoryCandidateRead[]>,
  })
}

export function useReview() {
  return useQuery<ReviewRead>({ queryKey: ['review'], queryFn: () => api.review() as Promise<ReviewRead> })
}
```

- [ ] **Step 3: Add focused panels**

Create panel components with these public props:

```tsx
// CapturePanel.tsx
export function CapturePanel() {
  return <section className="panel"><h2>Ask or capture</h2></section>
}
```

```tsx
// ChatPanel.tsx
export function ChatPanel() {
  return <section className="panel"><h2>Conversation</h2></section>
}
```

```tsx
// ContextPanel.tsx
import type { ChatResponse } from '../api/types'

export function ContextPanel({ response }: { response?: ChatResponse }) {
  return (
    <section className="panel">
      <h2>Context Now</h2>
      {response ? <p>{response.confidence}</p> : <p>Sources and recalled memories will appear here.</p>}
    </section>
  )
}
```

```tsx
// MemoryInbox.tsx
import { usePendingMemories } from '../api/hooks'

export function MemoryInbox() {
  const { data = [] } = usePendingMemories()
  return (
    <section className="panel">
      <h2>Memory Inbox</h2>
      {data.length === 0 ? <p>No pending memories yet.</p> : data.map((item) => <p key={item.id}>{item.text}</p>)}
    </section>
  )
}
```

```tsx
// SourceList.tsx
import { useSources } from '../api/hooks'

export function SourceList() {
  const { data = [] } = useSources()
  return (
    <section className="panel">
      <h2>Recent Sources</h2>
      {data.length === 0 ? <p>No sources yet.</p> : data.map((source) => <p key={source.id}>{source.title}</p>)}
    </section>
  )
}
```

```tsx
// ReviewPanel.tsx
import { useReview } from '../api/hooks'

export function ReviewPanel() {
  const { data } = useReview()
  return (
    <section className="panel">
      <h2>Daily Review</h2>
      {(data?.suggested_actions ?? ['Add a source to begin.']).map((action) => <p key={action}>{action}</p>)}
    </section>
  )
}
```

- [ ] **Step 4: Refactor AppShell to use panels**

Modify `frontend/src/components/AppShell.tsx` so the workbench body renders `CapturePanel`, `SourceList`, `ReviewPanel`, `MemoryInbox`, and `ContextPanel`.

Use this import block:

```tsx
import { CapturePanel } from './CapturePanel'
import { ContextPanel } from './ContextPanel'
import { MemoryInbox } from './MemoryInbox'
import { ReviewPanel } from './ReviewPanel'
import { SourceList } from './SourceList'
```

Use this center/right body:

```tsx
<section className="center-column">
  <CapturePanel />
  <SourceList />
  <ReviewPanel />
</section>
<aside className="context-column">
  <MemoryInbox />
  <ContextPanel />
</aside>
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend
npm run test
npm run build
```

Expected: tests PASS and build succeeds.

- [ ] **Step 6: Commit frontend API integration**

```bash
git add frontend/src
git commit -m "feat: connect workbench to Lumen API"
```

## Task 9: Documentation And End-To-End Verification

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Add environment example**

Create `.env.example`:

```dotenv
LUMEN_DATABASE_URL=sqlite:///./lumen.db
LUMEN_DATA_DIR=./data
LUMEN_LLM_MODE=extractive
LUMEN_EMBEDDING_MODE=hash
VITE_API_BASE=http://127.0.0.1:8000
```

- [ ] **Step 2: Add README**

Create `README.md`:

```markdown
# Lumen

Lumen is a personal AI knowledge base and long-term memory assistant.

## Phase 1

The first version focuses on the core loop:

- capture notes and sources
- index knowledge
- ask questions with citations
- extract pending memory candidates
- confirm or ignore memory candidates
- review recent sources and memories

## Run Backend

```bash
cd backend
uv sync
uv run uvicorn service.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Test

```bash
cd backend
uv run pytest -v

cd ../frontend
npm run test
npm run build
```
```

- [ ] **Step 3: Ensure ignored local artifacts**

Modify `.gitignore` to include:

```gitignore
backend/.venv/
backend/lumen.db
backend/data/
frontend/node_modules/
frontend/dist/
frontend/.vite/
```

- [ ] **Step 4: Run backend verification**

Run:

```bash
cd backend
uv run pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd frontend
npm run test
npm run build
```

Expected: tests PASS and build succeeds.

- [ ] **Step 6: Start both servers and smoke test**

Run backend:

```bash
cd backend
uv run uvicorn service.main:app --host 127.0.0.1 --port 8000
```

Run frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Smoke test:

```bash
curl -s http://127.0.0.1:8000/healthz
```

Expected output:

```json
{"status":"ok"}
```

- [ ] **Step 7: Commit docs and verification setup**

```bash
git add README.md .env.example .gitignore
git commit -m "docs: add Lumen local setup"
```

## Task 10: Phase 1 Acceptance Pass

**Files:**
- Modify only files required by failing acceptance checks.

- [ ] **Step 1: Run all verification commands**

Run:

```bash
cd backend
uv run pytest -v
cd ../frontend
npm run test
npm run build
```

Expected: all commands PASS.

- [ ] **Step 2: Manual API acceptance**

With the backend running on `127.0.0.1:8000`, run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/sources \
  -H 'Content-Type: application/json' \
  -d '{"title":"Acceptance Note","source_type":"note","content":"Lumen should cite sources and manage memories."}'
```

Expected: JSON containing `"status":"pending"` and an integer `"id"`.

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/sources/1/index
```

Expected: JSON containing `"status":"indexed"`.

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What should Lumen cite?"}'
```

Expected: JSON with non-empty `answer` and at least one item in `citations`.

- [ ] **Step 3: Manual frontend acceptance**

Open `http://127.0.0.1:5173` and verify:

- Lumen brand is visible.
- Ask / Capture is the primary center surface.
- Memory Inbox is visible.
- Context Now is visible.
- Recent Sources and Daily Review are visible.

- [ ] **Step 4: Fix only acceptance failures**

If an acceptance check fails, make the smallest code change that addresses that check and rerun the failing command. Do not add parity-expansion features during this task.

- [ ] **Step 5: Final commit**

```bash
git status --short
git add backend frontend README.md .env.example .gitignore
git commit -m "chore: complete Lumen phase 1 acceptance"
```

If there are no file changes after acceptance checks, skip the commit and record the successful verification output in the final handoff.

## Self-Review Notes

- Spec coverage: Phase 1 capture, knowledge base, chat, memory inbox, review, trust signals, error handling, and testing are covered by Tasks 1 through 10.
- Comet parity coverage: parity expansion is explicitly recorded in the design spec and is protected by the file boundaries here; the first implementation does not pretend to ship graph visualization, image library, or model configuration UI.
- Type consistency: `SourceRead`, `ChunkRead`, `ChatResponse`, `MemoryCandidateRead`, `MemoryRead`, and `ReviewRead` are defined in backend schemas and mirrored in frontend API types.
- Test-first flow: each backend feature task begins with failing tests, then minimal implementation, then verification, then commit.
