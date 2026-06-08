# Lumen Phase 1.2 Evidence-Grounded Answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the smallest useful provider adapter for evidence-grounded LLM answers while preserving the credential-free extractive default.

**Architecture:** Keep `ChatOrchestrator` responsible for retrieval, message persistence, citation persistence, and memory extraction. Move answer generation behind a typed provider boundary in `backend/service/core/llm.py`; the provider receives an evidence pack and returns answer metadata. Surface safe runtime model status through a read-only settings endpoint and small frontend display changes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy, httpx, pytest, React 18, TypeScript, TanStack Query, Vitest, Testing Library.

---

## File Structure

- Modify `backend/service/config.py`: add LLM settings read from `LUMEN_` environment variables.
- Modify `backend/service/schemas.py`: add answer metadata to `ChatResponse` and add `RuntimeSettingsRead`.
- Modify `backend/service/core/llm.py`: add `EvidencePack`, `EvidenceMemory`, `AnswerResult`, `AnswerProvider`, `ExtractiveAnswerProvider`, `FallbackAnswerProvider`, `ChatCompletionClient`, `HttpxChatCompletionClient`, `OpenAICompatibleAnswerProvider`, and `build_answer_provider`.
- Modify `backend/service/core/chat.py`: build an evidence pack and consume `AnswerResult`.
- Modify `backend/service/api/chat.py`: build the provider from settings.
- Create `backend/service/api/settings.py`: expose `GET /api/settings/runtime`.
- Modify `backend/service/api/router.py`: include the settings router.
- Modify `backend/tests/test_chat.py`: cover extractive metadata, LLM success, weak evidence no-LLM path, and fallback behavior.
- Create `backend/tests/test_settings.py`: cover safe runtime settings.
- Modify `frontend/src/api/types.ts`: add chat answer metadata and `RuntimeSettingsRead`.
- Modify `frontend/src/api/client.ts`: add `runtimeSettings`.
- Modify `frontend/src/api/hooks.ts`: add `useRuntimeSettings`.
- Modify `frontend/src/components/AppShell.tsx`: show runtime answer mode in the top bar.
- Modify `frontend/src/components/ChatPanel.tsx`: show answer mode metadata.
- Modify `frontend/src/components/ContextPanel.tsx`: show fallback reason when present.
- Modify `frontend/src/components/SettingsPanel.tsx`: fetch and render runtime settings.
- Modify `frontend/src/test/workbench.test.tsx`: mock runtime settings and assert LLM/fallback UI.
- Modify `README.md`: document Phase 1.2 LLM env vars and fallback behavior.

## Task 1: Backend Runtime Settings Shape

**Files:**
- Modify: `backend/service/config.py`
- Modify: `backend/service/schemas.py`
- Create: `backend/service/api/settings.py`
- Modify: `backend/service/api/router.py`
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Write failing runtime settings tests**

Create `backend/tests/test_settings.py`:

```python
from service.config import get_settings


def test_runtime_settings_omits_api_key(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.setenv("LUMEN_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LUMEN_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LUMEN_LLM_API_KEY", "secret-value")
    monkeypatch.setenv("LUMEN_LLM_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "llm_mode": "llm",
        "llm_provider": "openai-compatible",
        "llm_model": "gpt-test",
        "llm_configured": True,
        "llm_fallback_enabled": True,
        "embedding_mode": "hash",
    }
    assert "secret-value" not in response.text


def test_runtime_settings_defaults_to_extractive(client, monkeypatch):
    monkeypatch.delenv("LUMEN_LLM_MODE", raising=False)
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)
    get_settings.cache_clear()

    response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    data = response.json()
    assert data["llm_mode"] == "extractive"
    assert data["llm_provider"] == "openai-compatible"
    assert data["llm_model"] is None
    assert data["llm_configured"] is False
    assert data["llm_fallback_enabled"] is True
```

- [ ] **Step 2: Run the failing settings tests**

Run:

```bash
cd backend
uv run pytest tests/test_settings.py -v
```

Expected: fail because `/api/settings/runtime` and `RuntimeSettingsRead` do not exist.

- [ ] **Step 3: Add LLM config settings**

In `backend/service/config.py`, extend `Settings`:

```python
class Settings(BaseSettings):
    app_name: str = "Lumen"
    database_url: str = "sqlite:///./lumen.db"
    data_dir: Path = Path("./data")
    llm_mode: str = "extractive"
    llm_provider: str = "openai-compatible"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_fallback_enabled: bool = True
    embedding_mode: str = "hash"

    model_config = SettingsConfigDict(env_prefix="LUMEN_", env_file=".env", extra="ignore")
```

- [ ] **Step 4: Add runtime settings schema**

In `backend/service/schemas.py`, add:

```python
AnswerMode = Literal["extractive", "llm"]
```

Add this model near `ReviewRead`:

```python
class RuntimeSettingsRead(BaseModel):
    llm_mode: str
    llm_provider: str
    llm_model: str | None
    llm_configured: bool
    llm_fallback_enabled: bool
    embedding_mode: str
```

- [ ] **Step 5: Add settings API router**

Create `backend/service/api/settings.py`:

```python
from fastapi import APIRouter, Depends

from service.config import Settings, get_settings
from service.schemas import RuntimeSettingsRead

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/runtime", response_model=RuntimeSettingsRead)
def runtime_settings(settings: Settings = Depends(get_settings)) -> RuntimeSettingsRead:
    llm_configured = bool(settings.llm_api_key and settings.llm_model)
    return RuntimeSettingsRead(
        llm_mode=settings.llm_mode,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_configured=llm_configured,
        llm_fallback_enabled=settings.llm_fallback_enabled,
        embedding_mode=settings.embedding_mode,
    )
```

- [ ] **Step 6: Include settings router**

In `backend/service/api/router.py`, change the import to:

```python
from service.api import chat, memories, review, search, settings, sources
```

Add after the existing includes:

```python
router.include_router(settings.router)
```

- [ ] **Step 7: Verify settings tests pass**

Run:

```bash
cd backend
uv run pytest tests/test_settings.py -v
```

Expected: both settings tests pass.

## Task 2: Backend Provider Interface And Extractive Compatibility

**Files:**
- Modify: `backend/service/core/llm.py`
- Modify: `backend/service/core/chat.py`
- Modify: `backend/service/schemas.py`
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Add failing extractive metadata test**

Append to `backend/tests/test_chat.py`:

```python
def test_chat_response_includes_extractive_answer_metadata():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Lumen Mode", source_type="note", content="Lumen uses grounded evidence to answer questions.")
    )
    knowledge.index_source(source.id)

    response = chat.ask(ChatRequest(message="What does Lumen use to answer questions?"))

    assert response.confidence == "grounded"
    assert response.answer_mode == "extractive"
    assert response.fallback_reason is None
```

- [ ] **Step 2: Run the failing chat test**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_response_includes_extractive_answer_metadata -v
```

Expected: fail because `ChatResponse` lacks `answer_mode` and `fallback_reason`.

- [ ] **Step 3: Extend chat response schema**

In `backend/service/schemas.py`, update `ChatResponse`:

```python
class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    citations: list[CitationRead]
    memories: list[UsedMemoryRead]
    confidence: str
    answer_mode: AnswerMode = "extractive"
    fallback_reason: str | None = None
```

- [ ] **Step 4: Replace provider internals with typed evidence objects**

Replace `backend/service/core/llm.py` with:

```python
from dataclasses import dataclass, replace
from typing import Protocol

from service.config import Settings
from service.schemas import ChunkRead


@dataclass(frozen=True)
class EvidenceMemory:
    id: int
    text: str
    memory_type: str


@dataclass(frozen=True)
class EvidencePack:
    question: str
    chunks: list[ChunkRead]
    memories: list[EvidenceMemory]
    retrieval_confidence: str

    @property
    def has_evidence(self) -> bool:
        return bool(self.chunks or self.memories)


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    confidence: str
    answer_mode: str
    fallback_reason: str | None = None


class AnswerProvider(Protocol):
    def answer(self, evidence: EvidencePack) -> AnswerResult:
        ...


class ExtractiveAnswerProvider:
    def answer(self, evidence: EvidencePack) -> AnswerResult:
        memories = [memory.text for memory in evidence.memories]
        if evidence.chunks:
            source_bits = " ".join(chunk.text for chunk in evidence.chunks[:2])
            memory_bits = f" 已确认记忆：{' '.join(memories)}" if memories else ""
            return AnswerResult(
                answer=f"根据你的资料，{source_bits}{memory_bits}",
                confidence="grounded",
                answer_mode="extractive",
            )
        if memories:
            return AnswerResult(
                answer=f"我找到了相关的已确认记忆：{' '.join(memories)}",
                confidence="memory-only",
                answer_mode="extractive",
            )
        return AnswerResult(
            answer="Lumen 里还没有足够证据。请先添加相关资料，或确认一条相关记忆。",
            confidence="weak",
            answer_mode="extractive",
        )


class FallbackAnswerProvider:
    def __init__(self, fallback: AnswerProvider, reason: str):
        self.fallback = fallback
        self.reason = reason

    def answer(self, evidence: EvidencePack) -> AnswerResult:
        result = self.fallback.answer(evidence)
        return replace(result, fallback_reason=self.reason)


def build_answer_provider(settings: Settings) -> AnswerProvider:
    fallback = ExtractiveAnswerProvider()
    if settings.llm_mode != "llm":
        return fallback
    if not settings.llm_api_key or not settings.llm_model:
        return FallbackAnswerProvider(fallback, "LLM 未配置，已使用摘录模式。")
    return fallback
```

Task 3 replaces the temporary `return fallback` for configured LLM mode with the real OpenAI-compatible provider.

- [ ] **Step 5: Build evidence pack in chat orchestrator**

In `backend/service/core/chat.py`, update imports:

```python
from service.core.llm import AnswerProvider, EvidenceMemory, EvidencePack, ExtractiveAnswerProvider
```

Update the constructor type:

```python
answer_provider: AnswerProvider | None = None,
```

Add a private helper:

```python
    def _retrieval_confidence(self, chunks: list, memories: list) -> str:
        if chunks:
            return "grounded"
        if memories:
            return "memory-only"
        return "weak"
```

Replace answer generation inside `ask` with:

```python
        evidence = EvidencePack(
            question=request.message,
            chunks=chunks,
            memories=[
                EvidenceMemory(id=memory.id, text=memory.text, memory_type=memory.memory_type)
                for memory in memory_rows
            ],
            retrieval_confidence=self._retrieval_confidence(chunks, memory_rows),
        )
        result = self.answer_provider.answer(evidence)
```

Update assistant message creation:

```python
        assistant_message = self.conversations.add_message(conversation.id, "assistant", result.answer)
```

Update the returned `ChatResponse`:

```python
            answer=result.answer,
            citations=citations,
            memories=[UsedMemoryRead(id=memory.id, text=memory.text, memory_type=memory.memory_type) for memory in memory_rows],
            confidence=result.confidence,
            answer_mode=result.answer_mode,
            fallback_reason=result.fallback_reason,
```

- [ ] **Step 6: Verify chat test passes**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_response_includes_extractive_answer_metadata -v
```

Expected: the new metadata test passes.

- [ ] **Step 7: Run all current chat tests**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py -v
```

Expected: all chat tests pass with existing behavior preserved.

## Task 3: OpenAI-Compatible Provider And Fallback

**Files:**
- Modify: `backend/service/core/llm.py`
- Test: `backend/tests/test_chat.py`

- [ ] **Step 1: Add fake-client LLM success test**

Append to `backend/tests/test_chat.py`:

```python
from service.core.llm import OpenAICompatibleAnswerProvider


class FakeChatCompletionClient:
    def __init__(self):
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return "这是基于资料生成的中文总结。"


def test_chat_uses_llm_provider_when_evidence_is_grounded():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Lumen Evidence", source_type="note", content="Lumen must answer only from retrieved evidence.")
    )
    knowledge.index_source(source.id)
    fake_client = FakeChatCompletionClient()
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=fake_client,
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="How must Lumen answer?"))

    assert response.answer == "这是基于资料生成的中文总结。"
    assert response.answer_mode == "llm"
    assert response.confidence == "grounded"
    assert response.fallback_reason is None
    assert fake_client.calls
    assert "retrieved evidence" in fake_client.calls[0][1]["content"]
```

- [ ] **Step 2: Add weak-evidence no-LLM test**

Append to `backend/tests/test_chat.py`:

```python
def test_llm_provider_does_not_run_without_evidence():
    _db, _sources, _knowledge, _memories, chat = make_orchestrator()
    fake_client = FakeChatCompletionClient()
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=fake_client,
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="Tell me something unsupported."))

    assert response.confidence == "weak"
    assert response.answer_mode == "extractive"
    assert response.fallback_reason == "证据不足，已使用摘录模式。"
    assert fake_client.calls == []
```

- [ ] **Step 3: Add provider failure fallback test**

Append to `backend/tests/test_chat.py`:

```python
class FailingChatCompletionClient:
    def complete(self, messages):
        raise RuntimeError("provider down")


def test_llm_provider_falls_back_when_client_fails():
    _db, sources, knowledge, _memories, chat = make_orchestrator()
    source = sources.create(
        SourceCreate(title="Fallback Evidence", source_type="note", content="Fallback should preserve the existing extractive answer.")
    )
    knowledge.index_source(source.id)
    chat.answer_provider = OpenAICompatibleAnswerProvider(
        client=FailingChatCompletionClient(),
        fallback_provider=chat.answer_provider,
        fallback_enabled=True,
    )

    response = chat.ask(ChatRequest(message="What should fallback preserve?"))

    assert response.answer_mode == "extractive"
    assert response.fallback_reason == "LLM 请求失败，已使用摘录模式。"
    assert "Fallback should preserve" in response.answer
```

- [ ] **Step 4: Run failing LLM provider tests**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_uses_llm_provider_when_evidence_is_grounded tests/test_chat.py::test_llm_provider_does_not_run_without_evidence tests/test_chat.py::test_llm_provider_falls_back_when_client_fails -v
```

Expected: fail because `ChatCompletionClient` and `OpenAICompatibleAnswerProvider` do not exist.

- [ ] **Step 5: Add chat completion client and LLM provider**

Append these imports to `backend/service/core/llm.py`:

```python
from urllib.parse import urljoin

import httpx
```

Add below `FallbackAnswerProvider`:

```python
class ChatCompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        ...


class HttpxChatCompletionClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = httpx.post(
            urljoin(self.base_url, "chat/completions"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty chat completion content")
        return content.strip()


class OpenAICompatibleAnswerProvider:
    def __init__(
        self,
        client: ChatCompletionClient,
        fallback_provider: AnswerProvider,
        fallback_enabled: bool,
    ):
        self.client = client
        self.fallback_provider = fallback_provider
        self.fallback_enabled = fallback_enabled

    def answer(self, evidence: EvidencePack) -> AnswerResult:
        if not evidence.has_evidence:
            result = self.fallback_provider.answer(evidence)
            return replace(result, fallback_reason="证据不足，已使用摘录模式。")
        try:
            answer = self.client.complete(self._messages(evidence))
        except Exception:
            if not self.fallback_enabled:
                raise
            result = self.fallback_provider.answer(evidence)
            return replace(result, fallback_reason="LLM 请求失败，已使用摘录模式。")
        return AnswerResult(
            answer=answer,
            confidence=evidence.retrieval_confidence,
            answer_mode="llm",
        )

    def _messages(self, evidence: EvidencePack) -> list[dict[str, str]]:
        system = (
            "你是 Lumen，一个本地优先的个人知识库助手。"
            "只能依据用户提供的资料片段和已确认记忆回答。"
            "如果证据不足，请明确说明不知道，不要编造事实、日期、来源或用户偏好。"
            "用简洁中文回答。"
        )
        source_lines = [
            f"[资料 {index} | source_id={chunk.source_id} | chunk_id={chunk.id} | {chunk.source_title}]\\n{chunk.text}"
            for index, chunk in enumerate(evidence.chunks, start=1)
        ]
        memory_lines = [
            f"[记忆 {memory.id} | {memory.memory_type}] {memory.text}"
            for memory in evidence.memories
        ]
        user = (
            f"问题：{evidence.question}\\n\\n"
            "可用资料：\\n"
            f"{chr(10).join(source_lines) if source_lines else '无'}\\n\\n"
            "已确认记忆：\\n"
            f"{chr(10).join(memory_lines) if memory_lines else '无'}\\n\\n"
            "请只基于以上证据回答。"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
```

- [ ] **Step 6: Wire configured LLM provider into factory**

Replace the final `return fallback` in `build_answer_provider` with:

```python
    client = HttpxChatCompletionClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return OpenAICompatibleAnswerProvider(
        client=client,
        fallback_provider=fallback,
        fallback_enabled=settings.llm_fallback_enabled,
    )
```

- [ ] **Step 7: Verify LLM provider tests pass**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_uses_llm_provider_when_evidence_is_grounded tests/test_chat.py::test_llm_provider_does_not_run_without_evidence tests/test_chat.py::test_llm_provider_falls_back_when_client_fails -v
```

Expected: all three tests pass.

## Task 4: Backend API Wiring And Full Backend Verification

**Files:**
- Modify: `backend/service/api/chat.py`
- Test: `backend/tests/test_chat.py`
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Add API-level missing-config fallback test**

Append to `backend/tests/test_chat.py`:

```python
def test_chat_api_reports_missing_llm_config_fallback(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)
    from service.config import get_settings

    get_settings.cache_clear()
    client.post(
        "/api/sources",
        json={"title": "API Evidence", "source_type": "note", "content": "API fallback should be visible."},
    )
    client.post("/api/sources/1/index")

    response = client.post("/api/chat", json={"message": "What should be visible?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer_mode"] == "extractive"
    assert data["fallback_reason"] == "LLM 未配置，已使用摘录模式。"
```

- [ ] **Step 2: Run failing API wiring test**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_api_reports_missing_llm_config_fallback -v
```

Expected: fail because the chat API still constructs the orchestrator without settings.

- [ ] **Step 3: Build provider from settings in chat API**

In `backend/service/api/chat.py`, add imports:

```python
from service.config import Settings, get_settings
from service.core.llm import build_answer_provider
```

Update endpoint signature:

```python
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
```

Replace return line with:

```python
    answer_provider = build_answer_provider(settings)
    return ChatOrchestrator(conversations, knowledge, memories, answer_provider=answer_provider).ask(data)
```

- [ ] **Step 4: Verify API wiring test passes**

Run:

```bash
cd backend
uv run pytest tests/test_chat.py::test_chat_api_reports_missing_llm_config_fallback -v
```

Expected: test passes.

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd backend
uv run pytest -v
```

Expected: all backend tests pass.

## Task 5: Frontend Runtime Settings And Answer Metadata

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/components/ContextPanel.tsx`
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Update frontend fetch mocks and failing assertions**

In `frontend/src/test/workbench.test.tsx`, add this fetch mock near the other GET mocks:

```typescript
if (url.endsWith('/api/settings/runtime') && method === 'GET') {
  return jsonResponse({
    llm_mode: 'llm',
    llm_provider: 'openai-compatible',
    llm_model: 'gpt-test',
    llm_configured: true,
    llm_fallback_enabled: true,
    embedding_mode: 'hash',
  })
}
```

Update the `/api/chat` mock response:

```typescript
return jsonResponse({
  conversation_id: 1,
  message_id: 2,
  answer: '带引用的可信回答。',
  citations: [{ source_id: 1, source_title: '验收笔记', chunk_id: 1, quote: 'Lumen 应该引用资料来源。' }],
  memories: [],
  confidence: 'grounded',
  answer_mode: 'llm',
  fallback_reason: null,
})
```

In the first test, after asserting the answer appears, add:

```typescript
expect((await screen.findAllByText('LLM 模式')).length).toBeGreaterThan(0)
```

In the second test, after clicking settings, add:

```typescript
await user.click(screen.getByRole('button', { name: '设置' }))
expect(await screen.findByText('openai-compatible')).toBeInTheDocument()
expect(screen.getByText('gpt-test')).toBeInTheDocument()
expect(screen.getByText('API key 已配置')).toBeInTheDocument()
```

- [ ] **Step 2: Run failing frontend tests**

Run:

```bash
cd frontend
npm run test
```

Expected: fail because runtime settings and answer metadata UI are not implemented.

- [ ] **Step 3: Add frontend types**

In `frontend/src/api/types.ts`, update `ChatResponse`:

```typescript
export type ChatResponse = {
  conversation_id: number
  message_id: number
  answer: string
  citations: Array<{ source_id: number; source_title: string; chunk_id: number; quote: string }>
  memories: Array<{ id: number; text: string; memory_type: string }>
  confidence: string
  answer_mode: 'extractive' | 'llm'
  fallback_reason: string | null
}
```

Add:

```typescript
export type RuntimeSettingsRead = {
  llm_mode: 'extractive' | 'llm'
  llm_provider: string
  llm_model: string | null
  llm_configured: boolean
  llm_fallback_enabled: boolean
  embedding_mode: string
}
```

- [ ] **Step 4: Add client and hook**

In `frontend/src/api/client.ts`, import `RuntimeSettingsRead` and add:

```typescript
runtimeSettings: () => request<RuntimeSettingsRead>('/api/settings/runtime'),
```

In `frontend/src/api/hooks.ts`, import `RuntimeSettingsRead` and add:

```typescript
export function useRuntimeSettings() {
  return useQuery<RuntimeSettingsRead>({
    queryKey: ['settings', 'runtime'],
    queryFn: () => api.runtimeSettings(),
  })
}
```

- [ ] **Step 5: Render runtime mode in AppShell**

In `frontend/src/components/AppShell.tsx`, import:

```typescript
import { useRuntimeSettings } from '../api/hooks'
```

Inside `AppShell`, add:

```typescript
const runtimeSettings = useRuntimeSettings()
const answerModeLabel = runtimeSettings.data?.llm_mode === 'llm' ? 'LLM 模式' : '摘录模式'
```

Replace the hardcoded top-bar answer mode chip:

```tsx
<span>{answerModeLabel}</span>
```

- [ ] **Step 6: Render answer mode in ChatPanel**

In `frontend/src/components/ChatPanel.tsx`, add:

```typescript
const answerModeLabel = response?.answer_mode === 'llm' ? 'LLM 模式' : '摘录模式'
```

Inside the response block, after confidence, add:

```tsx
<p>
  回答模式：<strong>{answerModeLabel}</strong>
</p>
```

- [ ] **Step 7: Render fallback reason in ContextPanel**

In `frontend/src/components/ContextPanel.tsx`, inside the response stack after confidence, add:

```tsx
{response.fallback_reason ? (
  <article className="list-row">
    <strong>回退说明</strong>
    <p>{response.fallback_reason}</p>
  </article>
) : null}
```

- [ ] **Step 8: Fetch and render runtime settings in SettingsPanel**

Replace `frontend/src/components/SettingsPanel.tsx` with:

```tsx
import { API_BASE } from '../api/client'
import { useRuntimeSettings } from '../api/hooks'

export function SettingsPanel() {
  const runtimeSettings = useRuntimeSettings()
  const settings = runtimeSettings.data
  const answerMode = settings?.llm_mode === 'llm' ? 'LLM 模式' : '摘录模式'
  const modelName = settings?.llm_model ?? '未配置'
  const keyStatus = settings?.llm_configured ? 'API key 已配置' : 'API key 未配置'
  const fallbackStatus = settings?.llm_fallback_enabled ? '启用失败回退' : '未启用失败回退'

  return (
    <section className="center-panel full-span" aria-label="设置">
      <div className="panel-header">
        <div>
          <p className="eyebrow">本地运行</p>
          <h2>设置</h2>
        </div>
      </div>
      <div className="stack-list">
        <article className="list-row">
          <strong>API 地址</strong>
          <p>{API_BASE}</p>
        </article>
        <article className="list-row">
          <strong>回答模式</strong>
          <p>{runtimeSettings.isLoading ? '正在读取运行配置...' : answerMode}</p>
        </article>
        <article className="list-row">
          <strong>模型提供方</strong>
          <p>{settings?.llm_provider ?? 'openai-compatible'}</p>
        </article>
        <article className="list-row">
          <strong>模型</strong>
          <p>{modelName}</p>
        </article>
        <article className="list-row">
          <strong>密钥状态</strong>
          <p>{keyStatus}</p>
        </article>
        <article className="list-row">
          <strong>失败策略</strong>
          <p>{fallbackStatus}</p>
        </article>
        <article className="list-row">
          <strong>数据策略</strong>
          <p>模型密钥只从本地环境变量读取，不会写入数据库。</p>
        </article>
      </div>
    </section>
  )
}
```

- [ ] **Step 9: Verify frontend tests pass**

Run:

```bash
cd frontend
npm run test
```

Expected: frontend tests pass.

## Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current capabilities**

In `README.md`, under `当前能力`, add:

```markdown
- 默认使用摘录模式回答，不需要模型 API key。
- 可通过环境变量启用 OpenAI-compatible LLM 回答，并要求回答基于已检索资料和已确认记忆。
- LLM 未配置、请求失败或证据不足时会回退到摘录模式，并在界面显示回退说明。
```

- [ ] **Step 2: Update README limitations**

In `README.md`, under `当前限制`, replace:

```markdown
- 回答模式仍是摘录式，不是真正的 LLM 总结；当前不需要模型 API key。
```

with:

```markdown
- 默认回答模式仍是摘录式，不需要模型 API key；LLM 总结是可选能力。
- Phase 1.2 只支持通过环境变量配置一个 OpenAI-compatible 聊天模型，暂不支持设置页编辑、streaming 或多 provider 管理。
```

- [ ] **Step 3: Document LLM environment variables**

In `README.md`, after frontend startup instructions, add:

````markdown
## 可选 LLM 回答

默认不需要模型配置：

```bash
LUMEN_LLM_MODE=extractive
```

如果要启用 OpenAI-compatible 聊天模型，可以在启动后端前设置：

```bash
export LUMEN_LLM_MODE=llm
export LUMEN_LLM_PROVIDER=openai-compatible
export LUMEN_LLM_BASE_URL=https://api.openai.com/v1
export LUMEN_LLM_MODEL=<model-name>
export LUMEN_LLM_API_KEY=<api-key>
export LUMEN_LLM_FALLBACK_ENABLED=true
```

Lumen 不会把 API key 写入数据库。模型请求失败或证据不足时，回答会回退到摘录模式。
````

- [ ] **Step 4: Run full backend verification**

Run:

```bash
cd backend
uv run pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 5: Run full frontend verification**

Run:

```bash
cd frontend
npm run test
npm run build
```

Expected: frontend tests pass and production build succeeds.

- [ ] **Step 6: Commit implementation**

Run:

```bash
git add backend/service/config.py backend/service/schemas.py backend/service/core/llm.py backend/service/core/chat.py backend/service/api/chat.py backend/service/api/settings.py backend/service/api/router.py backend/tests/test_chat.py backend/tests/test_settings.py frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/hooks.ts frontend/src/components/AppShell.tsx frontend/src/components/ChatPanel.tsx frontend/src/components/ContextPanel.tsx frontend/src/components/SettingsPanel.tsx frontend/src/test/workbench.test.tsx README.md
git commit -m "feat: add evidence-grounded answer provider"
```

Expected: commit succeeds after tests and build pass.

## Self-Review Notes

- Spec coverage: provider adapter, evidence pack, optional LLM env config, fallback behavior, runtime settings, frontend visibility, tests, and README are covered.
- Scope control: no streaming, no editable provider settings, no database key storage, no agent tools, and no multi-provider UI.
- Type consistency: backend `answer_mode` and `fallback_reason` match frontend `ChatResponse`; runtime settings fields match `RuntimeSettingsRead`; provider factory uses `Settings` fields declared in `config.py`.
- External API note: the HTTP client uses the OpenAI-compatible `POST /v1/chat/completions` messages shape so compatible providers can share one minimal adapter.
