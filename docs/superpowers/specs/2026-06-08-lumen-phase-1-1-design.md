# Lumen Phase 1.1 Design Spec

Date: 2026-06-08

## Summary

Phase 1.1 turns the Phase 1 prototype into a tighter daily-use loop. It does not expand into graph visualization, image knowledge, model settings, or agent configuration. It closes the most visible gaps from Phase 1:

- confirmed memory management after inbox confirmation
- practical source capture for files and links
- real first-level navigation for Library, Memory, Search, Review, and Settings
- minor backend lifecycle cleanup

The goal is still local-first and extractive. The app should remain simple enough to run without model credentials.

## Product Scope

### Memory Management

Users can manage confirmed memories after they leave the inbox:

- list active memories
- edit memory text and type
- forget a memory so it no longer appears in active lists or future chat context
- merge one memory into another so related memories can be consolidated

Candidate memories remain explicit and controllable. A candidate can still be confirmed with edited text/type or ignored from the inbox.

### Source Capture

Users can add more than pasted notes:

- pasted notes, unchanged from Phase 1
- uploaded `.txt`, `.md`, and selectable-text `.pdf` files
- web links captured by URL, with safe server-side HTML extraction

If parsing fails, Lumen stores the source with `failed` status and a readable error. The user can retry indexing/capture after fixing the input or network issue. OCR, authenticated pages, JavaScript-heavy crawling, and recursive crawling remain out of scope.

### Navigation

The left nav should become useful without introducing heavy routing:

- Today shows the existing workbench loop
- Library shows sources and capture controls
- Memory shows confirmed memories and pending candidates
- Search provides a query box over indexed chunks
- Review shows recent sources, memories, questions, and suggested actions
- Settings shows current local runtime assumptions

The implementation can use internal React state rather than URL routes. That keeps the phase small while making the navigation honest and testable.

### Lifecycle Cleanup

Replace the FastAPI `on_event("startup")` hook with a lifespan handler to remove the current deprecation warning while preserving database initialization behavior.

## Non-Goals

- no graph visualization
- no image library
- no OCR
- no background queue dashboard
- no provider/model configuration UI beyond read-only settings context
- no full authentication
- no streaming chat

## Backend Design

Memory changes extend the existing `MemoryRepository` and `MemoryService` boundaries. New API endpoints live under `/api/memories/{memory_id}`:

- `PATCH /api/memories/{memory_id}` updates text/type and marks status `edited`
- `POST /api/memories/{memory_id}/forget` marks status `forgotten`
- `POST /api/memories/{memory_id}/merge` merges a source memory into a target memory and marks the source `merged`

Source capture keeps the existing `Source` model. File and link helpers normalize content into the existing `content` column so indexing remains unchanged:

- `POST /api/sources/upload` accepts multipart files
- `POST /api/sources/link` accepts a URL, fetches HTML, extracts readable text, and stores source metadata
- `POST /api/sources/{source_id}/index` continues to index content and records parse failures

Network fetch failures must not crash the app. They produce a failed `Source` row.

Search stays extractive and chunk-based. The existing `/api/search?q=` endpoint remains the backend contract.

## Frontend Design

The frontend keeps the current calm workbench visual system:

- palette: existing green primary, warm accent, soft neutral surfaces
- typography: existing local system stack
- spacing: existing 8px/10px/18px rhythm
- radius: 8px controls and panels
- motion: no new motion beyond hover/focus states

New UI is dense and operational:

- Capture panel gains mode controls for note, file, and link.
- Library page lists sources, statuses, errors, and retry indexing actions.
- Memory page shows pending candidates and confirmed memories with edit, forget, and merge controls.
- Search page adds a query field and result list with source title, score, and snippet.
- Review page reuses the existing review panel.
- Settings page exposes local-first mode, extractive answer mode, and configured API base.

UI text remains Chinese.

## Testing

Backend tests cover:

- memory edit
- memory forget removing it from search
- memory merge preserving target and hiding source
- text upload ingestion and indexing
- PDF parse failure path
- link capture success and fetch failure path
- lifespan startup health behavior

Frontend tests cover:

- switching nav views
- uploading a file source
- adding a link source
- searching indexed content
- editing, forgetting, and merging memories

## Acceptance Criteria

Phase 1.1 is complete when:

- all existing Phase 1 tests still pass
- a user can add note, file, or link sources from the UI
- failed source capture/indexing is visible in the UI
- a user can edit, forget, and merge confirmed memories
- forgotten or merged memories are not used in future answers
- nav items show distinct useful views
- backend and frontend tests pass
- frontend production build succeeds
