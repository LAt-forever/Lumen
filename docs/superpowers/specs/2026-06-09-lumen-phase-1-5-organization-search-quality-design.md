# Lumen Phase 1.5 Organization, Search, And Quality Design Spec

Date: 2026-06-09

## Summary

Phase 1.5 turns Lumen from a working knowledge-and-memory loop into a daily-use knowledge workspace. It adds user-controlled organization, true global search, lightweight retrieval quality checks, and a user-visible status surface while preserving the Phase 1.4 model runtime boundary.

The phase uses a data-model-first approach:

```text
tags and favorites
-> unified search across sources, memories, and conversations
-> visible result quality signals
-> small retrieval evaluation set
-> status panel with repair actions
```

Phase 1.5 intentionally does not add autonomous Agent tool routing, a full graph canvas, OCR, image understanding, external reranker configuration, or a full asynchronous queue dashboard.

## Product Goals

- Let users organize important sources, memories, and answers with tags and favorites.
- Let users search across sources, source chunks, memories, and conversation messages from one place.
- Make search results easier to trust by showing type, tags, favorite state, match reason, and score.
- Add a small local evaluation set so retrieval quality can be checked before future graph and Agent work.
- Give users a status panel that shows runtime and ingestion health and offers direct repair actions.

## Product Scope

### Tags

Users can manually create and apply tags to:

- sources
- memories
- conversation messages and assistant answers

Lumen can suggest tags from source, memory, and message content. Suggested tags are not applied automatically. They enter a pending state and become real assignments only after the user confirms them.

Tag suggestions include:

- suggested label
- target type
- target ID
- reason
- confidence
- status: `pending`, `confirmed`, or `ignored`

Confirmed AI suggestions become normal tag assignments with `source=ai-confirmed`. Manually applied tags use `source=user`.

### Favorites

Users can favorite:

- sources
- memories
- conversation messages and assistant answers

Favorites are a lightweight retrieval and review signal. They do not change the original object. Favorited objects are surfaced in global search filters and can be summarized by Review.

Favorite actions are idempotent:

- favoriting the same target twice keeps one favorite
- unfavoriting a target that is not favorited succeeds without damaging other state

### Global Search

Phase 1.5 adds true global search across:

- source chunks
- source records
- confirmed active memories
- conversation messages, including assistant answers

Search results use one unified response shape and include a `result_type` field:

- `source_chunk`
- `source`
- `memory`
- `message`

The global search page can filter by:

- result type
- tag
- favorite state

The existing chat retrieval path should remain stable. Phase 1.5 adds `/api/global-search` instead of replacing the existing `/api/search` chunk endpoint. This avoids breaking evidence-grounded chat citations from Phase 1.4.

### Search Quality Signals

Each global search result shows:

- result type
- title or concise label
- snippet
- score
- matched terms
- matched date when available
- match reason
- tags
- favorite state

The goal is not to create a perfect relevance model in Phase 1.5. The goal is to make the current local retrieval behavior legible and testable.

### Retrieval Evaluation

Phase 1.5 adds a small deterministic Chinese retrieval evaluation set. It should run without external model calls.

The evaluation fixtures cover:

- a date-based work-log question
- a project-goal question
- a preference memory question
- a conversation answer recall question
- a tag-filtered search question
- a favorite-filtered search question

Each case defines:

- seeded sources, memories, and messages
- query text
- expected result type
- expected target identifier or text fragment
- minimum acceptable rank
- required match reason behavior when applicable

The evaluation should be executable as backend tests. It can later become a user-visible quality dashboard, but Phase 1.5 only requires test coverage.

### Status Panel

Phase 1.5 adds a user-visible status view. It summarizes:

- runtime source: database profile, environment, or extractive fallback
- active provider profile name when present
- latest fallback reason when present
- total sources
- indexed sources
- failed sources
- pending tag suggestions
- recent failed source details

The status view includes repair actions:

- jump to Settings when model configuration needs attention
- jump to a source detail when a source failed
- retry failed source parsing or indexing
- jump to tag suggestions when pending suggestions exist

This is not a full task queue. It is a practical status and repair surface for the current local prototype.

## Non-Goals

- no Agent tool routing
- no autonomous multi-step task execution
- no Agent permission or approval UI
- no full graph visualization canvas
- no memory graph query language
- no OCR for scanned PDFs
- no image library or multimodal image search
- no external reranker provider integration
- no reranker configuration UI
- no full asynchronous job queue, cancellation, or log viewer
- no multi-user permissions or per-user tags

## Backend Design

### Data Model

Add the following SQLAlchemy models.

```text
Tag
- id: int
- name: str
- color: str | null
- created_at: datetime
- updated_at: datetime
```

`Tag.name` is unique after normalization. Normalization trims whitespace and compares case-insensitively. The stored name preserves user-facing text.

```text
TagAssignment
- id: int
- tag_id: int
- target_type: str
- target_id: int
- source: str
- created_at: datetime
```

Allowed `target_type` values:

- `source`
- `memory`
- `message`

Allowed `source` values:

- `user`
- `ai-confirmed`

The `(tag_id, target_type, target_id)` tuple is unique.

```text
TagSuggestion
- id: int
- label: str
- target_type: str
- target_id: int
- reason: str
- confidence: int
- status: str
- created_at: datetime
- updated_at: datetime
```

Allowed `status` values:

- `pending`
- `confirmed`
- `ignored`

```text
Favorite
- id: int
- target_type: str
- target_id: int
- created_at: datetime
```

Allowed `target_type` values:

- `source`
- `memory`
- `message`

The `(target_type, target_id)` tuple is unique.

Because the project currently uses `Base.metadata.create_all()`, Phase 1.5 can add these tables without a migration framework. The design should keep model changes additive.

### Schemas

Add public schemas for organization and search:

```text
TagRead
- id
- name
- color
- created_at

TagCreate
- name
- color

TagAssignmentRead
- id
- tag
- target_type
- target_id
- source
- created_at

TagAssignmentCreate
- tag_id
- target_type
- target_id

TagSuggestionRead
- id
- label
- target_type
- target_id
- reason
- confidence
- status
- created_at

FavoriteRead
- id
- target_type
- target_id
- created_at

FavoriteCreate
- target_type
- target_id

GlobalSearchResultRead
- result_type
- target_id
- title
- snippet
- score
- matched_terms
- matched_date
- match_reason
- tags
- is_favorite
- created_at
```

### API Endpoints

Add organization endpoints:

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

Add global search:

```text
GET /api/global-search?q=&types=&tag=&favorite=
```

Query behavior:

- `q` is required and must be non-empty after trimming
- `types` is optional and can include one or more result types
- `tag` filters to targets assigned that tag
- `favorite=true` filters to favorited targets

Add status and repair endpoints:

```text
GET /api/status
POST /api/sources/{source_id}/retry
```

`POST /api/sources/{source_id}/retry` reruns the existing parsing and indexing flow for failed sources. It returns the updated source detail. It should reject retry for missing sources and no-op safely for sources that are already indexed.

### Repositories And Services

Add focused repositories:

- `TagRepository`: tag CRUD, normalized lookup, assignment create/delete, assignments by target
- `TagSuggestionRepository`: pending list, confirm, ignore
- `FavoriteRepository`: create/delete/list, favorite state by target
- `GlobalSearchService`: aggregate and rank sources, chunks, memories, and messages
- `StatusService`: runtime and content health summary

`GlobalSearchService` should reuse existing search explanation helpers where possible. It should not mutate data.

### Tag Suggestions

Phase 1.5 can start with deterministic local suggestions. The suggestion generator should extract conservative labels from:

- source titles
- repeated project names
- memory types
- clear Chinese project or preference phrases

It should not call an LLM by default. If an LLM-backed tag suggestion path is added later, it must keep the same pending-confirmation boundary.

### Ranking

Global search uses a simple blended score:

- textual match score
- date match boost when the query contains a recognizable date
- title match boost for sources
- memory type or provenance match boost for memories
- recent message match boost for conversations
- favorite boost when not filtering by favorite
- tag boost when query text matches an assigned tag

Scores are explainable. The `match_reason` should mention the strongest visible reason, such as matched terms, matched date, tag match, favorite match, or title match.

### Status Summary

`GET /api/status` returns:

```text
StatusSummaryRead
- runtime
- source_counts
- failed_sources
- pending_tag_suggestion_count
- latest_fallback_reason
- suggested_actions
```

The `runtime` object can reuse existing safe runtime settings fields from `/api/settings/runtime`. It must not expose API keys.

## Frontend Design

### Navigation

Add a `状态` view to the left navigation. The first screen remains the workbench; status is a supporting view.

### Global Search Page

Upgrade the Search page copy and behavior from source-only search to global search.

Controls:

- query input
- segmented result-type filter: all, source, memory, conversation
- tag filter
- favorite-only toggle

Results:

- type label
- title
- snippet
- tags
- favorite toggle
- match reason
- score or quality indicator

The page should preserve the work-focused Phase 1 UI style. It should not become a marketing-style dashboard.

### Source And Memory Organization

Source details and memory cards show:

- assigned tags
- add/remove tag control
- favorite toggle
- pending tag suggestions for that object
- confirm/ignore actions for suggestions

### Chat Favorites

Assistant answers and useful conversation messages expose a favorite toggle. The UI does not need full message editing in Phase 1.5.

### Status View

The status view shows compact sections:

- model runtime
- source indexing health
- pending tag suggestions
- suggested repair actions

Repair actions route users to the relevant existing view when possible:

- Settings for model issues
- Source detail for parse/index failures
- tag suggestion review controls for pending suggestions

## Error Handling

- Tag creation with a duplicate normalized name returns the existing tag or a clear 409-style validation error.
- Assigning a tag to a missing target returns 404.
- Confirming a missing or non-pending tag suggestion returns a clear 404 or 400.
- Favoriting a missing target returns 404.
- Global search with no matches returns an empty list and a calm empty state.
- Status summary failures should not block the whole app shell; the status view can show a localized error.
- Source retry preserves the original source record and updates status/error fields through the existing ingestion boundary.

## Testing Strategy

### Backend Tests

Add focused tests for:

- tag creation and normalized duplicate handling
- tag assignment to sources, memories, and messages
- assignment deletion
- tag suggestion confirm and ignore
- favorite create/delete idempotency
- global search across source chunks, sources, memories, and messages
- global search type filters
- global search tag and favorite filters
- result quality signals and match reasons
- status summary counts
- failed source retry behavior
- no API key leakage in status runtime payloads

### Retrieval Evaluation Tests

Add deterministic fixtures covering:

- date work-log retrieval
- project-goal retrieval
- preference memory retrieval
- conversation answer retrieval
- tag-filtered retrieval
- favorite-filtered retrieval

Each fixture should assert that the expected target appears within the configured maximum rank and includes an understandable match reason.

### Frontend Tests

Add component tests for:

- global search rendering mixed result types
- result type filtering
- tag filter and favorite-only toggle
- tag suggestion confirm/ignore interactions
- favorite toggles on sources, memories, and chat answers
- status view runtime and source health sections
- status view repair actions

## Acceptance Criteria

Phase 1.5 is complete when:

- users can create tags and assign them to sources, memories, and messages
- Lumen can create pending tag suggestions and users can confirm or ignore them
- users can favorite sources, memories, and conversation messages or assistant answers
- global search returns source, memory, and conversation results in one response shape
- global search can filter by result type, tag, and favorite state
- search results show match reasons and quality signals
- the deterministic Chinese retrieval evaluation tests pass
- the status view shows runtime, source indexing health, pending tag suggestions, and repair actions
- source retry works for failed sources without deleting source history
- backend tests pass
- frontend tests pass
- frontend production build succeeds

## Future Expansion

Phase 1.5 creates foundations for later phases:

- graph visualization can use tags, favorites, and target relationships as graph affordances
- image knowledge can reuse tags, favorites, and global search result shapes
- Agent routing can use global search and favorites as read-only tools before any write-capable actions
- a future queue dashboard can expand the status view without replacing it
- future rerankers can improve `GlobalSearchService` while preserving result explanations
