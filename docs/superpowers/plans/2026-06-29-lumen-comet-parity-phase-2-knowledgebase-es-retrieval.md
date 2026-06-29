# Lumen Comet Parity Phase 2 KnowledgeBase and ES Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-knowledge-base ownership, real OpenAI-compatible embeddings, Elasticsearch BM25/vector hybrid retrieval, and switch search/chat to the new retrieval path.

**Architecture:** PostgreSQL remains the canonical store for users, knowledge bases, sources, chunks, provider profiles, and indexing runs. Elasticsearch stores a rebuildable source chunk projection scoped by `user_id` and `knowledge_base_id`. Retrieval routes through one service that can use ES hybrid search, rerank scoped candidates, and fall back to the current local retrieval path in `auto` mode.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, Redis, httpx, Elasticsearch HTTP API, React, TanStack Query, Vitest, Pytest.

---

## Approved Spec

- `docs/superpowers/specs/2026-06-29-lumen-comet-parity-phase-2-knowledgebase-es-retrieval-design.md`

## Execution Notes

- Work on branch `codex/comet-parity-phase-2-knowledgebase-es-retrieval`.
- Do not include the existing untracked `.claude/` directory in any commit.
- Remote sync may fail in this environment because direct GitHub 443 access timed out after proxy variables were cleared. If network remains unavailable, continue from local commit `207dc9c` after confirming with the user.
- Use one implementer subagent per task. Do not run multiple implementation subagents in parallel because many tasks touch shared models, schemas, and APIs.
- After every implementation task, run a spec-compliance review and a code-quality review before moving to the next task.

## File Map

Backend model and migrations:

- Modify: `backend/service/models.py`
- Create: `backend/alembic/versions/20260629_0003_knowledgebase_es_retrieval.py`

Backend repositories:

- Create: `backend/service/repositories/knowledge_bases.py`
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/repositories/chunks.py`
- Modify: `backend/service/repositories/ingestion_jobs.py`
- Modify: `backend/service/repositories/provider_profiles.py`
- Modify: `backend/service/repositories/agent.py`

Backend APIs and schemas:

- Create: `backend/service/api/knowledge_bases.py`
- Modify: `backend/service/api/router.py`
- Modify: `backend/service/api/sources.py`
- Modify: `backend/service/api/ingestion_jobs.py`
- Modify: `backend/service/api/search.py`
- Modify: `backend/service/api/chat.py`
- Modify: `backend/service/api/settings.py`
- Modify: `backend/service/api/status.py`
- Modify: `backend/service/schemas.py`

Backend core services:

- Modify: `backend/service/config.py`
- Modify: `backend/service/core/embeddings.py`
- Create: `backend/service/core/elasticsearch_projection.py`
- Create: `backend/service/core/retrieval.py`
- Modify: `backend/service/core/knowledge.py`
- Modify: `backend/service/core/ingestion.py`
- Modify: `backend/service/core/chat.py`
- Modify: `backend/service/worker.py`

Backend eval and tests:

- Modify: `backend/service/eval/retrieval.py`
- Modify: `backend/service/eval/retrieval_cases.json`
- Create: `backend/tests/test_knowledge_bases.py`
- Create: `backend/tests/test_knowledge_base_source_scope.py`
- Create: `backend/tests/test_embedding_provider.py`
- Create: `backend/tests/test_elasticsearch_projection.py`
- Create: `backend/tests/test_retrieval_service.py`
- Modify: existing API and worker tests where schemas gain fields.

Frontend:

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Create: `frontend/src/knowledgeBase/KnowledgeBaseContext.tsx`
- Create: `frontend/src/components/KnowledgeBaseSelector.tsx`
- Create: `frontend/src/components/KnowledgeBasePanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/CapturePanel.tsx`
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/components/SearchPanel.tsx`
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/test/workbench.test.tsx`

Docs and runtime:

- Modify: `.env.example`
- Modify: `backend/.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `docs/comet-parity-matrix.md`
- Modify: `docs/comet-parity-remaining-work.md`

---

## Task 0: Baseline Verification

**Files:**
- Read: current branch and test outputs only.
- Modify: none.

- [ ] **Step 1: Confirm branch and working tree**

Run:

```bash
git status --short --branch
```

Expected:

- Current branch is `codex/comet-parity-phase-2-knowledgebase-es-retrieval`.
- Only `.claude/` may be untracked before implementation begins.

- [ ] **Step 2: Run backend baseline**

Run:

```bash
cd backend && uv run pytest
```

Expected:

- Existing suite passes before Phase 2 implementation changes.
- If this fails, stop and diagnose before touching implementation files.

- [ ] **Step 3: Run frontend baseline**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected:

- Vitest suite passes.
- Vite production build passes.

- [ ] **Step 4: Commit**

No commit for Task 0 because it changes no files.

---

## Task 1: KnowledgeBase Models and Migration

**Files:**
- Modify: `backend/service/models.py`
- Create: `backend/alembic/versions/20260629_0003_knowledgebase_es_retrieval.py`
- Create: `backend/tests/test_knowledge_bases.py`
- Create: `backend/tests/test_knowledge_base_source_scope.py`

- [ ] **Step 1: Write failing model and migration tests**

Create `backend/tests/test_knowledge_bases.py` with these tests:

```python
from service.models import KnowledgeBase
from service.repositories.knowledge_bases import KnowledgeBaseRepository


def test_default_knowledge_base_exists_for_bootstrap_user(client):
    response = client.get("/api/knowledge-bases")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "默认知识库"
    assert rows[0]["is_default"] is True
    assert rows[0]["status"] == "active"


def test_user_cannot_see_other_users_knowledge_bases(client, auth_headers):
    other_headers = auth_headers("phase2-other@example.com")
    created = client.post(
        "/api/knowledge-bases",
        json={"name": "另一个用户的知识库", "description": "private"},
        headers=other_headers,
    )
    assert created.status_code == 200

    mine = client.get("/api/knowledge-bases")
    assert mine.status_code == 200
    assert all(row["name"] != "另一个用户的知识库" for row in mine.json())


def test_default_knowledge_base_is_created_by_repository(client):
    from service.db import SessionLocal
    from service.auth import get_user_by_email

    with SessionLocal() as db:
        user = get_user_by_email(db, "admin@example.com")
        assert user is not None
        repo = KnowledgeBaseRepository(db, user_id=user.id)
        default = repo.default()
        assert isinstance(default, KnowledgeBase)
        assert default.name == "默认知识库"
        assert default.is_default is True
```

Create `backend/tests/test_knowledge_base_source_scope.py` with this initial failing test:

```python
def test_sources_are_assigned_to_default_knowledge_base(client):
    source = client.post(
        "/api/sources",
        json={"title": "Phase 2 note", "source_type": "note", "content": "知识库归属测试"},
    )
    assert source.status_code == 200
    body = source.json()
    assert body["knowledge_base_id"] is not None
    assert body["knowledge_base_name"] == "默认知识库"

    listed = client.get("/api/sources")
    assert listed.status_code == 200
    assert listed.json()[0]["knowledge_base_id"] == body["knowledge_base_id"]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_knowledge_bases.py tests/test_knowledge_base_source_scope.py -q
```

Expected:

- Fails because `KnowledgeBase`, `KnowledgeBaseRepository`, `/api/knowledge-bases`, and source knowledge base fields do not exist.

- [ ] **Step 3: Add model classes and columns**

Modify `backend/service/models.py`:

- Add `KnowledgeBase` before `Source`.
- Add `IndexingRun` after `IngestionJob` or near source indexing models.
- Add `knowledge_base_id` to `Source`.
- Add user/knowledge-base/indexing metadata columns to `SourceChunk`.
- Add `knowledge_base_id` to `IngestionJob`.
- Add embedding capability fields to `LLMProviderProfile`.

The final model shape must include these attributes:

```python
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_knowledge_bases_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

Add `Source.knowledge_base_id`:

```python
knowledge_base_id: Mapped[Optional[int]] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=True, index=True)
```

Add `SourceChunk` fields:

```python
user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
knowledge_base_id: Mapped[Optional[int]] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=True, index=True)
content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
embedding_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
embedding_provider_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("llm_provider_profiles.id"), nullable=True)
embedding_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
embedding_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
embedded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
index_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
index_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

Add `IndexingRun`:

```python
class IndexingRun(Base):
    __tablename__ = "indexing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    knowledge_base_id: Mapped[Optional[int]] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=True, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False, index=True)
    embedding_provider_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("llm_provider_profiles.id"), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunks_embedded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 4: Add idempotent Alembic migration**

Create `backend/alembic/versions/20260629_0003_knowledgebase_es_retrieval.py`.

The migration must:

- Create `knowledge_bases` if missing.
- Add `sources.knowledge_base_id` if missing.
- Add `ingestion_jobs.knowledge_base_id` if missing.
- Add new `source_chunks` metadata columns if missing.
- Add provider capability columns if missing.
- Create `indexing_runs` if missing.
- Create default knowledge base rows for existing users.
- Backfill `sources.knowledge_base_id`, `ingestion_jobs.knowledge_base_id`, and chunk user/knowledge base columns from their source/job.

Use helper functions matching the Phase 1 migration style:

```python
def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
```

Use SQL updates for backfill:

```sql
UPDATE sources
SET knowledge_base_id = (
  SELECT kb.id FROM knowledge_bases kb
  WHERE kb.user_id = sources.user_id AND kb.is_default = 1
  ORDER BY kb.id ASC LIMIT 1
)
WHERE knowledge_base_id IS NULL
```

For SQLite compatibility, keep partial unique default enforcement in repository logic instead of adding a database partial index.

- [ ] **Step 5: Run migration verification**

Run:

```bash
cd backend && LUMEN_DATABASE_URL=sqlite:////private/tmp/lumen-phase2-alembic-kb.db uv run alembic -c alembic.ini upgrade head
```

Expected:

- Runs through `20260629_0003` without table/column duplication errors.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/service/models.py backend/alembic/versions/20260629_0003_knowledgebase_es_retrieval.py backend/tests/test_knowledge_bases.py backend/tests/test_knowledge_base_source_scope.py
git commit -m "feat: add knowledge base storage model"
```

---

## Task 2: KnowledgeBase Repository and API

**Files:**
- Create: `backend/service/repositories/knowledge_bases.py`
- Create: `backend/service/api/knowledge_bases.py`
- Modify: `backend/service/api/router.py`
- Modify: `backend/service/schemas.py`
- Modify: `backend/tests/test_knowledge_bases.py`

- [ ] **Step 1: Extend failing API tests**

Add these tests to `backend/tests/test_knowledge_bases.py`:

```python
def test_create_rename_archive_restore_and_delete_empty_knowledge_base(client):
    created = client.post("/api/knowledge-bases", json={"name": "项目资料", "description": "Phase 2"})
    assert created.status_code == 200
    kb_id = created.json()["id"]

    renamed = client.patch(f"/api/knowledge-bases/{kb_id}", json={"name": "项目资料归档", "description": "renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "项目资料归档"

    archived = client.post(f"/api/knowledge-bases/{kb_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    restored = client.post(f"/api/knowledge-bases/{kb_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    deleted = client.delete(f"/api/knowledge-bases/{kb_id}")
    assert deleted.status_code == 204


def test_cannot_delete_non_empty_knowledge_base(client):
    kb = client.post("/api/knowledge-bases", json={"name": "非空知识库"}).json()
    source = client.post(
        "/api/sources",
        json={
            "title": "非空资料",
            "source_type": "note",
            "content": "不能删除非空知识库",
            "knowledge_base_id": kb["id"],
        },
    )
    assert source.status_code == 200

    deleted = client.delete(f"/api/knowledge-bases/{kb['id']}")
    assert deleted.status_code == 400
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_knowledge_bases.py -q
```

Expected:

- Fails because API/repository/schema do not exist yet.

- [ ] **Step 3: Add schemas**

Modify `backend/service/schemas.py`:

```python
KnowledgeBaseStatus = Literal["active", "archived"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    status: KnowledgeBaseStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime
```

Also extend `SourceCreate`:

```python
knowledge_base_id: int | None = None
```

Extend `SourceRead`:

```python
knowledge_base_id: int | None
knowledge_base_name: str | None = None
```

- [ ] **Step 4: Add repository**

Create `backend/service/repositories/knowledge_bases.py` with:

- `ensure_default()`
- `default()`
- `list()`
- `get(kb_id)`
- `create(data)`
- `update(kb_id, data)`
- `archive(kb_id)`
- `restore(kb_id)`
- `delete_empty(kb_id)`
- `require_active(kb_id | None)`

Repository rules:

- All queries filter `KnowledgeBase.user_id == self.user_id` when user_id is set.
- `default()` creates default if missing.
- `require_active(None)` returns default.
- Duplicate name raises `ValueError("knowledge base name already exists")`.
- Archiving default raises `ValueError("default knowledge base cannot be archived")`.
- Deleting default raises `ValueError("default knowledge base cannot be deleted")`.
- Deleting non-empty knowledge base raises `ValueError("knowledge base is not empty")`.

- [ ] **Step 5: Add API router**

Create `backend/service/api/knowledge_bases.py`:

- Use `get_current_user`.
- Map `ValueError` to `400` for invalid operations and `404` for missing records.
- Register router in `backend/service/api/router.py`.

- [ ] **Step 6: Run tests**

Run:

```bash
cd backend && uv run pytest tests/test_knowledge_bases.py -q
```

Expected:

- All knowledge base API tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/service/repositories/knowledge_bases.py backend/service/api/knowledge_bases.py backend/service/api/router.py backend/service/schemas.py backend/tests/test_knowledge_bases.py
git commit -m "feat: add knowledge base api"
```

---

## Task 3: Scope Sources and Ingestion by KnowledgeBase

**Files:**
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/repositories/chunks.py`
- Modify: `backend/service/repositories/ingestion_jobs.py`
- Modify: `backend/service/api/sources.py`
- Modify: `backend/service/api/ingestion_jobs.py`
- Modify: `backend/service/core/ingestion.py`
- Modify: `backend/service/worker.py`
- Modify: `backend/tests/test_knowledge_base_source_scope.py`
- Modify: existing ingestion tests if response bodies add knowledge base fields.

- [ ] **Step 1: Add failing source and ingestion scope tests**

Extend `backend/tests/test_knowledge_base_source_scope.py`:

```python
def test_source_list_filters_by_knowledge_base(client):
    kb_a = client.post("/api/knowledge-bases", json={"name": "A"}).json()
    kb_b = client.post("/api/knowledge-bases", json={"name": "B"}).json()
    client.post("/api/sources", json={"title": "A note", "source_type": "note", "content": "alpha", "knowledge_base_id": kb_a["id"]})
    client.post("/api/sources", json={"title": "B note", "source_type": "note", "content": "beta", "knowledge_base_id": kb_b["id"]})

    a_rows = client.get(f"/api/sources?knowledge_base_id={kb_a['id']}").json()
    b_rows = client.get(f"/api/sources?knowledge_base_id={kb_b['id']}").json()

    assert [row["title"] for row in a_rows] == ["A note"]
    assert [row["title"] for row in b_rows] == ["B note"]


def test_ingestion_note_payload_keeps_knowledge_base_scope(client):
    kb = client.post("/api/knowledge-bases", json={"name": "队列知识库"}).json()
    response = client.post(
        "/api/ingestion-jobs/notes",
        json={"title": "queued", "source_type": "note", "content": "queued content", "knowledge_base_id": kb["id"]},
    )
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        body = response.json()
        assert body["sources"][0]["knowledge_base_id"] == kb["id"]
        assert body["jobs"][0]["knowledge_base_id"] == kb["id"]
```

- [ ] **Step 2: Run failing scope tests**

Run:

```bash
cd backend && uv run pytest tests/test_knowledge_base_source_scope.py -q
```

Expected:

- Fails until repositories and response schemas handle knowledge base scope.

- [ ] **Step 3: Update repositories**

`SourceRepository` constructor becomes:

```python
def __init__(self, db: Session, user_id: int | None = None, knowledge_base_id: int | None = None):
    self.db = db
    self.user_id = user_id
    self.knowledge_base_id = knowledge_base_id
```

Repository behavior:

- `create()` uses `data.knowledge_base_id` if provided, otherwise `self.knowledge_base_id`.
- `list()` filters `Source.knowledge_base_id == self.knowledge_base_id` when set.
- `get()` filters both user and knowledge base when `self.knowledge_base_id` is set.
- `status_counts()` and `failed_sources()` accept existing scope.

`ChunkRepository`:

- Constructor gains `knowledge_base_id`.
- `replace_for_source()` copies `user_id` and `knowledge_base_id` from source onto each chunk.
- `list_all()` filters by source or chunk knowledge base scope.
- `count_for_source()` keeps ownership check.

`IngestionJobRepository`:

- Constructor gains `knowledge_base_id`.
- `create()` stores `knowledge_base_id`.
- list/get methods can filter by knowledge base when provided.

- [ ] **Step 4: Update APIs**

In `backend/service/api/sources.py`:

- Add `knowledge_base_id: int | None = None` query/body support.
- Use `KnowledgeBaseRepository(db, current_user.id).require_active(knowledge_base_id)` before creating/listing.
- Build `SourceRead` through a helper that includes `knowledge_base_name`.

In `backend/service/api/ingestion_jobs.py`:

- Store `knowledge_base_id` in source create and job create.
- Include `knowledge_base_id` in payload JSON.
- Extend `_job_read` to return `knowledge_base_id`.

In `backend/service/schemas.py`, extend `IngestionJobRead`:

```python
knowledge_base_id: int | None = None
```

- [ ] **Step 5: Update worker and ingestion service**

In `worker.run_ingestion_job()`:

- Build scoped repositories with `knowledge_base_id=job.knowledge_base_id`.
- Pass job knowledge base scope to `IngestionService`.

In `IngestionService.__init__()`:

- Accept repositories already scoped by knowledge base.
- Ensure `index_existing_source()` never indexes a source outside those scoped repos.

- [ ] **Step 6: Run source and ingestion tests**

Run:

```bash
cd backend && uv run pytest tests/test_knowledge_base_source_scope.py tests/test_ingestion_jobs_api.py tests/test_ingestion_worker.py -q
```

Expected:

- Knowledge base scope tests pass.
- Existing ingestion tests pass with updated response schemas.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/service/repositories/sources.py backend/service/repositories/chunks.py backend/service/repositories/ingestion_jobs.py backend/service/api/sources.py backend/service/api/ingestion_jobs.py backend/service/core/ingestion.py backend/service/worker.py backend/service/schemas.py backend/tests/test_knowledge_base_source_scope.py backend/tests/test_ingestion_jobs_api.py backend/tests/test_ingestion_worker.py
git commit -m "feat: scope ingestion by knowledge base"
```

---

## Task 4: Embedding Capabilities and Provider

**Files:**
- Modify: `backend/service/config.py`
- Modify: `backend/service/core/embeddings.py`
- Modify: `backend/service/repositories/provider_profiles.py`
- Modify: `backend/service/api/settings.py`
- Modify: `backend/service/schemas.py`
- Create: `backend/tests/test_embedding_provider.py`
- Modify: settings/provider profile tests.

- [ ] **Step 1: Write failing embedding provider tests**

Create `backend/tests/test_embedding_provider.py`:

```python
import httpx

from service.core.embeddings import OpenAICompatibleEmbeddingProvider


def test_openai_compatible_embedding_provider_batches_inputs():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = request.json()
        assert payload == {"model": "text-embedding-3-small", "input": ["alpha", "beta"]}
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [1.0, 0.0, 0.0]},
                    {"embedding": [0.0, 1.0, 0.0]},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test/v1",
        model="text-embedding-3-small",
        api_key="test-key",
        dimensions=3,
        client=client,
    )

    assert provider.embed_many(["alpha", "beta"]) == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert len(requests) == 1


def test_embedding_provider_rejects_dimension_mismatch():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.test/v1",
        model="text-embedding-3-small",
        api_key="test-key",
        dimensions=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.embed_many(["alpha"])
    except ValueError as exc:
        assert "dimension" in str(exc).lower()
    else:
        raise AssertionError("expected dimension mismatch")
```

- [ ] **Step 2: Add failing settings API test**

Extend settings tests with:

```python
def test_provider_profile_supports_embedding_configuration(client):
    response = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Embedding profile",
            "provider": "openai-compatible",
            "base_url": "https://example.test/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret",
            "supports_chat": True,
            "supports_embedding": True,
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
            "timeout_seconds": 30,
            "fallback_enabled": True,
            "is_active": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["supports_embedding"] is True
    assert body["embedding_model"] == "text-embedding-3-small"
    assert body["embedding_dimensions"] == 1536
    assert body["embedding_status"] == "untested"
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_embedding_provider.py tests/test_settings.py -q
```

Expected:

- Fails because provider and schema fields are missing.

- [ ] **Step 4: Extend settings and schemas**

Add config:

```python
embedding_dimensions: int = 1536
embedding_batch_size: int = 32
retrieval_backend: str = "auto"
retrieval_bm25_weight: float = 1.0
retrieval_vector_weight: float = 1.0
elasticsearch_index: str = "lumen_source_chunks"
```

Extend provider profile schemas with:

```python
supports_chat: bool = True
supports_embedding: bool = False
embedding_model: str | None = Field(default=None, max_length=200)
embedding_dimensions: int | None = Field(default=None, ge=1, le=8192)
```

Extend read schema:

```python
supports_chat: bool
supports_embedding: bool
embedding_model: str | None
embedding_dimensions: int | None
embedding_status: ProviderProfileStatus
embedding_last_error: str | None
embedding_last_checked_at: datetime | None
```

- [ ] **Step 5: Implement embedding provider**

Modify `backend/service/core/embeddings.py`:

- Keep `HashEmbeddingProvider.embed(text)` for local fallback.
- Add `HashEmbeddingProvider.embed_many(texts)`.
- Add `OpenAICompatibleEmbeddingProvider.embed_many(texts)`.
- Add `EmbeddingProviderConfig`.
- Add `build_embedding_provider(settings, active_profile)`.

The HTTP provider must:

- POST to normalized `base_url + "/embeddings"`.
- Accept base URLs with or without trailing slash.
- Validate returned vector count equals input count.
- Validate each vector length equals configured dimensions.
- Raise `ValueError` with a sanitized message on provider errors.

- [ ] **Step 6: Update provider repository and settings API**

`ProviderProfileRepository.create/update()` must persist the new fields and continue encrypting `api_key`.

`settings.py`:

- `_read_profile()` returns embedding fields.
- Add `POST /api/settings/provider-profiles/{profile_id}/test-embedding`.
- The test endpoint decrypts api key, builds `OpenAICompatibleEmbeddingProvider`, embeds `["Lumen embedding smoke"]`, and writes `embedding_status`.

- [ ] **Step 7: Run tests**

Run:

```bash
cd backend && uv run pytest tests/test_embedding_provider.py tests/test_settings.py -q
```

Expected:

- Embedding provider tests pass.
- Settings tests pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/service/config.py backend/service/core/embeddings.py backend/service/repositories/provider_profiles.py backend/service/api/settings.py backend/service/schemas.py backend/tests/test_embedding_provider.py backend/tests/test_settings.py
git commit -m "feat: add embedding provider configuration"
```

---

## Task 5: IndexingRun and Chunk Indexing Metadata

**Files:**
- Modify: `backend/service/repositories/chunks.py`
- Create: `backend/service/repositories/indexing_runs.py`
- Modify: `backend/service/core/knowledge.py`
- Modify: `backend/service/core/ingestion.py`
- Modify: `backend/service/worker.py`
- Create: `backend/tests/test_indexing_runs.py`
- Modify: `backend/tests/test_sources.py`
- Modify: `backend/tests/test_ingestion_worker.py`

- [ ] **Step 1: Write failing indexing metadata tests**

Create `backend/tests/test_indexing_runs.py`:

```python
from service.db import SessionLocal
from service.repositories.indexing_runs import IndexingRunRepository


def test_indexing_run_records_chunk_progress(client):
    source = client.post(
        "/api/sources",
        json={"title": "Index run", "source_type": "note", "content": "第一段。\n\n第二段。"},
    ).json()
    indexed = client.post(f"/api/sources/{source['id']}/index")
    assert indexed.status_code == 200

    with SessionLocal() as db:
        runs = IndexingRunRepository(db, user_id=1).list_for_source(source["id"])
        assert len(runs) >= 1
        latest = runs[-1]
        assert latest.status == "succeeded"
        assert latest.chunks_total >= 1
        assert latest.chunks_embedded >= 1
```

Extend chunk tests to assert:

```python
assert chunk.user_id == source.user_id
assert chunk.knowledge_base_id == source.knowledge_base_id
assert chunk.content_hash
assert chunk.embedding_status in ("embedded", "skipped")
assert chunk.index_status in ("indexed", "skipped")
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_indexing_runs.py tests/test_sources.py tests/test_ingestion_worker.py -q
```

Expected:

- Fails because indexing run repository and chunk metadata writes do not exist.

- [ ] **Step 3: Add indexing run repository**

Create `backend/service/repositories/indexing_runs.py` with:

- `create(run_type, source_id, knowledge_base_id, job_id, embedding_provider_profile_id, embedding_model, embedding_dimensions)`
- `mark_running(run_id)`
- `update_progress(run_id, chunks_total, chunks_embedded, chunks_indexed)`
- `mark_succeeded(run_id)`
- `mark_failed(run_id, error_message)`
- `list_for_source(source_id)`

All reads filter by `user_id` when set.

- [ ] **Step 4: Update ChunkRepository**

Change `replace_for_source()` signature:

```python
def replace_for_source(
    self,
    source_id: int,
    chunks: list[tuple[str, str]],
    *,
    embedding_status: str,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    index_status: str,
) -> list[SourceChunk]:
```

Inside it:

- Load source through scoped query.
- Compute `content_hash = sha256(text.encode("utf-8")).hexdigest()`.
- Set `token_count = max(1, len(text) // 4)` for first approximation.
- Set chunk user and knowledge base from source.
- Keep citation cleanup behavior when replacing chunks.

- [ ] **Step 5: Update KnowledgeService indexing**

`KnowledgeService.index_source()` must:

- Create an `IndexingRun`.
- Mark source parsing.
- Chunk content.
- Use local hash embedding for fallback path.
- Write chunk metadata with `embedding_status="skipped"` and `index_status="skipped"` until ES projection task wires real indexing.
- Mark run succeeded with counts.
- Mark source indexed.

This keeps existing local behavior passing while preparing metadata.

- [ ] **Step 6: Update worker progress**

Worker should:

- Keep job progress messages.
- Allow `KnowledgeService.index_source()` to create/update indexing run.
- Propagate failures to `IndexingRunRepository.mark_failed()`.

- [ ] **Step 7: Run tests**

Run:

```bash
cd backend && uv run pytest tests/test_indexing_runs.py tests/test_sources.py tests/test_ingestion_worker.py -q
```

Expected:

- Indexing run and existing source/worker tests pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/service/repositories/chunks.py backend/service/repositories/indexing_runs.py backend/service/core/knowledge.py backend/service/core/ingestion.py backend/service/worker.py backend/tests/test_indexing_runs.py backend/tests/test_sources.py backend/tests/test_ingestion_worker.py
git commit -m "feat: track chunk indexing runs"
```

---

## Task 6: Elasticsearch Projection Service

**Files:**
- Create: `backend/service/core/elasticsearch_projection.py`
- Modify: `backend/service/config.py`
- Modify: `backend/service/repositories/chunks.py`
- Create: `backend/tests/test_elasticsearch_projection.py`

- [ ] **Step 1: Write fake-client projection tests**

Create `backend/tests/test_elasticsearch_projection.py`:

```python
from service.core.elasticsearch_projection import ElasticsearchProjection, SourceChunkDocument


class FakeElasticsearchClient:
    def __init__(self):
        self.calls = []

    def put(self, path, json=None):
        self.calls.append(("PUT", path, json))
        return {"acknowledged": True}

    def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        return {"hits": {"hits": []}}

    def delete(self, path, json=None):
        self.calls.append(("DELETE", path, json))
        return {"acknowledged": True}


def test_projection_ensure_index_creates_dense_vector_mapping():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="lumen_source_chunks", dimensions=3)
    projection.ensure_index()
    method, path, payload = client.calls[0]
    assert method == "PUT"
    assert path == "/lumen_source_chunks"
    assert payload["mappings"]["properties"]["embedding"]["dims"] == 3


def test_projection_indexes_chunk_document():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="lumen_source_chunks", dimensions=3)
    projection.index_chunk(
        SourceChunkDocument(
            user_id=1,
            knowledge_base_id=2,
            source_id=3,
            chunk_id=4,
            source_title="Title",
            source_type="note",
            text="body",
            content_hash="abc",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=3,
            embedding=[1.0, 0.0, 0.0],
        )
    )
    method, path, payload = client.calls[0]
    assert method == "PUT"
    assert path == "/lumen_source_chunks/_doc/source_chunk:4"
    assert payload["user_id"] == 1
    assert payload["knowledge_base_id"] == 2
    assert payload["embedding"] == [1.0, 0.0, 0.0]
```

- [ ] **Step 2: Run failing projection tests**

Run:

```bash
cd backend && uv run pytest tests/test_elasticsearch_projection.py -q
```

Expected:

- Fails because projection service does not exist.

- [ ] **Step 3: Implement HTTP client wrapper and projection**

`backend/service/core/elasticsearch_projection.py` must include:

- `ElasticsearchHttpClient`
- `SourceChunkDocument`
- `ElasticsearchProjection`
- `ElasticsearchProjectionError`

Use `httpx.Client` internally. Public methods:

- `ensure_index()`
- `index_chunk(document)`
- `delete_source(user_id, knowledge_base_id, source_id)`
- `search_bm25(query, user_id, knowledge_base_id, limit)`
- `search_vector(vector, user_id, knowledge_base_id, limit)`

BM25 query body:

```python
{
    "size": limit,
    "query": {
        "bool": {
            "filter": [
                {"term": {"user_id": user_id}},
                {"term": {"knowledge_base_id": knowledge_base_id}},
            ],
            "must": [{"multi_match": {"query": query, "fields": ["source_title^2", "text"]}}],
        }
    },
}
```

Vector query body for ES 8 kNN:

```python
{
    "knn": {
        "field": "embedding",
        "query_vector": vector,
        "k": limit,
        "num_candidates": max(limit * 5, 50),
        "filter": [
            {"term": {"user_id": user_id}},
            {"term": {"knowledge_base_id": knowledge_base_id}},
        ],
    },
    "size": limit,
}
```

- [ ] **Step 4: Add rebuild service entry point**

In the projection module, add:

```python
def rebuild_source_chunks(chunks: list[SourceChunk], projection: ElasticsearchProjection) -> int:
    projection.ensure_index()
    count = 0
    for chunk in chunks:
        if chunk.embedding_status == "embedded" and chunk.embedding_json:
            projection.index_chunk(SourceChunkDocument.from_chunk(chunk))
            count += 1
    return count
```

`SourceChunkDocument.from_chunk()` must read source metadata from relationship-loaded chunk.

- [ ] **Step 5: Run projection tests**

Run:

```bash
cd backend && uv run pytest tests/test_elasticsearch_projection.py -q
```

Expected:

- Projection unit tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/service/core/elasticsearch_projection.py backend/service/config.py backend/service/repositories/chunks.py backend/tests/test_elasticsearch_projection.py
git commit -m "feat: add elasticsearch source chunk projection"
```

---

## Task 7: Retrieval Service with Hybrid ES and Fallback

**Files:**
- Create: `backend/service/core/retrieval.py`
- Modify: `backend/service/core/knowledge.py`
- Modify: `backend/service/repositories/chunks.py`
- Modify: `backend/service/repositories/agent.py`
- Create: `backend/tests/test_retrieval_service.py`

- [ ] **Step 1: Write retrieval service tests**

Create `backend/tests/test_retrieval_service.py`:

```python
from service.core.retrieval import RetrievalService, RetrievalHit


class FakeHybridBackend:
    def search_bm25(self, query, user_id, knowledge_base_id, limit):
        return [RetrievalHit(chunk_id=1, score=10.0, rank=1, channel="bm25")]

    def search_vector(self, vector, user_id, knowledge_base_id, limit):
        return [RetrievalHit(chunk_id=1, score=0.9, rank=2, channel="vector"), RetrievalHit(chunk_id=2, score=0.8, rank=1, channel="vector")]


def test_hybrid_retrieval_fuses_bm25_and_vector(client):
    kb = client.get("/api/knowledge-bases").json()[0]
    first = client.post("/api/sources", json={"title": "Alpha", "source_type": "note", "content": "Lumen hybrid search alpha"}).json()
    second = client.post("/api/sources", json={"title": "Beta", "source_type": "note", "content": "Lumen vector search beta"}).json()
    client.post(f"/api/sources/{first['id']}/index")
    client.post(f"/api/sources/{second['id']}/index")

    service = RetrievalService.for_test(client_backend=FakeHybridBackend())
    results = service.search(query="Lumen search", user_id=1, knowledge_base_id=kb["id"], limit=5)
    assert [result.id for result in results][:2] == [1, 2]
    assert results[0].retrieval_mode == "es_hybrid"
    assert results[0].retrieval_source == "elasticsearch"


def test_auto_retrieval_falls_back_to_local_when_es_fails(client):
    source = client.post("/api/sources", json={"title": "Fallback", "source_type": "note", "content": "fallback keyword"}).json()
    client.post(f"/api/sources/{source['id']}/index")
    response = client.get("/api/search?q=fallback")
    assert response.status_code == 200
    assert response.json()[0]["retrieval_source"] in ("local_fallback", "local")
```

Adjust the fake backend construction to fit the final `RetrievalService` constructor. Keep the assertions intact.

- [ ] **Step 2: Run failing retrieval tests**

Run:

```bash
cd backend && uv run pytest tests/test_retrieval_service.py -q
```

Expected:

- Fails because retrieval service and schema fields do not exist.

- [ ] **Step 3: Extend `ChunkRead` and `CitationRead`**

In `backend/service/schemas.py`:

```python
RetrievalMode = Literal["local", "es_bm25", "es_vector", "es_hybrid"]
RetrievalSource = Literal["elasticsearch", "local", "local_fallback"]
```

Add to `ChunkRead` and `CitationRead`:

```python
retrieval_mode: RetrievalMode = "local"
retrieval_source: RetrievalSource = "local"
```

- [ ] **Step 4: Implement retrieval service**

Create `backend/service/core/retrieval.py` with:

- `RetrievalHit`
- `RetrievalScope`
- `RetrievalService`
- `rrf_fuse(bm25_hits, vector_hits, k, bm25_weight, vector_weight)`

Constructor dependencies:

- `sources`
- `chunks`
- `local_knowledge`
- `embedding_provider`
- `projection`
- `reranker_repository`
- `settings`

Behavior:

- `backend == "local"` uses local knowledge service.
- `backend == "auto"` tries ES; on failure calls local knowledge service and sets `retrieval_source="local_fallback"`.
- `backend == "elasticsearch"` raises on ES or embedding failure.
- All ES chunk ids are reloaded from PostgreSQL through scoped `ChunkRepository`.
- Missing or cross-scope chunk ids are ignored.

- [ ] **Step 5: Connect reranker profile**

Use existing `RerankerProfile` settings as an optional post-processing hook:

- If active profile has no `base_url`, skip rerank.
- If rerank fails in auto mode, keep hybrid order and append a fallback reason to logs or match reason.
- Do not send any candidate outside the scoped retrieval result set.

Implement the hook behind a small method so tests can use a fake reranker later.

- [ ] **Step 6: Run retrieval tests**

Run:

```bash
cd backend && uv run pytest tests/test_retrieval_service.py tests/test_search.py tests/test_chat.py -q
```

Expected:

- Retrieval tests pass.
- Existing search/chat tests pass after schema defaults.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/service/core/retrieval.py backend/service/core/knowledge.py backend/service/repositories/chunks.py backend/service/repositories/agent.py backend/service/schemas.py backend/tests/test_retrieval_service.py backend/tests/test_search.py backend/tests/test_chat.py
git commit -m "feat: add hybrid retrieval service"
```

---

## Task 8: Switch Search, Chat, and Stream Chat to Retrieval

**Files:**
- Modify: `backend/service/api/search.py`
- Modify: `backend/service/api/chat.py`
- Modify: `backend/service/core/chat.py`
- Modify: `backend/service/api/global_search.py`
- Modify: `backend/tests/test_search.py`
- Modify: `backend/tests/test_chat.py`
- Modify: `backend/tests/test_global_search.py`

- [ ] **Step 1: Write API-level knowledge base retrieval tests**

Add tests:

```python
def test_search_uses_requested_knowledge_base(client):
    kb_a = client.post("/api/knowledge-bases", json={"name": "Search A"}).json()
    kb_b = client.post("/api/knowledge-bases", json={"name": "Search B"}).json()
    source_a = client.post("/api/sources", json={"title": "A", "source_type": "note", "content": "shared needle alpha", "knowledge_base_id": kb_a["id"]}).json()
    source_b = client.post("/api/sources", json={"title": "B", "source_type": "note", "content": "shared needle beta", "knowledge_base_id": kb_b["id"]}).json()
    client.post(f"/api/sources/{source_a['id']}/index")
    client.post(f"/api/sources/{source_b['id']}/index")

    results = client.get(f"/api/search?q=needle&knowledge_base_id={kb_a['id']}").json()
    assert results
    assert all(row["source_title"] == "A" for row in results)


def test_chat_uses_requested_knowledge_base_for_citations(client):
    kb = client.post("/api/knowledge-bases", json={"name": "Chat KB"}).json()
    source = client.post("/api/sources", json={"title": "Chat Source", "source_type": "note", "content": "Lumen citation scope", "knowledge_base_id": kb["id"]}).json()
    client.post(f"/api/sources/{source['id']}/index")

    response = client.post("/api/chat", json={"message": "Lumen citation", "knowledge_base_id": kb["id"]})
    assert response.status_code == 200
    assert response.json()["citations"][0]["source_title"] == "Chat Source"
```

- [ ] **Step 2: Run failing API tests**

Run:

```bash
cd backend && uv run pytest tests/test_search.py tests/test_chat.py -q
```

Expected:

- Fails until APIs pass knowledge base scope into retrieval.

- [ ] **Step 3: Update `ChatRequest`**

In `backend/service/schemas.py`:

```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: int | None = None
    knowledge_base_id: int | None = None
```

- [ ] **Step 4: Build retrieval service in API dependencies**

Create helper functions in API modules or a small dependency module:

```python
def build_retrieval_service(db: Session, settings: Settings, user_id: int, knowledge_base_id: int | None) -> RetrievalService:
    kb = KnowledgeBaseRepository(db, user_id=user_id).require_active(knowledge_base_id)
    sources = SourceRepository(db, user_id=user_id, knowledge_base_id=kb.id)
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=kb.id)
    return RetrievalService.from_runtime(db=db, settings=settings, user_id=user_id, knowledge_base_id=kb.id, sources=sources, chunks=chunks)
```

Use this in:

- `GET /api/search`
- `POST /api/chat`
- `POST /api/chat/stream`

- [ ] **Step 5: Update ChatOrchestrator**

`ChatOrchestrator` should accept a retrieval interface instead of `KnowledgeService`:

```python
class ChatOrchestrator:
    def __init__(self, conversations, retrieval, memories, answer_provider=None):
        self.retrieval = retrieval
```

In `_prepare()`:

```python
chunks = self.retrieval.search(request.message, limit=4, knowledge_base_id=request.knowledge_base_id)
```

Keep final citation creation unchanged except include retrieval fields in `CitationRead`.

- [ ] **Step 6: Update global search source chunk path**

`GlobalSearchService` may keep source/memory/message local ranking, but source chunk candidates should call retrieval service for the query and convert top chunks into global search rows. Preserve tag/favorite filtering after conversion.

- [ ] **Step 7: Run API tests**

Run:

```bash
cd backend && uv run pytest tests/test_search.py tests/test_chat.py tests/test_global_search.py -q
```

Expected:

- Search and chat pass.
- Stream chat uses the same retrieval path.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/service/api/search.py backend/service/api/chat.py backend/service/core/chat.py backend/service/api/global_search.py backend/service/schemas.py backend/tests/test_search.py backend/tests/test_chat.py backend/tests/test_global_search.py
git commit -m "feat: route search and chat through retrieval"
```

---

## Task 9: Frontend KnowledgeBase UI and Embedding Settings

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Create: `frontend/src/knowledgeBase/KnowledgeBaseContext.tsx`
- Create: `frontend/src/components/KnowledgeBaseSelector.tsx`
- Create: `frontend/src/components/KnowledgeBasePanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/CapturePanel.tsx`
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/components/SearchPanel.tsx`
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Add failing frontend tests**

Extend `frontend/src/test/workbench.test.tsx`:

```tsx
it('selects a knowledge base and scopes capture search and chat requests', async () => {
  const user = userEvent.setup()
  render(<App />)

  await screen.findByText('默认知识库')
  await user.click(screen.getByRole('button', { name: /知识库/ }))
  await user.click(screen.getByRole('option', { name: '项目知识库' }))

  await user.type(screen.getByLabelText('记录标题'), 'KB note')
  await user.type(screen.getByLabelText('记录内容'), '知识库前端测试')
  await user.click(screen.getByRole('button', { name: '保存并索引' }))

  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:8000/api/ingestion-jobs/notes',
    expect.objectContaining({
      body: expect.stringContaining('"knowledge_base_id":2'),
    }),
  )
})
```

Add settings test:

```tsx
it('saves embedding profile fields from settings', async () => {
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: '设置' }))
  await user.click(screen.getByLabelText('支持 embedding'))
  await user.type(screen.getByLabelText('Embedding 模型'), 'text-embedding-3-small')
  await user.clear(screen.getByLabelText('Embedding 维度'))
  await user.type(screen.getByLabelText('Embedding 维度'), '1536')
  await user.click(screen.getByRole('button', { name: '保存模型配置' }))
  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:8000/api/settings/provider-profiles',
    expect.objectContaining({
      body: expect.stringContaining('"supports_embedding":true'),
    }),
  )
})
```

Adjust selectors to match existing labels in `CapturePanel` and `SettingsPanel`.

- [ ] **Step 2: Run failing frontend tests**

Run:

```bash
cd frontend && npm test -- --run src/test/workbench.test.tsx
```

Expected:

- Fails because knowledge base UI and embedding settings fields do not exist.

- [ ] **Step 3: Add API types and client methods**

`types.ts`:

```ts
export type KnowledgeBaseRead = {
  id: number
  name: string
  description: string | null
  status: 'active' | 'archived'
  is_default: boolean
  created_at: string
  updated_at: string
}
```

Extend `SourceRead`, `IngestionJobRead`, `ChunkRead`, `ChatResponse` citation types with knowledge base and retrieval fields.

`client.ts`:

- `listKnowledgeBases`
- `createKnowledgeBase`
- `updateKnowledgeBase`
- `archiveKnowledgeBase`
- `restoreKnowledgeBase`
- `deleteKnowledgeBase`
- Include `knowledge_base_id` in source/ingestion/search/chat request payloads.

- [ ] **Step 4: Add context and selector**

Create `KnowledgeBaseContext.tsx`:

- localStorage key `lumen.activeKnowledgeBaseId`.
- Fetch knowledge bases with TanStack Query.
- Pick stored active id if active exists.
- Else pick default.
- Expose active id and active row.

Create `KnowledgeBaseSelector.tsx`:

- Use a native select or accessible menu.
- Label: `知识库`.
- Options show active knowledge bases.
- Include a compact action button to open management view.

- [ ] **Step 5: Add management panel**

Create `KnowledgeBasePanel.tsx`:

- List active and archived knowledge bases.
- Form fields: `知识库名称`, `描述`.
- Actions: create, rename, archive, restore, delete empty.
- Use existing app panel styles, no nested card layout.

Add view key `knowledge` to `AppShell` nav.

- [ ] **Step 6: Wire active knowledge base into workflows**

Update:

- `CapturePanel` sends active `knowledge_base_id`.
- `SourceList` queries current knowledge base and invalidates when active changes.
- `SearchPanel` sends active `knowledge_base_id`.
- Chat request and stream request send active `knowledge_base_id`.
- `ContextPanel` continues rendering citations unchanged, with optional retrieval mode label.

- [ ] **Step 7: Extend SettingsPanel embedding fields**

Add controls:

- checkbox `支持聊天`
- checkbox `支持 embedding`
- input `Embedding 模型`
- numeric input `Embedding 维度`
- button `测试 embedding`

Keep API key password behavior unchanged.

- [ ] **Step 8: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected:

- All Vitest tests pass.
- Build passes.

- [ ] **Step 9: Commit**

Run:

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/hooks.ts frontend/src/knowledgeBase/KnowledgeBaseContext.tsx frontend/src/components/KnowledgeBaseSelector.tsx frontend/src/components/KnowledgeBasePanel.tsx frontend/src/App.tsx frontend/src/components/AppShell.tsx frontend/src/components/CapturePanel.tsx frontend/src/components/SourceList.tsx frontend/src/components/SearchPanel.tsx frontend/src/components/SettingsPanel.tsx frontend/src/styles.css frontend/src/test/workbench.test.tsx
git commit -m "feat: add knowledge base workbench controls"
```

---

## Task 10: Retrieval Evaluation, Docs, and Final Verification

**Files:**
- Modify: `backend/service/eval/retrieval.py`
- Modify: `backend/service/eval/retrieval_cases.json`
- Modify: `.env.example`
- Modify: `backend/.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `docs/comet-parity-matrix.md`
- Modify: `docs/comet-parity-remaining-work.md`

- [ ] **Step 1: Extend retrieval eval**

Add cases in `retrieval_cases.json`:

- query that should hit only default knowledge base.
- query that should hit ES BM25 exact keyword.
- query that should hit vector semantic text.
- query that should test weak evidence fallback.

Modify `retrieval.py` so seed data creates at least two knowledge bases and records expected `knowledge_base_id` for scoped assertions.

- [ ] **Step 2: Update env and compose docs**

Add to `.env.example` and `backend/.env.example`:

```env
LUMEN_ELASTICSEARCH_INDEX=lumen_source_chunks
LUMEN_EMBEDDING_DIMENSIONS=1536
LUMEN_EMBEDDING_BATCH_SIZE=32
LUMEN_RETRIEVAL_BACKEND=auto
LUMEN_RETRIEVAL_BM25_WEIGHT=1.0
LUMEN_RETRIEVAL_VECTOR_WEIGHT=1.0
```

Ensure `docker-compose.yml` backend and worker services receive these env vars.

- [ ] **Step 3: Update README and parity docs**

README must describe:

- Knowledge base selector and management.
- Embedding profile setup.
- ES hybrid retrieval and local fallback.
- Smoke flow: login, create knowledge base, ingest, search, chat citation.

`docs/comet-parity-matrix.md`:

- Mark multi-knowledge-base as Phase 2 complete.
- Mark ES hybrid retrieval and true embedding as Phase 2 complete when tests pass.

`docs/comet-parity-remaining-work.md`:

- Move completed Phase 2 items to checked.
- Add Phase 2 verification record.
- Set next recommendation to Phase 3 image/document knowledge surfaces.

- [ ] **Step 4: Run final backend verification**

Run:

```bash
cd backend && uv run pytest
```

Expected:

- Full backend suite passes.

- [ ] **Step 5: Run final frontend verification**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected:

- Full frontend suite passes.
- Build passes.

- [ ] **Step 6: Run Alembic verification**

Run:

```bash
cd backend && LUMEN_DATABASE_URL=sqlite:////private/tmp/lumen-phase2-final-alembic.db uv run alembic -c alembic.ini upgrade head
```

Expected:

- Fresh SQLite database upgrades through `20260629_0003`.

- [ ] **Step 7: Run compose config check**

Run:

```bash
docker compose config --services
```

Expected:

- Output includes `postgres`, `redis`, `elasticsearch`, `neo4j`, `backend`, `worker`, `beat`, `frontend`.

- [ ] **Step 8: Docker smoke when daemon is available**

Run:

```bash
docker compose up --build -d
```

Expected when Docker daemon is running:

- Stack starts.
- Login works.
- Knowledge base creation works.
- Note ingestion produces indexed chunks.
- Search returns scoped source chunk results.
- Chat returns citations from the selected knowledge base.

If Docker daemon is unavailable, record the exact daemon error in `docs/comet-parity-remaining-work.md`.

- [ ] **Step 9: Commit final docs and verification updates**

Run:

```bash
git add backend/service/eval/retrieval.py backend/service/eval/retrieval_cases.json .env.example backend/.env.example docker-compose.yml README.md docs/comet-parity-matrix.md docs/comet-parity-remaining-work.md
git commit -m "docs: document phase 2 retrieval workflow"
```

---

## Final Branch Completion

- [ ] **Step 1: Check status**

Run:

```bash
git status --short --branch
```

Expected:

- Only `.claude/` may remain untracked.
- No unstaged or staged Phase 2 implementation files remain.

- [ ] **Step 2: Review commit list**

Run:

```bash
git log --oneline --decorate -12
```

Expected:

- Includes design commit plus one commit per implementation task.

- [ ] **Step 3: Push without proxy when requested**

Run:

```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy git -c credential.helper=/Library/Developer/CommandLineTools/usr/libexec/git-core/git-credential-osxkeychain -c http.proxy= -c https.proxy= -c http.https://github.com.proxy= push -u origin codex/comet-parity-phase-2-knowledgebase-es-retrieval
```

Expected:

- Branch pushes to origin.

If direct GitHub access times out again, report that branch is committed locally and push is blocked by network connectivity.

## Subagent Assignment Plan

Use subagent-driven development in this order:

1. Task 0 manually by controller.
2. Task 1 implementer subagent, then spec reviewer, then code quality reviewer.
3. Task 2 implementer subagent, then spec reviewer, then code quality reviewer.
4. Task 3 implementer subagent, then spec reviewer, then code quality reviewer.
5. Task 4 implementer subagent, then spec reviewer, then code quality reviewer.
6. Task 5 implementer subagent, then spec reviewer, then code quality reviewer.
7. Task 6 implementer subagent, then spec reviewer, then code quality reviewer.
8. Task 7 implementer subagent, then spec reviewer, then code quality reviewer.
9. Task 8 implementer subagent, then spec reviewer, then code quality reviewer.
10. Task 9 implementer subagent, then spec reviewer, then code quality reviewer.
11. Task 10 implementer subagent, then final whole-branch code review.

Each implementer prompt must include:

- The approved spec path.
- The exact task text from this plan.
- The current branch name.
- The instruction to avoid `.claude/`.
- The instruction to run only the task-specific tests first, then the specified broader tests.
- The instruction to commit only the task's scoped files.

## Plan Self-Review

- Spec coverage: tasks cover KnowledgeBase, source scope, ingestion scope, embedding profiles, OpenAI-compatible embeddings, indexing metadata, ES projection, hybrid retrieval, search/chat switching, frontend UI, eval, docs, and final verification.
- Completion scan: all planning language is concrete and ready for execution.
- Type consistency: `knowledge_base_id`, `retrieval_mode`, `retrieval_source`, `embedding_dimensions`, `embedding_status`, and `index_status` are named consistently across backend and frontend tasks.
- Testability: every implementation task starts with failing tests and includes exact commands for focused and broader verification.
