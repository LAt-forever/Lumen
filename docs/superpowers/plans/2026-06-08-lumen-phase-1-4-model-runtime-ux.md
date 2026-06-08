# Lumen Phase 1.4 Model Runtime UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLite-backed OpenAI-compatible provider profiles, safe connection diagnostics, and streaming chat while preserving Phase 1.3 evidence-grounded behavior.

**Architecture:** Add a small provider-profile persistence boundary under settings, then make LLM provider construction resolve active SQLite profile before environment settings. Add a non-breaking streaming chat endpoint and frontend streaming path with fallback to the existing non-streaming API.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, httpx, pytest, React, TypeScript, TanStack Query, Vitest.

---

## File Structure

- Modify `backend/service/models.py`: add `LLMProviderProfile`.
- Create `backend/service/repositories/provider_profiles.py`: CRUD, activation, safe status update.
- Modify `backend/service/schemas.py`: add safe provider profile request/response schemas and runtime metadata fields.
- Modify `backend/service/api/settings.py`: add provider profile endpoints, activation, delete, and connection test.
- Modify `backend/service/core/llm.py`: add runtime config resolution from DB, sanitized connection testing, and streaming client helpers.
- Modify `backend/service/core/chat.py`: add shared evidence-pack building and a streaming orchestration method.
- Modify `backend/service/api/chat.py`: wire provider profile repository into `/api/chat` and add `/api/chat/stream`.
- Modify backend tests: `backend/tests/test_settings.py`, `backend/tests/test_chat.py`.
- Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`: provider profile contracts and streaming chat client.
- Modify `frontend/src/components/SettingsPanel.tsx`: profile list, create/edit form, activation, connection test, safe key replace/clear controls.
- Modify `frontend/src/components/CapturePanel.tsx`: prefer streaming ask and fallback to non-streaming.
- Modify `frontend/src/components/ChatPanel.tsx`: show in-progress streamed answer.
- Modify `frontend/src/test/workbench.test.tsx`: provider profile and streaming flows.
- Modify `README.md`: document Phase 1.4 model profile and streaming behavior.

---

### Task 1: Backend Provider Profile Persistence

**Files:**
- Modify: `backend/service/models.py`
- Create: `backend/service/repositories/provider_profiles.py`
- Modify: `backend/service/schemas.py`
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Write failing profile persistence tests**

Add tests that create profiles, verify API keys are omitted from safe reads, preserve existing keys when update omits `api_key`, clear keys when requested, activate one profile, and reject deleting an active profile.

```python
def test_provider_profile_responses_omit_raw_api_key(client):
    created = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Local OpenAI",
            "provider": "openai-compatible",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key": "secret-key",
            "timeout_seconds": 12,
            "fallback_enabled": True,
            "is_active": True,
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["api_key_configured"] is True
    assert "api_key" not in payload
    assert "secret-key" not in created.text


def test_provider_profile_update_preserves_or_clears_key(client):
    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Primary",
            "provider": "openai-compatible",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key": "secret-key",
            "timeout_seconds": 12,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    preserved = client.patch(
        f"/api/settings/provider-profiles/{profile['id']}",
        json={"name": "Renamed", "model": "gpt-renamed"},
    ).json()
    assert preserved["api_key_configured"] is True

    cleared = client.patch(
        f"/api/settings/provider-profiles/{profile['id']}",
        json={"clear_api_key": True},
    ).json()
    assert cleared["api_key_configured"] is False
```

```python
def test_provider_profile_activation_and_active_delete_guard(client):
    first = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "First",
            "provider": "openai-compatible",
            "base_url": "https://first.test/v1",
            "model": "gpt-first",
            "api_key": "first-key",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": True,
        },
    ).json()
    second = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Second",
            "provider": "openai-compatible",
            "base_url": "https://second.test/v1",
            "model": "gpt-second",
            "api_key": "second-key",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    activated = client.post(f"/api/settings/provider-profiles/{second['id']}/activate").json()
    profiles = client.get("/api/settings/provider-profiles").json()

    assert activated["is_active"] is True
    assert {profile["id"]: profile["is_active"] for profile in profiles} == {
        first["id"]: False,
        second["id"]: True,
    }
    assert client.delete(f"/api/settings/provider-profiles/{second['id']}").status_code == 400
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_settings.py::test_provider_profile_responses_omit_raw_api_key tests/test_settings.py::test_provider_profile_update_preserves_or_clears_key tests/test_settings.py::test_provider_profile_activation_and_active_delete_guard -v`

Expected: FAIL because provider profile endpoints and model do not exist.

- [ ] **Step 3: Add `LLMProviderProfile` model**

Add this model to `backend/service/models.py`:

```python
class LLMProviderProfile(Base):
    __tablename__ = "llm_provider_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="openai-compatible", nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[float] = mapped_column(default=30.0, nullable=False)
    fallback_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="untested", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

Also import `Boolean` and `Float` from SQLAlchemy and use `mapped_column(Boolean, ...)`, `mapped_column(Float, ...)` if type inference is not enough.

- [ ] **Step 4: Add safe schemas**

Add `LLMProviderProfileCreate`, `LLMProviderProfileUpdate`, and `LLMProviderProfileRead` to `backend/service/schemas.py`. Use `api_key_configured: bool` on reads and no `api_key` read field.

- [ ] **Step 5: Add repository**

Create `backend/service/repositories/provider_profiles.py` with `create`, `list`, `get`, `active`, `update`, `activate`, `delete`, and `mark_test_result`. `create` and `activate` deactivate other profiles when the target is active.

- [ ] **Step 6: Add settings endpoints**

In `backend/service/api/settings.py`, add endpoints under `/provider-profiles`. Convert model rows to `LLMProviderProfileRead` using a helper that sets `api_key_configured=bool(profile.api_key)`.

- [ ] **Step 7: Run focused settings tests**

Run: `cd backend && uv run pytest tests/test_settings.py -v`

Expected: PASS.

---

### Task 2: Runtime Profile Resolution And Connection Test

**Files:**
- Modify: `backend/service/core/llm.py`
- Modify: `backend/service/api/chat.py`
- Modify: `backend/service/api/settings.py`
- Modify: `backend/service/schemas.py`
- Test: `backend/tests/test_settings.py`
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Write failing runtime resolution tests**

Add tests proving an active database profile overrides environment settings and no active DB profile falls back to environment settings.

```python
def test_runtime_settings_prefers_active_database_profile(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "env-model")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "env-key")

    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "DB Profile",
            "provider": "openai-compatible",
            "base_url": "https://db.test/v1",
            "model": "db-model",
            "api_key": "db-key",
            "timeout_seconds": 8,
            "fallback_enabled": False,
            "is_active": True,
        },
    ).json()

    runtime = client.get("/api/settings/runtime").json()

    assert runtime["runtime_source"] == "database-profile"
    assert runtime["active_profile_id"] == profile["id"]
    assert runtime["active_profile_name"] == "DB Profile"
    assert runtime["llm_model"] == "db-model"
    assert runtime["llm_configured"] is True
```

```python
def test_runtime_settings_uses_environment_without_active_profile(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "env-model")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "env-key")

    runtime = client.get("/api/settings/runtime").json()

    assert runtime["runtime_source"] == "environment"
    assert runtime["active_profile_id"] is None
    assert runtime["llm_model"] == "env-model"
    assert runtime["llm_configured"] is True
```

- [ ] **Step 2: Write failing connection test tests**

Use monkeypatch to replace the connection-test client path with success/failure fake behavior. Assert status changes and secret values are absent.

```python
def test_provider_profile_connection_test_marks_ready(client, monkeypatch):
    import service.api.settings as settings_api

    monkeypatch.setattr(settings_api, "_test_provider_profile", lambda profile: None)
    profile = client.post(
        "/api/settings/provider-profiles",
        json={
            "name": "Ready Profile",
            "provider": "openai-compatible",
            "base_url": "https://ready.test/v1",
            "model": "gpt-ready",
            "api_key": "ready-secret",
            "timeout_seconds": 10,
            "fallback_enabled": True,
            "is_active": False,
        },
    ).json()

    response = client.post(f"/api/settings/provider-profiles/{profile['id']}/test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["last_error"] is None
    assert "ready-secret" not in response.text
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_settings.py::test_runtime_settings_prefers_active_database_profile tests/test_settings.py::test_runtime_settings_uses_environment_without_active_profile tests/test_settings.py::test_provider_profile_connection_test_marks_ready -v`

Expected: FAIL because runtime source fields and connection test do not exist.

- [ ] **Step 4: Add runtime config object and resolver**

In `backend/service/core/llm.py`, add a dataclass:

```python
@dataclass(frozen=True)
class RuntimeLLMConfig:
    mode: str
    provider: str
    base_url: str
    model: str | None
    api_key: str | None
    timeout_seconds: float
    fallback_enabled: bool
    runtime_source: str
    active_profile_id: int | None = None
    active_profile_name: str | None = None
```

Add `resolve_runtime_llm_config(settings, profiles)` where `profiles` may be `None`; when an active profile exists, return database values and `mode="llm"`.

- [ ] **Step 5: Update provider construction**

Change `build_answer_provider(settings)` to accept an optional repository or runtime config:

```python
def build_answer_provider(settings: Settings, runtime_config: RuntimeLLMConfig | None = None) -> AnswerProvider:
    config = runtime_config or RuntimeLLMConfig(...)
```

Keep env-only behavior as default so existing tests remain valid.

- [ ] **Step 6: Update chat API**

In `backend/service/api/chat.py`, instantiate `ProviderProfileRepository(db)`, resolve runtime config, and pass it to `build_answer_provider`.

- [ ] **Step 7: Extend runtime settings response**

Add `runtime_source`, `active_profile_id`, and `active_profile_name` to `RuntimeSettingsRead`. Update `runtime_settings()` to resolve active DB profile.

- [ ] **Step 8: Add connection test endpoint**

In settings API, add `POST /api/settings/provider-profiles/{profile_id}/test`. Use `_test_provider_profile(profile)` helper. On success store `ready`; on failure store `failed` with sanitized message.

- [ ] **Step 9: Run backend settings and chat tests**

Run: `cd backend && uv run pytest tests/test_settings.py tests/test_chat.py -v`

Expected: PASS.

---

### Task 3: Backend Streaming Primitives And Endpoint

**Files:**
- Modify: `backend/service/core/llm.py`
- Modify: `backend/service/core/chat.py`
- Modify: `backend/service/api/chat.py`
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Write failing streaming parser tests**

Add a parser-level test:

```python
def test_parse_openai_streaming_lines_extracts_content():
    from service.core.llm import parse_openai_stream_lines

    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        "data: [DONE]",
    ]

    assert list(parse_openai_stream_lines(lines)) == ["你", "好"]
```

- [ ] **Step 2: Write failing streaming endpoint tests**

Use a fake provider injected through monkeypatch if needed. The test should add a source, call `/api/chat/stream`, and assert SSE contains `event: chunk` and `event: final`.

```python
def test_chat_stream_emits_chunk_and_final_events(client, monkeypatch):
    source = client.post(
        "/api/sources",
        json={"title": "Streaming Note", "source_type": "note", "content": "Streaming answers still cite evidence."},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    response = client.post("/api/chat/stream", json={"message": "What still cites evidence?"})

    assert response.status_code == 200
    text = response.text
    assert "event: chunk" in text
    assert "event: final" in text
    assert "Streaming answers still cite evidence." in text
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_chat.py::test_parse_openai_streaming_lines_extracts_content tests/test_chat.py::test_chat_stream_emits_chunk_and_final_events -v`

Expected: FAIL because parser and endpoint do not exist.

- [ ] **Step 4: Add stream parser**

In `backend/service/core/llm.py`, add `parse_openai_stream_lines(lines: Iterable[str]) -> Iterator[str]` that handles `data:` lines, `[DONE]`, and JSON chunks with `choices[0].delta.content`.

- [ ] **Step 5: Add streaming client method**

Add `ChatCompletionClient.stream(messages)` to the protocol as optional or create `StreamingChatCompletionClient`. Implement `HttpxChatCompletionClient.stream()` using `httpx.stream(...)` with `stream=True` payload.

- [ ] **Step 6: Refactor evidence building in ChatOrchestrator**

Extract existing evidence setup into `_prepare(request)` returning conversation, user message, chunks, memory rows, evidence. Keep `ask()` behavior unchanged.

- [ ] **Step 7: Add `stream()` orchestration**

Add `ChatOrchestrator.stream(request)` returning an iterator of SSE event strings. If no streaming provider capability exists or evidence is weak, emit one extractive chunk and final metadata using existing answer path.

- [ ] **Step 8: Add streaming endpoint**

In `backend/service/api/chat.py`, add:

```python
@router.post("/stream")
def chat_stream(...):
    return StreamingResponse(generator, media_type="text/event-stream")
```

- [ ] **Step 9: Run chat tests**

Run: `cd backend && uv run pytest tests/test_chat.py -v`

Expected: PASS.

---

### Task 4: Frontend Provider Profile API And Settings UI

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing frontend provider profile test**

Extend the fetch mock with `/api/settings/provider-profiles` GET/POST/PATCH/activate/test responses. Add a test that opens Settings, sees `DB Profile`, creates a new profile, activates it, and tests it. Assert `secret-key` is not visible.

```tsx
await user.click(screen.getByRole('button', { name: '设置' }))
expect(await screen.findByText('DB Profile')).toBeInTheDocument()
expect(screen.queryByText('secret-key')).not.toBeInTheDocument()
await user.type(screen.getByLabelText('配置名称'), 'New Profile')
await user.type(screen.getByLabelText('Base URL'), 'https://new.test/v1')
await user.type(screen.getByLabelText('模型名称'), 'gpt-new')
await user.type(screen.getByLabelText('API key'), 'new-secret')
await user.click(screen.getByRole('button', { name: '保存模型配置' }))
await user.click(screen.getAllByRole('button', { name: '设为当前配置' })[0])
await user.click(screen.getAllByRole('button', { name: '测试连接' })[0])
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run: `cd frontend && npm run test`

Expected: FAIL because provider profile API and UI do not exist.

- [ ] **Step 3: Add frontend types**

Add `LLMProviderProfileRead`, `LLMProviderProfileCreate`, `LLMProviderProfileUpdate` to `frontend/src/api/types.ts`.

- [ ] **Step 4: Add client methods and hooks**

Add `listProviderProfiles`, `createProviderProfile`, `updateProviderProfile`, `activateProviderProfile`, `testProviderProfile`, and `deleteProviderProfile`. Add React Query hooks that invalidate `provider-profiles` and `settings/runtime`.

- [ ] **Step 5: Build Settings UI form**

Extend `SettingsPanel` with an inline form:

- `配置名称`
- `Base URL`
- `模型名称`
- `API key`
- timeout input
- fallback checkbox
- save button

Profile cards show key configured status, active status, provider status, last error, and action buttons.

- [ ] **Step 6: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: PASS.

---

### Task 5: Frontend Streaming Chat

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Modify: `frontend/src/components/CapturePanel.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing streaming frontend test**

Mock `/api/chat/stream` as a `ReadableStream` with SSE chunk and final events. Assert the streamed text appears and final metadata is shown.

```tsx
await user.type(screen.getByLabelText('询问 Lumen'), '请流式回答')
await user.click(screen.getByRole('button', { name: '询问 Lumen' }))
expect(await screen.findByText('流式回答完成。')).toBeInTheDocument()
expect(await screen.findAllByText('LLM 模式')).toHaveLength(expect.any(Number))
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run: `cd frontend && npm run test`

Expected: FAIL because `CapturePanel` still uses non-streaming mutation only.

- [ ] **Step 3: Add streaming client**

Add `streamAsk(message, onChunk, onFinal)` to `frontend/src/api/client.ts`. Use `fetch`, `response.body.getReader()`, `TextDecoder`, and parse SSE events.

- [ ] **Step 4: Add streaming hook**

Add `useAskLumenStream()` that manages streaming state, calls `api.streamAsk`, invalidates pending memories and review on final, and falls back to `api.ask` when streaming throws.

- [ ] **Step 5: Update CapturePanel/AppShell**

Allow `CapturePanel` to call the streaming hook and publish partial response state upward. Use an interim `ChatResponse` with the growing answer text and conservative metadata until final event arrives.

- [ ] **Step 6: Update ChatPanel**

Show `正在生成...` when response is streaming. Keep existing final metadata display.

- [ ] **Step 7: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: PASS.

---

### Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document Phase 1.4:

- SQLite-backed provider profiles
- API key storage tradeoff
- connection test
- streaming chat
- environment fallback
- agent routing remains deferred

- [ ] **Step 2: Run backend tests**

Run: `cd backend && uv run pytest -v`

Expected: PASS.

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Review diff**

Run: `git status --short`, `git diff --stat`, and `git diff --check`.

Expected: clean whitespace check and only Phase 1.4 files changed.
