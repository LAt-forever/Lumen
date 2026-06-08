# Lumen Phase 1.3 Daily-Use Hardening Design Spec

Date: 2026-06-08

## Summary

Phase 1.3 makes the Phase 1.2 prototype reliable enough for repeated daily use. It does not add large Comet-parity surfaces such as graph visualization, image knowledge, streaming chat, or agent routing. Instead, it hardens the existing loop:

- add sources
- index and inspect sources
- ask questions with visible evidence
- manage remembered context
- review recent activity and diagnostics

The main product bet is that Lumen becomes more useful by improving trust, recoverability, and control before expanding into bigger features.

## Product Scope

### Retrieval And Citation Quality

Lumen should provide clearer, more stable evidence when answering questions.

The backend search path gains an explicit explanation for each returned chunk:

- matched query terms
- matched date, when date filtering contributed to the result
- retrieval score
- source title and chunk ID, unchanged from Phase 1.2

The UI presents this explanation in the context panel and search results so a user can quickly see why a citation appeared. Existing confidence values remain `grounded`, `memory-only`, and `weak`, but the visible Chinese copy should explain weak evidence more clearly.

Phase 1.3 also adds focused regression tests for Chinese retrieval cases:

- exact Chinese project or product names
- Chinese date questions
- mixed Chinese and English terms
- unrelated text that should not be returned because of hash/vector collision
- duplicate snippets that should be collapsed

### Source Management

The Library view becomes a practical place to inspect and recover source ingestion.

Users can:

- open a source detail panel or view
- see full source metadata, status, original location, parse error, and indexed chunk count
- retry indexing for failed or stale sources
- delete a source, including its chunks and answer citations

Deleting a source removes its chunks from future search and answers. Existing conversations may keep historical assistant text, but deleted-source citations should no longer be used for new answers.

### Memory Quality Control

The Memory view becomes more explicit about memory provenance and duplicate cleanup.

Users can:

- see where a candidate or confirmed memory came from, using message or source provenance
- see lightweight duplicate suggestions for active memories with very similar text
- merge suggested duplicates with the existing merge behavior

Candidate confirmation remains user-controlled. Phase 1.3 does not silently promote or delete memories.

### Runtime Diagnostics

Settings and Review show lightweight diagnostics for the answer pipeline:

- current answer mode
- provider and model status
- fallback enabled status
- latest fallback reason seen by the current UI session
- a suggested action when LLM mode is requested but not configured

Diagnostics stay safe: API keys are never returned to the frontend or stored in the database.

## Non-Goals

- no streaming chat
- no editable model/provider form
- no provider marketplace or multiple provider profiles
- no graph visualization
- no image library or multimodal search
- no OCR for scanned PDFs
- no recursive crawler or JavaScript-rendered page capture
- no autonomous agent tool routing
- no authentication or multi-user permissions
- no production deployment packaging

## Backend Design

### Search Result Explanation

Extend `ChunkRead` with optional evidence metadata:

```text
matched_terms: list[str]
matched_date: string | null
match_reason: string
```

`KnowledgeService.search()` already computes query terms and date terms. Phase 1.3 should promote those intermediate values into a small internal ranked result object and map them into API schemas. Existing clients can ignore the added fields.

### Source Detail And Delete

Extend the source API under `/api/sources`:

```text
GET /api/sources/{source_id}
DELETE /api/sources/{source_id}
```

The read endpoint returns source metadata plus indexed chunk count. The delete endpoint removes source chunks first, then the source. If historical citation rows exist, deletion should not crash; citation cleanup can either cascade or be handled explicitly by repositories.

Retry indexing continues to use:

```text
POST /api/sources/{source_id}/index
```

### Memory Provenance And Duplicates

Expose provenance fields already stored on memory candidates and memories in API responses:

```text
source_kind
source_ref
```

Add a deterministic duplicate suggestion helper in the memory service. It should be conservative:

- compare only active memories
- normalize whitespace and punctuation
- use token overlap from the existing Chinese/mixed-language term logic
- return suggestions only when overlap is high enough to avoid noisy UI

This helper supports the UI; it does not merge automatically.

### Runtime Diagnostics

Keep runtime settings read-only. Add optional non-secret diagnostics:

```text
latest_fallback_reason: string | null
configuration_hint: string | null
```

The backend can derive configuration hints from settings. The latest fallback reason may remain frontend-session state if persistent telemetry would add too much surface area.

## Frontend Design

The existing dense, operational layout stays intact.

### Context Panel

Citation rows show:

- source title
- quote
- retrieval score
- matched terms or date
- short Chinese match reason

The panel still prioritizes the answer and trust signals over decoration.

### Library View

The Library view adds source inspection actions:

- select a source from the list
- inspect details and chunk count
- retry indexing
- delete source with confirmation

The delete confirmation uses direct Chinese copy and makes the consequence clear: deleted source chunks will not appear in future answers.

### Memory View

Memory cards show provenance when available. Duplicate suggestions appear near active memories and reuse the existing merge action. The UI should remain quiet: suggestions are small helper rows, not a new dashboard.

### Settings And Review

Settings shows current non-secret model diagnostics. Review can include a suggested action when the app is in LLM mode without usable credentials.

## Error Handling

- Source detail for a missing source returns 404.
- Deleting a missing source returns 404.
- Deleting a source with chunks and citations must be idempotent from the user's perspective: after a successful delete, search and chat no longer retrieve the source.
- Retry indexing keeps the source visible and stores parse errors instead of crashing.
- Duplicate suggestions should fail closed: if similarity cannot be computed, return no suggestions.
- Runtime diagnostics must never expose the raw API key or environment variable values.

## Testing

Backend tests cover:

- search explanations for matched Chinese terms
- search explanations for matched dates
- no result for unrelated hash/vector collisions
- source detail includes chunk count
- deleting a source removes it from future search
- deleting a missing source returns 404
- memory provenance appears in API responses
- duplicate memory suggestions are conservative
- runtime settings never expose secrets

Frontend tests cover:

- context panel renders match explanations
- library source detail, retry, and delete flows
- deleted source disappears from search results
- memory provenance and duplicate suggestion UI
- settings diagnostics for configured and missing LLM modes

## Acceptance Criteria

Phase 1.3 is complete when:

- baseline Phase 1.2 tests still pass
- source inspection and deletion work from the UI
- deleted sources do not appear in new search or chat evidence
- citations and search results explain why evidence matched
- memory cards expose provenance
- duplicate memory suggestions are visible and mergeable
- settings/review provide safe answer-mode diagnostics
- backend tests pass
- frontend tests pass
- frontend production build succeeds

## Future Expansion

Phase 1.3 prepares the app for Phase 1.4 provider UX and streaming without implementing them. It also creates cleaner source and memory surfaces that later graph, tags, favorites, and global search can build on.
