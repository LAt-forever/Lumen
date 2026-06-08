# Lumen Phase 1.3 Daily-Use Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Lumen's daily-use loop with explainable retrieval, source inspection/deletion, memory duplicate suggestions, and safe runtime diagnostics.

**Architecture:** Extend existing FastAPI repository/service boundaries and React Query hooks rather than adding new infrastructure. Backend schemas gain additive fields so Phase 1.2 clients continue to work, and frontend components enrich the current dense workbench views.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, TanStack Query, Vitest.

---

## File Structure

- Modify `backend/service/schemas.py`: add source detail, chunk explanation, memory duplicate suggestion, and runtime diagnostic response fields.
- Modify `backend/service/core/knowledge.py`: compute matched terms, matched dates, and Chinese match reasons for each result.
- Modify `backend/service/repositories/chunks.py`: add chunk counting and source chunk deletion helpers.
- Modify `backend/service/repositories/sources.py`: add source deletion helper.
- Modify `backend/service/api/sources.py`: add source detail and delete endpoints.
- Modify `backend/service/repositories/memories.py`: expose active memory list for duplicate comparison.
- Modify `backend/service/core/memory.py`: add conservative duplicate suggestion logic.
- Modify `backend/service/api/memories.py`: add duplicate suggestion endpoint.
- Modify `backend/service/api/settings.py`: add non-secret configuration hints.
- Modify `backend/tests/test_knowledge.py`, `backend/tests/test_sources.py`, `backend/tests/test_memories.py`, `backend/tests/test_settings.py`: backend behavior coverage.
- Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`: add API contracts and React Query hooks.
- Modify `frontend/src/components/ContextPanel.tsx`, `frontend/src/components/SearchPanel.tsx`, `frontend/src/components/SourceList.tsx`, `frontend/src/components/MemoryManager.tsx`, `frontend/src/components/SettingsPanel.tsx`: surface the new trust and control fields.
- Modify `frontend/src/test/workbench.test.tsx`: frontend flow coverage.
- Modify `README.md`: document Phase 1.3 behavior and remaining limits.

---

### Task 1: Backend Search Explanations

**Files:**
- Modify: `backend/service/schemas.py`
- Modify: `backend/service/core/knowledge.py`
- Test: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write failing tests for Chinese term and date explanations**

Add tests asserting returned chunks include `matched_terms`, `matched_date`, and `match_reason`.

```python
def test_search_explains_chinese_term_matches(client):
    source = client.post(
        "/api/sources",
        json={"title": "Lumen 日志", "source_type": "note", "content": "Lumen 检索需要展示引用原因。"},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    results = client.get("/api/search", params={"q": "Lumen 检索"}).json()

    assert results[0]["matched_terms"]
    assert "匹配关键词" in results[0]["match_reason"]


def test_search_explains_date_matches(client):
    source = client.post(
        "/api/sources",
        json={"title": "日报", "source_type": "note", "content": "2026年6月1日 完成 Lumen 日期检索。"},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    results = client.get("/api/search", params={"q": "2026年6月1日 Lumen 做了什么"}).json()

    assert results[0]["matched_date"] == "2026-06-01"
    assert "匹配日期 2026-06-01" in results[0]["match_reason"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_knowledge.py::test_search_explains_chinese_term_matches tests/test_knowledge.py::test_search_explains_date_matches -v`

Expected: FAIL because `ChunkRead` lacks explanation fields.

- [ ] **Step 3: Add additive schema fields**

Extend `ChunkRead`:

```python
class ChunkRead(BaseModel):
    id: int
    source_id: int
    source_title: str
    text: str
    score: float
    matched_terms: list[str] = []
    matched_date: str | None = None
    match_reason: str = ""
```

- [ ] **Step 4: Compute explanations in `KnowledgeService.search()`**

Store sorted matched terms and matched date in `RankedChunk`, then build a Chinese `match_reason` such as `匹配关键词：Lumen、检索` or `匹配日期 2026-06-01；匹配关键词：Lumen`.

- [ ] **Step 5: Run focused backend tests**

Run: `cd backend && uv run pytest tests/test_knowledge.py -v`

Expected: PASS.

---

### Task 2: Backend Source Detail And Delete

**Files:**
- Modify: `backend/service/schemas.py`
- Modify: `backend/service/repositories/chunks.py`
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/api/sources.py`
- Test: `backend/tests/test_sources.py`

- [ ] **Step 1: Write failing tests for source detail and delete**

Add tests asserting source detail includes `chunk_count`, delete removes chunks from search, and missing source returns 404.

```python
def test_source_detail_includes_chunk_count(client):
    source = client.post(
        "/api/sources",
        json={"title": "Detail source", "source_type": "note", "content": "Chunk count visible."},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    detail = client.get(f"/api/sources/{source['id']}").json()

    assert detail["id"] == source["id"]
    assert detail["chunk_count"] >= 1


def test_delete_source_removes_it_from_future_search(client):
    source = client.post(
        "/api/sources",
        json={"title": "Delete me", "source_type": "note", "content": "DeleteMarker searchable content."},
    ).json()
    client.post(f"/api/sources/{source['id']}/index")

    assert client.get("/api/search", params={"q": "DeleteMarker"}).json()
    response = client.delete(f"/api/sources/{source['id']}")

    assert response.status_code == 204
    assert client.get("/api/search", params={"q": "DeleteMarker"}).json() == []


def test_delete_missing_source_returns_404(client):
    response = client.delete("/api/sources/9999")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_sources.py::test_source_detail_includes_chunk_count tests/test_sources.py::test_delete_source_removes_it_from_future_search tests/test_sources.py::test_delete_missing_source_returns_404 -v`

Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Add `SourceDetailRead`**

Add a schema extending the source read shape with `chunk_count: int`.

- [ ] **Step 4: Add repository helpers**

Add `ChunkRepository.count_for_source(source_id)`, `ChunkRepository.delete_for_source(source_id)`, and `SourceRepository.delete(source_id)`.

- [ ] **Step 5: Add API endpoints**

Add `GET /api/sources/{source_id}` and `DELETE /api/sources/{source_id}`. Delete chunks first, then source, and return HTTP 204.

- [ ] **Step 6: Run focused backend tests**

Run: `cd backend && uv run pytest tests/test_sources.py -v`

Expected: PASS.

---

### Task 3: Backend Memory Duplicate Suggestions

**Files:**
- Modify: `backend/service/schemas.py`
- Modify: `backend/service/core/memory.py`
- Modify: `backend/service/api/memories.py`
- Test: `backend/tests/test_memories.py`

- [ ] **Step 1: Write failing duplicate suggestion tests**

Add tests for high-overlap memories returning one suggestion and unrelated memories returning none.

```python
def test_duplicate_memory_suggestions_are_conservative(client):
    first = client.post("/api/chat", json={"message": "我喜欢 Lumen 回答带清晰引用。"}).json()
    candidates = client.get("/api/memories/candidates").json()
    client.post(f"/api/memories/candidates/{candidates[0]['id']}/confirm", json={"text": "我喜欢 Lumen 回答带清晰引用。", "memory_type": "preference"})
    client.post("/api/chat", json={"message": "我的偏好是 Lumen 的回答要有清楚引用。"})
    candidates = client.get("/api/memories/candidates").json()
    client.post(f"/api/memories/candidates/{candidates[0]['id']}/confirm", json={"text": "我的偏好是 Lumen 的回答要有清楚引用。", "memory_type": "preference"})

    suggestions = client.get("/api/memories/duplicate-suggestions").json()

    assert suggestions
    assert suggestions[0]["source_memory_id"] != suggestions[0]["target_memory_id"]
    assert suggestions[0]["overlap_score"] >= 0.6
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_memories.py::test_duplicate_memory_suggestions_are_conservative -v`

Expected: FAIL because endpoint does not exist.

- [ ] **Step 3: Add response schema**

Add `MemoryDuplicateSuggestionRead` with `source_memory_id`, `target_memory_id`, `source_text`, `target_text`, and `overlap_score`.

- [ ] **Step 4: Implement conservative overlap**

Reuse the memory service term extraction. Compare active memories pairwise, require overlap score >= 0.6, and return deterministic pairs sorted by score desc.

- [ ] **Step 5: Add endpoint**

Add `GET /api/memories/duplicate-suggestions`.

- [ ] **Step 6: Run memory tests**

Run: `cd backend && uv run pytest tests/test_memories.py -v`

Expected: PASS.

---

### Task 4: Backend Runtime Diagnostics

**Files:**
- Modify: `backend/service/schemas.py`
- Modify: `backend/service/api/settings.py`
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Write failing runtime hint tests**

Add tests for missing LLM config and no secret leakage.

```python
def test_runtime_settings_reports_missing_llm_configuration_hint(client, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "llm")
    monkeypatch.delenv("LUMEN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("LUMEN_LLM_MODEL", raising=False)

    payload = client.get("/api/settings/runtime").json()

    assert payload["configuration_hint"] == "LLM 模式已开启，但模型名称或 API key 未配置。"
    assert "api_key" not in payload
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_settings.py::test_runtime_settings_reports_missing_llm_configuration_hint -v`

Expected: FAIL because `configuration_hint` is missing.

- [ ] **Step 3: Add schema fields**

Add `configuration_hint: str | None = None` and `latest_fallback_reason: str | None = None` to `RuntimeSettingsRead`.

- [ ] **Step 4: Derive safe hint**

If `llm_mode == "llm"` and config is incomplete, return `LLM 模式已开启，但模型名称或 API key 未配置。`; otherwise return `None`.

- [ ] **Step 5: Run settings tests**

Run: `cd backend && uv run pytest tests/test_settings.py -v`

Expected: PASS.

---

### Task 5: Frontend API Contracts And Hooks

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing frontend API-flow assertions**

Update test stubs to handle `GET /api/sources/7`, `DELETE /api/sources/7`, and `GET /api/memories/duplicate-suggestions`. Add assertions that source detail and delete actions call the new endpoints.

- [ ] **Step 2: Run frontend test and verify failure**

Run: `cd frontend && npm run test`

Expected: FAIL because hooks/components do not call new endpoints yet.

- [ ] **Step 3: Add TypeScript types**

Add `SourceDetailRead`, chunk explanation fields, `MemoryDuplicateSuggestionRead`, and runtime diagnostic fields.

- [ ] **Step 4: Add client methods**

Add `getSource`, `deleteSource`, and `duplicateMemorySuggestions`.

- [ ] **Step 5: Add hooks**

Add `useSourceDetail(sourceId)`, `useDeleteSource()`, and `useDuplicateMemorySuggestions()`. Invalidate `sources`, `search`, and `review` after delete.

- [ ] **Step 6: Run TypeScript-facing test**

Run: `cd frontend && npm run test`

Expected: PASS after UI tasks use the hooks.

---

### Task 6: Frontend UI Hardening

**Files:**
- Modify: `frontend/src/components/ContextPanel.tsx`
- Modify: `frontend/src/components/SearchPanel.tsx`
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/components/MemoryManager.tsx`
- Modify: `frontend/src/components/SettingsPanel.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing UI expectations**

Assert visible Chinese copy for match reasons, source chunk count, delete confirmation/action, memory provenance, duplicate suggestions, and configuration hint.

- [ ] **Step 2: Run frontend test and verify failure**

Run: `cd frontend && npm run test`

Expected: FAIL because new UI copy is absent.

- [ ] **Step 3: Render match explanations**

Context and search rows show `match_reason`, `matched_terms`, `matched_date`, and score when present.

- [ ] **Step 4: Add source inspection and delete controls**

Source rows can be selected. Detail area shows chunk count, location, parse errors, retry, and delete. Use `window.confirm` for deletion in this phase.

- [ ] **Step 5: Render memory provenance and duplicate suggestions**

Memory cards show `provenance`. Duplicate suggestions show source/target texts and call existing merge mutation.

- [ ] **Step 6: Render runtime hints**

Settings shows `configuration_hint` and latest fallback placeholder only when present.

- [ ] **Step 7: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: PASS.

---

### Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README capability and limitation lists**

Document Phase 1.3 additions: explainable citations/search, source detail/delete, duplicate memory suggestions, and safe runtime hints.

- [ ] **Step 2: Run full backend tests**

Run: `cd backend && uv run pytest -v`

Expected: PASS.

- [ ] **Step 3: Run full frontend tests**

Run: `cd frontend && npm run test`

Expected: PASS.

- [ ] **Step 4: Run frontend production build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Review git diff**

Run: `git status --short` and `git diff --stat`.

Expected: only Phase 1.3 files changed.
