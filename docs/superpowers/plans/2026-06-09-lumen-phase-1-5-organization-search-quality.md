# Lumen Phase 1.5 Organization, Search, And Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1.5 organization, global search, retrieval quality checks, and status repair surfaces from `docs/superpowers/specs/2026-06-09-lumen-phase-1-5-organization-search-quality-design.md`.

**Architecture:** Add additive SQLAlchemy models for tags, tag assignments, tag suggestions, and favorites. Keep the existing `/api/search` endpoint stable for chat retrieval and add `/api/global-search` for mixed source, memory, and conversation results. Frontend work extends the current React workbench with global search filters, organization controls, favorite toggles, and a status view.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite, pytest, React, TypeScript, TanStack Query, Vitest, Testing Library.

---

## File Structure

Backend files:

- Modify `backend/service/models.py`: add `Tag`, `TagAssignment`, `TagSuggestion`, and `Favorite`.
- Modify `backend/service/schemas.py`: add organization, global search, and status schemas.
- Create `backend/service/repositories/organization.py`: tag, suggestion, and favorite persistence.
- Modify `backend/service/repositories/sources.py`: count and failed-source helpers.
- Modify `backend/service/repositories/conversations.py`: message listing and lookup helpers.
- Modify `backend/service/repositories/memories.py`: list/get active memories for search and target validation.
- Create `backend/service/core/tagging.py`: deterministic tag suggestion generation.
- Create `backend/service/core/global_search.py`: mixed global search service and ranking.
- Create `backend/service/core/status.py`: status summary composition.
- Create `backend/service/api/organization.py`: tag, suggestion, and favorite endpoints.
- Create `backend/service/api/global_search.py`: `/api/global-search`.
- Create `backend/service/api/status.py`: `/api/status`.
- Modify `backend/service/api/sources.py`: add `/api/sources/{source_id}/retry`.
- Modify `backend/service/api/router.py`: include new routers.
- Test `backend/tests/test_organization.py`: tag, suggestion, and favorite behavior.
- Test `backend/tests/test_global_search.py`: mixed search, filters, and evaluation fixtures.
- Test `backend/tests/test_status.py`: status summary and source retry.

Frontend files:

- Modify `frontend/src/api/types.ts`: add organization, global search, and status types.
- Modify `frontend/src/api/client.ts`: add organization, global search, status, and retry client methods.
- Modify `frontend/src/api/hooks.ts`: add TanStack Query hooks and invalidations.
- Modify `frontend/src/App.tsx`: add `状态` navigation.
- Modify `frontend/src/components/AppShell.tsx`: render status view and support navigation to status.
- Create `frontend/src/components/OrganizationControls.tsx`: shared tags, suggestions, and favorite UI.
- Modify `frontend/src/components/SearchPanel.tsx`: global search UI with type, tag, and favorite filters.
- Modify `frontend/src/components/SourceList.tsx`: source tags, suggestions, favorite toggle, retry.
- Modify `frontend/src/components/MemoryManager.tsx`: memory tags, suggestions, favorite toggle.
- Modify `frontend/src/components/ChatPanel.tsx`: favorite assistant answer.
- Create `frontend/src/components/StatusPanel.tsx`: runtime, source health, tag suggestions, repair actions.
- Modify `frontend/src/styles.css`: compact controls, chips, segmented filters, and status sections.
- Test `frontend/src/test/workbench.test.tsx`: global search, organization controls, favorites, and status view.

Docs:

- Modify `README.md`: update current capabilities and limits for Phase 1.5.

---

### Task 1: Backend Organization Data Model And Schemas

**Files:**
- Modify: `backend/service/models.py`
- Modify: `backend/service/schemas.py`
- Test: `backend/tests/test_organization.py`

- [ ] **Step 1: Write failing model/schema tests**

Create `backend/tests/test_organization.py` with tests named:

```python
def test_tag_creation_normalizes_duplicate_names(client): ...
def test_tag_assignment_supports_source_memory_and_message_targets(client): ...
def test_favorite_create_and_delete_are_idempotent(client): ...
```

Run: `cd backend && uv run pytest tests/test_organization.py -v`

Expected: FAIL because `/api/tags`, `/api/tags/assignments`, and `/api/favorites` do not exist.

- [ ] **Step 2: Add additive SQLAlchemy models**

In `backend/service/models.py`, add `Tag`, `TagAssignment`, `TagSuggestion`, and `Favorite` with the fields from the design spec. Add uniqueness constraints for normalized tag name, tag assignment tuple, and favorite target tuple.

- [ ] **Step 3: Add Pydantic schemas**

In `backend/service/schemas.py`, add:

```text
TargetType = Literal["source", "memory", "message"]
TagSuggestionStatus = Literal["pending", "confirmed", "ignored"]
TagAssignmentSource = Literal["user", "ai-confirmed"]
TagRead
TagCreate
TagAssignmentRead
TagAssignmentCreate
TagSuggestionRead
FavoriteRead
FavoriteCreate
TargetOrganizationRead
```

- [ ] **Step 4: Run focused tests**

Run: `cd backend && uv run pytest tests/test_organization.py -v`

Expected: still FAIL because repository and router behavior is not implemented yet, but model import and schema validation errors should be gone.

---

### Task 2: Backend Organization Repositories And API

**Files:**
- Create: `backend/service/repositories/organization.py`
- Create: `backend/service/api/organization.py`
- Modify: `backend/service/api/router.py`
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/repositories/memories.py`
- Modify: `backend/service/repositories/conversations.py`
- Test: `backend/tests/test_organization.py`

- [ ] **Step 1: Implement target validation helpers**

Add helper methods:

```text
SourceRepository.exists(source_id) -> bool
MemoryRepository.exists_active(memory_id) -> bool
ConversationRepository.get_message(message_id) -> Message | None
```

- [ ] **Step 2: Implement organization repository**

Create `OrganizationRepository` with:

```text
normalize_tag_name(name)
list_tags()
create_tag(name, color)
assign_tag(tag_id, target_type, target_id, source="user")
delete_assignment(assignment_id)
list_assignments(target_type=None, target_id=None)
create_suggestion(label, target_type, target_id, reason, confidence)
pending_suggestions(target_type=None, target_id=None)
confirm_suggestion(suggestion_id)
ignore_suggestion(suggestion_id)
favorite(target_type, target_id)
unfavorite(target_type, target_id)
is_favorite(target_type, target_id)
favorites(target_type=None)
```

- [ ] **Step 3: Implement organization router**

Create endpoints:

```text
GET /api/tags
POST /api/tags
POST /api/tags/assignments
DELETE /api/tags/assignments/{assignment_id}
GET /api/tag-suggestions
POST /api/tag-suggestions/{suggestion_id}/confirm
POST /api/tag-suggestions/{suggestion_id}/ignore
GET /api/favorites
POST /api/favorites
DELETE /api/favorites/{target_type}/{target_id}
```

All write endpoints validate that the target exists. Confirming a suggestion creates or reuses the tag and adds an `ai-confirmed` assignment.

- [ ] **Step 4: Include router and run tests**

Modify `backend/service/api/router.py` to include the organization router.

Run: `cd backend && uv run pytest tests/test_organization.py -v`

Expected: PASS.

- [ ] **Step 5: Run related regression tests**

Run: `cd backend && uv run pytest tests/test_sources.py tests/test_memories.py tests/test_chat.py -v`

Expected: PASS.

- [ ] **Step 6: Commit backend organization**

Run:

```bash
git add backend/service/models.py backend/service/schemas.py backend/service/repositories/organization.py backend/service/repositories/sources.py backend/service/repositories/memories.py backend/service/repositories/conversations.py backend/service/api/organization.py backend/service/api/router.py backend/tests/test_organization.py
git commit -m "feat: add organization tags and favorites"
```

---

### Task 3: Backend Global Search And Retrieval Evaluation

**Files:**
- Create: `backend/service/core/global_search.py`
- Create: `backend/service/api/global_search.py`
- Modify: `backend/service/api/router.py`
- Modify: `backend/service/repositories/conversations.py`
- Modify: `backend/service/repositories/memories.py`
- Test: `backend/tests/test_global_search.py`

- [ ] **Step 1: Write failing global search tests**

Create `backend/tests/test_global_search.py` with tests named:

```python
def test_global_search_returns_sources_memories_and_messages(client): ...
def test_global_search_filters_by_result_type(client): ...
def test_global_search_filters_by_tag_and_favorite(client): ...
def test_retrieval_evaluation_date_project_preference_and_answer_cases(client): ...
```

Run: `cd backend && uv run pytest tests/test_global_search.py -v`

Expected: FAIL because `/api/global-search` does not exist.

- [ ] **Step 2: Implement GlobalSearchService**

Create a service that searches source chunks, source records, active memories, and messages. Reuse the existing date and term extraction approach from `KnowledgeService` and return `GlobalSearchResultRead` records with tags and favorite state.

- [ ] **Step 3: Implement global search router**

Create:

```text
GET /api/global-search?q=&types=&tag=&favorite=
```

Rules:

- `q` is required and trimmed
- `types` can repeat or use comma-separated values
- `tag` filters assigned targets and source chunks through their parent source tag
- `favorite=true` filters favorited targets and source chunks through their parent source favorite

- [ ] **Step 4: Include router and run focused tests**

Run: `cd backend && uv run pytest tests/test_global_search.py -v`

Expected: PASS.

- [ ] **Step 5: Run search and chat regressions**

Run: `cd backend && uv run pytest tests/test_global_search.py tests/test_knowledge.py tests/test_chat.py -v`

Expected: PASS.

- [ ] **Step 6: Commit global search**

Run:

```bash
git add backend/service/core/global_search.py backend/service/api/global_search.py backend/service/api/router.py backend/service/repositories/conversations.py backend/service/repositories/memories.py backend/tests/test_global_search.py
git commit -m "feat: add global search"
```

---

### Task 4: Backend Status Summary, Source Retry, And Tag Suggestions

**Files:**
- Create: `backend/service/core/tagging.py`
- Create: `backend/service/core/status.py`
- Create: `backend/service/api/status.py`
- Modify: `backend/service/api/sources.py`
- Modify: `backend/service/api/router.py`
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/repositories/organization.py`
- Test: `backend/tests/test_status.py`
- Test: `backend/tests/test_organization.py`

- [ ] **Step 1: Write failing status and suggestion tests**

Create `backend/tests/test_status.py` with tests named:

```python
def test_status_summary_reports_runtime_sources_and_pending_tag_suggestions(client): ...
def test_source_retry_reindexes_failed_source_without_deleting_history(client): ...
def test_status_runtime_payload_does_not_leak_api_keys(client): ...
```

Add to `backend/tests/test_organization.py`:

```python
def test_tag_suggestions_can_be_confirmed_or_ignored(client): ...
```

Run: `cd backend && uv run pytest tests/test_status.py tests/test_organization.py -v`

Expected: FAIL because status, retry, and suggestions are incomplete.

- [ ] **Step 2: Implement deterministic tag suggestion service**

Create `TagSuggestionService` in `backend/service/core/tagging.py`. It creates conservative pending suggestions from source titles/content, memory type/text, and message content. It avoids duplicates for the same normalized label and target.

- [ ] **Step 3: Implement status service and router**

Create `StatusService` in `backend/service/core/status.py` and `/api/status` in `backend/service/api/status.py`. The payload includes runtime settings, source counts, failed sources, pending tag suggestion count, latest fallback reason, and suggested actions.

- [ ] **Step 4: Add source retry endpoint**

In `backend/service/api/sources.py`, add:

```text
POST /api/sources/{source_id}/retry
```

It uses `KnowledgeService.index_source()` for failed or pending sources, returns `SourceDetailRead`, and leaves already indexed sources stable.

- [ ] **Step 5: Run focused and regression tests**

Run: `cd backend && uv run pytest tests/test_status.py tests/test_organization.py tests/test_sources.py -v`

Expected: PASS.

- [ ] **Step 6: Commit status and retry**

Run:

```bash
git add backend/service/core/tagging.py backend/service/core/status.py backend/service/api/status.py backend/service/api/sources.py backend/service/api/router.py backend/service/repositories/sources.py backend/service/repositories/organization.py backend/tests/test_status.py backend/tests/test_organization.py
git commit -m "feat: add status and repair actions"
```

---

### Task 5: Frontend API Types, Client, And Hooks

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing frontend API usage tests**

Extend `frontend/src/test/workbench.test.tsx` with assertions that the UI calls:

```text
GET /api/global-search
GET /api/tags
GET /api/tag-suggestions
POST /api/favorites
GET /api/status
POST /api/sources/failed-id/retry
```

Run: `cd frontend && npm test -- --run`

Expected: FAIL because the frontend does not call new endpoints.

- [ ] **Step 2: Add TypeScript types**

Add `TagRead`, `TagAssignmentRead`, `TagSuggestionRead`, `FavoriteRead`, `GlobalSearchResultRead`, and `StatusSummaryRead`.

- [ ] **Step 3: Add client methods**

Add client methods:

```text
listTags
createTag
assignTag
deleteTagAssignment
listTagSuggestions
confirmTagSuggestion
ignoreTagSuggestion
listFavorites
favorite
unfavorite
globalSearch
status
retrySource
```

- [ ] **Step 4: Add hooks and invalidations**

Add hooks for tags, suggestions, favorites, global search, status, and source retry. Invalidate relevant query keys after organization writes.

- [ ] **Step 5: Run typecheck**

Run: `cd frontend && npm run build`

Expected: PASS once UI imports are updated in later tasks. During this task it may fail only if unused exports are not referenced; resolve by keeping exports valid and not importing them yet.

---

### Task 6: Frontend Global Search And Organization Controls

**Files:**
- Create: `frontend/src/components/OrganizationControls.tsx`
- Modify: `frontend/src/components/SearchPanel.tsx`
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/components/MemoryManager.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Implement shared organization controls**

Create a compact component that renders:

- favorite toggle
- assigned tags
- add-tag selector
- pending suggestion chips with confirm and ignore buttons

- [ ] **Step 2: Upgrade SearchPanel**

Replace source-only search with global search. Add result type segmented filter, tag selector, favorite-only checkbox, mixed result cards, match reasons, tags, and favorite toggles.

- [ ] **Step 3: Add organization controls to source and memory views**

Render controls for each source, selected source detail, and memory card.

- [ ] **Step 4: Add favorite control to chat answers**

Render a favorite toggle for the latest assistant answer when `response.message_id` exists.

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && npm test -- --run`

Expected: PASS.

---

### Task 7: Frontend Status View

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/StatusPanel.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Add status navigation**

Add `状态` to `frontend/src/App.tsx` using a lucide status/monitor icon.

- [ ] **Step 2: Render StatusPanel**

Add `status` to `ViewKey` and render `StatusPanel` in `AppShell`.

- [ ] **Step 3: Implement StatusPanel**

Render runtime source, active profile, latest fallback, source counts, failed sources, pending tag suggestions, and suggested actions. Retry failed sources through the retry hook.

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit frontend Phase 1.5 UI**

Run:

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/hooks.ts frontend/src/App.tsx frontend/src/components/AppShell.tsx frontend/src/components/OrganizationControls.tsx frontend/src/components/SearchPanel.tsx frontend/src/components/SourceList.tsx frontend/src/components/MemoryManager.tsx frontend/src/components/ChatPanel.tsx frontend/src/components/StatusPanel.tsx frontend/src/styles.css frontend/src/test/workbench.test.tsx
git commit -m "feat: add organization search and status ui"
```

---

### Task 8: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Test: full backend and frontend suites

- [ ] **Step 1: Update README**

Document Phase 1.5 capabilities:

- tags and AI tag suggestions
- favorites for sources, memories, and answers
- global search across sources, memories, and conversations
- search filters and quality signals
- status view and source retry

Update current limitations to keep Agent routing, graph canvas, OCR, images, external rerankers, and full queue dashboard out of scope.

- [ ] **Step 2: Run backend full suite**

Run: `cd backend && uv run pytest -v`

Expected: PASS.

- [ ] **Step 3: Run frontend full suite**

Run: `cd frontend && npm test -- --run`

Expected: PASS.

- [ ] **Step 4: Run frontend production build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Inspect git status**

Run: `git status --short`

Expected: only intended Phase 1.5 changes.

- [ ] **Step 6: Commit docs and verification fixes**

Run:

```bash
git add README.md
git commit -m "docs: document phase 1.5 capabilities"
```

---

## Completion Audit

Before claiming Phase 1.5 is complete, verify every acceptance criterion from the design spec against current evidence:

- tags can be created and assigned to sources, memories, and messages
- pending tag suggestions can be created, confirmed, and ignored
- sources, memories, and messages can be favorited and unfavorited
- global search returns source, memory, and conversation results in one response shape
- global search filters by result type, tag, and favorite state
- search results show match reasons and quality signals
- deterministic Chinese retrieval evaluation tests pass
- status view shows runtime, source health, pending tag suggestions, and repair actions
- source retry works for failed sources without deleting history
- backend tests pass
- frontend tests pass
- frontend production build succeeds
