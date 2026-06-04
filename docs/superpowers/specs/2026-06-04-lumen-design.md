# Lumen Design Spec

Date: 2026-06-04

## Summary

Lumen is a personal AI knowledge base and long-term memory assistant. Its long-term goal is to match and exceed the core capabilities of Comet: knowledge RAG, image knowledge, memory graph, Agent chat, global search, tags, favorites, graph visualization, model configuration, asynchronous processing, and deployment.

The first phase will not attempt full feature parity at once. It will ship a complete, high-quality vertical loop:

```text
capture notes/files/links
-> ingest into a knowledge base
-> ask with trusted citations
-> extract candidate memories from conversation
-> review memories in an inbox
-> use confirmed memories and sources in future answers
-> review recent knowledge and memory changes
```

This lets Lumen become useful early while preserving the larger Comet parity goal.

## Product Positioning

Lumen is not a dashboard-first clone of Comet. It is an experience-first personal AI workspace.

The product should feel like a calm, reliable thinking environment:

- Fast enough to open daily.
- Clear enough to trust.
- Personal enough to remember user context.
- Practical enough to run locally during development and grow into a full application.

## Goals

- Match Comet's core capability map over time.
- Make the first screen more actionable than Comet's dashboard.
- Provide trustworthy answers with visible sources, recalled memories, and confidence signals.
- Make memory explicit and controllable through confirmation, editing, merging, and forgetting.
- Keep the first implementation practical and extensible.

## Non-Goals For The First Phase

- Full Comet feature parity in one release.
- Multi-user team collaboration.
- A polished mobile app.
- Complex graph exploration as a required first-use workflow.
- Heavy infrastructure before the core loop works.

## First Screen

The first authenticated screen is the Lumen workbench, not a system dashboard.

Primary regions:

- Left navigation: Today, Ask, Library, Memory, Graph, Search, Review, Settings.
- Center work area: Ask / Capture input for questions, quick notes, file upload, and link capture.
- Right context panel: current answer sources, recalled memories, confidence signals, and pending memory candidates.
- Lower work area: recent sources, suggested next actions, and daily review.

The first screen must answer three user questions immediately:

- What can I do right now?
- What does Lumen already know?
- Why should I trust the current answer or memory?

## Phase 1 Scope

Phase 1 delivers the core loop.

### Capture

Users can add:

- Plain notes.
- Markdown files.
- Text files.
- PDF files with text extraction for selectable-text PDFs. Scanned PDF OCR is deferred.
- Web links as captured URLs with safe HTML text extraction. Authenticated pages, JavaScript-heavy pages, and crawling beyond the submitted URL are deferred.

Every captured item becomes a source with metadata:

- title
- source type
- original location or filename
- created time
- ingestion status
- parse errors if any

If link fetching fails, Lumen still stores the URL as a Source with a failed parse status and a retry action.

### Knowledge Base

Captured sources are parsed into chunks and indexed for retrieval.

Minimum retrieval behavior:

- Keyword search.
- Vector search.
- Hybrid scoring when both are available.
- Source-level citations in answers.

The first implementation should keep retrieval interfaces pluggable so the storage backend can evolve from local-first to heavier services if needed.

### Chat

Users can ask Lumen questions from the workbench.

Each answer should show:

- Final answer.
- Sources used.
- Relevant memory cards used.
- A confidence explanation when retrieval is weak or ambiguous.

The chat system should support streaming output if the chosen framework makes it straightforward. If streaming complicates the first implementation, non-streaming responses are acceptable for the first runnable version, but the API should not prevent streaming later.

### Memory

Lumen extracts candidate memories from user messages and confirmed source content.

Candidate memories are not silently committed. They appear in the Memory Inbox.

Each memory card includes:

- memory text
- memory type: preference, fact, project, relationship, goal, event, or note
- source message or source document
- created time
- confidence
- status: pending, confirmed, ignored, forgotten, merged

Users can:

- confirm a memory
- edit a memory
- ignore a memory
- forget a memory
- merge similar memories

Confirmed memories can be retrieved in future answers.

### Review

Lumen provides a simple daily or recent review surface.

The first review includes:

- newly added sources
- newly confirmed memories
- pending memory candidates
- recent questions
- suggested next actions based on current data

## Comet Parity Matrix

The table below defines the long-term parity target.

| Capability | Comet Has It | Lumen Phase 1 | Later Lumen Target |
| --- | --- | --- | --- |
| Authenticated app shell | Yes | Optional local-only first | Full auth if needed |
| Dashboard | Yes | Replaced by workbench | Add analytics dashboard later |
| Knowledge documents | Yes | Yes | Stronger source inspection and citation UX |
| Web page ingestion | Yes | Basic safe capture | More robust crawler and refresh |
| Image library | Yes | Not required | Multimodal image understanding and search |
| RAG search | Yes | Yes | Hybrid retrieval, rerank, evaluation set |
| Agent chat | Yes | Basic tool-aware chat | Full tool routing and streaming |
| Citations | Yes | Yes | Better citation panel and evidence quality |
| Memory extraction | Yes | Yes | More controllable extraction policy |
| Memory graph | Yes | Lightweight graph model first | Full graph visualization and graph queries |
| Global search | Yes | Basic unified search | Search across sources, chunks, memories, chats, images |
| Tags | Yes | Basic metadata only | User and AI tags with merge controls |
| Favorites | Yes | Not required | Save sources, answers, and memories |
| Model configuration | Yes | Environment/config first | UI-managed providers and model profiles |
| Agent configuration | Yes | Sensible defaults | User-editable tool and behavior profiles |
| Async processing | Yes | Background jobs where needed | Queue dashboard and retry management |
| System health | Yes | Developer health endpoint | User-visible status panel |
| Docker deployment | Yes | Later | One-command local deployment |

## Architecture

The system should be split into clear units.

### Frontend

Responsibilities:

- Workbench UI.
- Capture and upload flows.
- Chat experience.
- Source and citation panels.
- Memory inbox.
- Basic review view.

Suggested shape:

- React + TypeScript.
- A design system with restrained, work-focused styling.
- Query/state layer for API calls and local UI state.
- Component boundaries around Workbench, Chat, Sources, MemoryInbox, Review, and Settings.

### API

Responsibilities:

- Source ingestion endpoints.
- Chat endpoints.
- Search endpoints.
- Memory candidate and memory management endpoints.
- Review endpoints.
- Health endpoint.

Suggested shape:

- FastAPI or an equivalent typed API framework.
- Service layer for business logic.
- Repository layer for storage access.
- Background task boundary for parsing, indexing, and memory extraction.

### Knowledge Service

Responsibilities:

- Parse sources.
- Chunk text.
- Embed chunks.
- Index chunks.
- Search chunks.
- Return citation-ready source references.

The first implementation should expose a stable internal interface:

```text
add_source(input) -> source
index_source(source_id) -> ingest_result
search(query, filters) -> ranked_chunks
get_citations(chunk_ids) -> citation_list
```

### Memory Service

Responsibilities:

- Extract candidate memories.
- Store pending memories.
- Support confirm, edit, ignore, forget, and merge actions.
- Search confirmed memories for answer context.

The first implementation can store memory relationships in a relational schema. It should keep a graph-shaped domain model so Neo4j or another graph backend can be added later.

### Chat Orchestrator

Responsibilities:

- Decide when to use knowledge search.
- Decide when to use memory search.
- Compose context for the model.
- Produce answer plus evidence metadata.
- Trigger memory candidate extraction after user messages or completed answers.

First-phase orchestration can be deterministic:

- Always run knowledge search for knowledge questions.
- Always run memory search for personal context.
- Include both when confidence is useful.
- Avoid autonomous multi-step agent loops until the core answer quality is stable.

## Data Model

Core entities:

- User: optional in local-first mode; required if auth is enabled.
- Source: original captured note, file, or link.
- SourceChunk: indexed text chunk with source reference and position.
- Conversation: chat thread.
- Message: user or assistant message.
- Citation: source and chunk reference used in an answer.
- MemoryCandidate: extracted but unconfirmed memory.
- Memory: confirmed memory.
- MemoryRelation: relation between memories or entities when graph features are enabled.
- ReviewItem: generated daily or recent review entry.

Important statuses:

- Source status: pending, parsing, indexed, failed.
- Memory candidate status: pending, confirmed, ignored, merged.
- Memory status: active, edited, forgotten, merged.

## Key Flows

### Ingest Source

1. User adds note, file, or link.
2. API creates a Source with pending status.
3. Parser extracts text and metadata.
4. Chunker creates retrieval chunks.
5. Embedding/indexing stores searchable chunks.
6. Source status becomes indexed or failed.
7. UI shows the result and any parse errors.

### Ask Question

1. User asks in the workbench.
2. Chat orchestrator retrieves relevant chunks.
3. Chat orchestrator retrieves confirmed memories when personal context may help.
4. Model answers with context.
5. API stores answer, citations, and memory usage metadata.
6. UI displays answer, citations, recalled memories, and confidence explanation.
7. Memory extraction runs on the user message and creates pending candidates.

### Review Memory

1. User opens Memory Inbox.
2. Pending candidates are grouped by source or theme.
3. User confirms, edits, ignores, forgets, or merges.
4. Confirmed memories become searchable.
5. Later answers can cite those memories as personal context.

## Error Handling

Lumen should make failures visible and recoverable.

- Source parsing failures show a readable error and allow retry.
- Indexing failures do not delete the original source.
- Retrieval with weak evidence must say evidence is weak instead of over-answering.
- Model failures return a useful message and preserve the user prompt for retry.
- Memory extraction failures do not block chat answers.
- Duplicate memory candidates are grouped or merge-suggested instead of silently multiplying.

## Trust And Control

Trust is a first-class feature.

Required trust behaviors:

- Answers show sources.
- Personal context shows which memories were used.
- Memory candidates require user confirmation before becoming active.
- Users can forget memory items.
- Edited memories preserve enough provenance to explain where they came from.
- Lumen should say when it does not know.

## Testing Strategy

Phase 1 should include focused tests around the core loop.

Backend tests:

- Source creation and status transitions.
- Chunking produces stable chunk references.
- Search returns citation-ready results.
- Chat response stores citations.
- Memory candidate lifecycle: pending, confirmed, edited, ignored, forgotten, merged.
- Review endpoint aggregates recent sources and memories.

Frontend tests:

- Workbench renders with empty state.
- Capture flow shows pending and indexed states.
- Chat answer displays sources and memories.
- Memory inbox supports confirm, edit, ignore, and forget.
- Review view handles empty and populated states.

Integration tests:

- Add a source, ask a question, receive an answer with a citation.
- Ask a personal-context question after confirming a memory.
- Failed source parsing stays recoverable.

## Milestones

### Milestone 0: Project Foundation

- Initialize app structure.
- Establish frontend and backend.
- Add basic health checks.
- Add storage and configuration.

### Milestone 1: Workbench And Capture

- Build Lumen shell and first screen.
- Add note/file/link capture.
- Store source metadata.
- Show source status.

### Milestone 2: Knowledge Search And Citations

- Parse and chunk sources.
- Add search.
- Add citation-ready answer flow.
- Show source panel in chat.

### Milestone 3: Memory Inbox

- Extract candidate memories.
- Add memory lifecycle actions.
- Retrieve confirmed memories during chat.

### Milestone 4: Review And Polish

- Add recent review.
- Improve empty states and loading states.
- Add reliability tests and basic deployment path.

### Milestone 5: Comet Parity Expansion

- Add image library.
- Add graph visualization.
- Add tags and favorites.
- Add model and Agent configuration UI.
- Add async task visibility and system health panel.

## Open Decisions

These decisions are intentionally deferred to the implementation plan, because they depend on local dependency availability and desired deployment complexity.

- Exact backend framework and package manager.
- Exact vector storage choice for the first local version.
- Whether the first runnable version uses SQLite, PostgreSQL, or a local embedded database.
- Whether streaming chat is included in the first runnable milestone.
- Which LLM and embedding providers are configured first.

The design remains valid across those choices because each subsystem has a stable boundary.

## Acceptance Criteria For Phase 1

Lumen Phase 1 is successful when:

- A user can open the workbench and immediately ask or capture.
- A source can be ingested and searched.
- A question can be answered with at least one visible citation when evidence exists.
- A conversation can produce a pending memory candidate.
- The user can confirm, edit, ignore, or forget a memory candidate.
- Confirmed memories can influence later answers.
- The review view summarizes recent sources and memories.
- The app has tests covering the main happy path and key failure paths.
