# Lumen Comet Parity Program Design

Date: 2026-06-22

## Summary

Lumen will move from a local-first prototype into a full Comet-class personal AI knowledge base and agent platform. The target is complete capability parity with the Comet open source repository, without discounting heavy infrastructure, multi-user product surfaces, graph storage, advanced retrieval, autonomous agent workflows, or secondary product modules.

This spec supersedes the earlier "light prototype first" framing. Existing Lumen strengths remain part of the target product:

- Evidence-grounded answers with visible citations.
- Explicit memory confirmation, editing, merging, forgetting, and provenance.
- Durable ingestion progress and repair surfaces.
- Auditable tool logs and controlled configuration.
- Chinese-first product copy.

The new target adds the full Comet-level platform shape:

- Multi-user authentication and user-scoped data isolation.
- PostgreSQL, Elasticsearch, Neo4j, Redis, Celery worker, and Celery beat in the default local stack.
- Real embedding, hybrid retrieval, reranking, and rebuildable search indexes.
- Neo4j-backed memory graph with entities, triples, events, provenance, timeline, and visualization.
- Multi-knowledge-base management, image knowledge, sharing, tags, favorites, global search, dashboard, and status.
- Agent configuration, tools, MCP servers, Skills, research tasks, ReAct or function-calling execution, and task logs.
- Persona, persona groups, group chat, notifications, model configuration, music, and emotion-related product surfaces matching Comet's module map.

## Product Decision

Lumen will not fork Comet or copy its source as the main approach. Lumen will evolve its current codebase into the same product class while keeping local code ownership, existing tests, and Lumen's trust-oriented interaction model.

The approved execution strategy is evolutionary full parity:

1. Keep the application runnable after each phase.
2. Upgrade the runtime stack before building features that depend on it.
3. Build each capability as a complete vertical slice: data model, service, API, worker behavior, frontend route, tests, and smoke flow.
4. Treat every Comet-visible domain as in scope unless explicitly removed by a future user-approved scope change.

## Parity Definition

A capability counts as parity only when all of the following are true:

- The user can access it from the frontend through a stable route or workflow.
- The backend exposes durable API endpoints for the workflow.
- Data is persisted in the appropriate store with user isolation.
- Background work is durable and visible when the workflow is asynchronous.
- Search, graph, and derived projections can be rebuilt from primary records.
- Failures are visible and retryable where retry makes sense.
- Tests cover the core service behavior and at least one API path.
- A smoke flow is documented in README or a phase-specific acceptance section.

## Goals

- Make Lumen a Comet-class platform, not a narrower local knowledge prototype.
- Adopt the full multi-service runtime: PostgreSQL, Redis, Elasticsearch, Neo4j, backend, worker, scheduler, frontend.
- Replace hash embeddings and keyword gates with real embeddings, ES BM25/vector retrieval, and reranking.
- Replace rule-only memory extraction with LLM-structured memory extraction while keeping user confirmation controls.
- Use Neo4j for memory graph queries, visualization, community-style exploration, and timeline/event reasoning.
- Add full multi-user authentication and user-level data isolation across relational, search, graph, file, and worker boundaries.
- Add Comet-level Agent, MCP, Skills, research, persona, group chat, dashboard, notifications, model configuration, sharing, image, music, and emotion surfaces.
- Keep evidence visibility, provenance, approval, and audit logs as first-class Lumen product values.

## Non-Goals

- No direct source-code fork of Comet as the primary architecture.
- No hidden global data access in the name of speed.
- No "demo-only" feature that bypasses persistence, user isolation, or tests.
- No replacement of existing Lumen trust controls with silent automation.
- No removal of existing Lumen workflows until the parity replacement is functional.

## Current Lumen State

Lumen already has a useful base:

- FastAPI backend with SQLAlchemy, Alembic, Celery, Redis, PostgreSQL when configured, and SQLite fallback.
- React frontend with React Query, React Flow, d3-force, and a Chinese workspace UI.
- Durable ingestion jobs for notes, uploads, links, crawls, and bookmarks.
- Parsers for text, markdown, PDF, DOCX, EPUB, images, web links, crawls, and bookmark HTML.
- Extractive answers and OpenAI-compatible LLM answers when configured, both with citations.
- Memory candidates, confirmed memories, manual relations, graph visualization, duplicate suggestions, tags, favorites, global search, status, settings, and controlled Agent tools.
- Retrieval evaluation seed command and smoke guidance.

Important current limitations:

- Retrieval still uses hash embeddings and in-process keyword/date scoring.
- Memory extraction is mostly deterministic keyword classification.
- Memory graph is stored relationally, not in Neo4j.
- Agent runs preselected read-only tools and does not perform autonomous multi-step planning.
- There is no multi-user authentication or cross-store user isolation.
- The default compose stack does not include Elasticsearch or Neo4j.
- Product surfaces such as persona, group chat, Skills, MCP management, research, notifications, music, and emotion modules are absent or not equivalent.

## Target Runtime Architecture

The default development and product stack contains:

- `postgres`: primary transactional database for users, sources, conversations, memory metadata, model configuration, agent configuration, jobs, tags, favorites, shares, and audit logs.
- `redis`: Celery broker, Celery result backend, short-lived caches, and coordination primitives.
- `elasticsearch`: full-text, vector, hybrid, and global search index. It uses Chinese-capable analysis where available and stores only rebuildable search projections.
- `neo4j`: memory graph, entity graph, triple graph, event graph, provenance paths, and graph analytics projections.
- `backend`: FastAPI API service.
- `worker`: Celery worker for ingestion, embedding, indexing, memory extraction, graph sync, research, notification, and rebuild tasks.
- `beat`: Celery beat scheduler for periodic maintenance, retries, refreshes, and reminder-style tasks.
- `frontend`: React/Vite frontend.

SQLite remains allowed only as a legacy emergency mode for narrow development checks. It is not the target stack for Comet parity.

## Data Ownership

PostgreSQL is the primary source of truth for business records:

- users and auth records
- knowledge bases
- sources and file metadata
- conversations and messages
- memory candidates and memory decisions
- model/provider/agent/tool/skill configuration
- jobs and audit logs
- tags, favorites, shares, notifications, and product metadata

Elasticsearch is the search projection:

- source chunks
- image descriptions and OCR text
- conversations and assistant answers
- memories and graph-derived summaries
- tags and favorite boost signals
- global search documents

Neo4j is the graph query projection:

- memory nodes
- entities
- relations/triples
- events and time anchors
- source/message provenance nodes
- merge lineage and contradiction/support edges
- user and knowledge-base scoping properties

Projection rebuild is mandatory. If Elasticsearch or Neo4j data is lost, worker commands must rebuild them from PostgreSQL and stored files where possible.

All writes to Elasticsearch and Neo4j go through service boundaries or background tasks. Controllers do not perform ad hoc cross-store writes.

## Multi-User And Isolation Model

Every user-owned table gains `user_id` or joins through a parent that has `user_id`. This includes sources, chunks, ingestion jobs, conversations, messages, citations, memories, memory candidates, graph relations, tags, favorites, shares, model profiles, agent profiles, skills, MCP servers, research reports, notifications, image assets, music records, and emotion records.

Every Elasticsearch document includes:

- `user_id`
- `knowledge_base_id` when applicable
- `document_type`
- `target_id`
- visibility flags

Every Neo4j node and relationship includes:

- `user_id`
- `scope_type`
- `scope_id`
- provenance fields where relevant

API handlers resolve the current user from authenticated context. Repository methods accept user scope explicitly or are constructed with a user scope object. Cross-user reads are rejected at repository or service boundaries, not only in controllers.

## Authentication And Accounts

The parity target includes:

- email/password login
- registration switch controlled by settings
- password hashing
- JWT access token
- refresh token or session renewal flow
- current user endpoint
- frontend auth store and protected routes
- logout
- admin bootstrap user controlled by settings

Secrets stored in provider, reranker, model, MCP, notification, and external tool configuration remain encrypted at rest.

## Knowledge Base Architecture

Lumen will add explicit multi-knowledge-base support.

Core objects:

- `KnowledgeBase`: user-owned workspace for documents, images, and web captures.
- `Source`: one original source record.
- `SourceAsset`: stored file or fetched raw artifact.
- `SourceChunk`: parsed text chunk with embedding status and index status.
- `IndexingRun`: durable record of embedding, ES indexing, and graph-sync operations.

Ingestion supports:

- text and markdown
- PDF with selectable text and OCR fallback
- DOCX
- EPUB
- images with OCR and vision description
- web links
- recursive web crawls
- browser bookmarks
- future file families through parser registry

Knowledge-base workflows:

- create, rename, archive, delete knowledge bases
- select active knowledge base in chat and search
- upload or capture into one or more knowledge bases
- inspect source details, chunks, parse metadata, indexing state, and citations
- retry failed parse, embedding, and index tasks
- refresh web sources and crawls
- share selected conversations, reports, or source summaries

## Retrieval Architecture

Lumen will replace current hash embedding retrieval with a full retrieval pipeline.

Pipeline:

1. Parse and chunk source content.
2. Generate real embeddings using configured embedding provider.
3. Store chunk metadata and embedding status in PostgreSQL.
4. Index searchable projections in Elasticsearch with:
   - body text
   - title
   - tags
   - source metadata
   - user and knowledge-base scope
   - vector field
   - timestamps
   - citation pointers
5. Query BM25 and vector search in one request or coordinated requests.
6. Merge and normalize scores.
7. Apply reranker when configured.
8. Return citations and match explanations.

Retrieval modes:

- knowledge-base search
- memory search
- conversation search
- image search
- global search
- agent tool search

The evaluation command expands from a small seed into a versioned regression suite that measures retrieval hit rate, citation quality, weak-evidence behavior, and reranker improvements.

## Memory Architecture

Memory extraction becomes LLM-structured, but confirmation remains explicit.

Extraction flow:

1. A user message, assistant answer, or source chunk becomes an extraction candidate input.
2. A worker runs a structured extraction prompt.
3. The extractor returns candidate facts, preferences, projects, goals, relationships, events, entities, and triples.
4. Candidates are stored in PostgreSQL with provenance, confidence, raw model output, and source pointers.
5. The user can confirm, edit, ignore, merge, or forget candidates.
6. Confirmed memories write graph projections into Neo4j.

Neo4j graph model:

- `User`
- `Memory`
- `Entity`
- `Event`
- `Source`
- `Message`
- `KnowledgeBase`
- `Tag`

Relationship types:

- `RELATED_TO`
- `BELONGS_TO`
- `CAUSES`
- `SUPPORTS`
- `CONTRADICTS`
- `MERGED_INTO`
- `MENTIONS`
- `DERIVED_FROM`
- `OCCURRED_ON`
- `PREFERS`
- `WORKS_ON`
- `HAS_GOAL`

Every graph write includes provenance. Graph relations are never anonymous.

Memory UX:

- inbox for pending candidates
- confirmed memory list
- duplicate and conflict suggestions
- manual relation editor
- graph view
- timeline view
- provenance path inspector
- merge lineage
- forget and restore where policy allows

## Agent, Tools, MCP, And Skills

The target Agent system matches Comet's product class while keeping Lumen auditability.

Core objects:

- `AgentProfile`
- `AgentTool`
- `AgentTask`
- `AgentRun`
- `AgentStep`
- `AgentToolLog`
- `MCPServer`
- `Skill`
- `SkillVersion`

Capabilities:

- ReAct loop and function-calling loop, selected by provider capability.
- Tool registry for knowledge search, memory search, graph query, web search, source inspection, report creation, notification, and MCP tools.
- MCP server configuration, health checks, and tool discovery.
- Skills with prompt templates, instructions, and tool permissions.
- Tool allowlist per agent profile.
- Approval policy for write-capable tools.
- Streaming step updates to the frontend.
- Durable run logs and replayable traces.

Agent answer rules:

- Evidence-bearing tasks must cite retrieved sources or graph provenance.
- Write actions require explicit policy checks and, where configured, approval.
- Agent failures produce visible error summaries and retry actions.

## Research Tasks

Research is a first-class Agent workflow, not just chat.

Workflow:

1. User creates a research task with topic, scope, knowledge-base selection, and a web-permission flag.
2. Planner decomposes the task into research questions.
3. Retriever gathers local and external evidence.
4. Curator filters and clusters evidence.
5. Distiller writes structured findings.
6. Report generator creates a saved report with citations.
7. User can share the report.

Research artifacts are stored in PostgreSQL, searchable in Elasticsearch, and linked to graph provenance when memory or entity claims are extracted.

## Persona And Group Chat

Lumen will add:

- persona cards
- persona groups
- group chat sessions
- host or moderator role
- speaker selection
- persona-specific prompts
- persona memory access policies
- group chat sharing and join links

Persona chat still uses the same evidence and memory boundaries as single-agent chat. Personas do not gain cross-user access.

## Product Surface Parity

Frontend routes will expand from the current Lumen workbench into a Comet-class app shell.

Required route families:

- Home or Dashboard
- Chat
- Knowledge Bases
- Knowledge Detail
- Image Library
- Memory
- Graph
- Global Search
- Favorites
- Model Config
- Agent Config
- Agent Tasks
- Research
- Personas
- Group Chat
- Skills
- MCP Tools
- Notifications
- Music Library
- Emotion
- Profile
- Share pages
- Status and maintenance

The frontend may keep Lumen's current visual style where it improves clarity, but the functional surface must match the Comet module map. Ant Design-level component coverage is acceptable through AntD adoption or equivalent components, but missing controls are not acceptable.

## Dashboard And Status

Dashboard parity includes:

- recent knowledge changes
- recent memory changes
- pending memory candidates
- failed jobs
- retrieval/index health
- graph sync health
- storage health for PostgreSQL, Elasticsearch, Neo4j, Redis, and worker
- agent task status
- recent conversations
- favorites and tags
- suggested next actions

Status parity includes:

- job queue
- worker heartbeat
- ES index health
- Neo4j health
- projection rebuild actions
- failed parse/index/graph-sync retries
- maintenance command documentation

## Tags, Favorites, And Sharing

Tags and favorites become cross-domain primitives:

- sources
- chunks or documents
- memories
- messages
- reports
- images
- music records where applicable

Tag suggestions can be deterministic or LLM-assisted, but confirmation remains visible. Sharing supports public or tokenized read-only access to conversations, reports, or selected knowledge summaries.

## Notifications

Notification channels are user-owned configurations.

Initial channel types:

- in-app notifications
- webhook
- email-compatible provider

Notification events:

- job failed
- research task completed
- scheduled review ready
- model/provider test failed
- graph/index rebuild completed
- agent approval needed

## Music And Emotion Modules

Music and emotion modules are in scope for parity because Comet exposes them as product modules. They will be implemented after core knowledge, memory, and Agent work so they can reuse user isolation, file storage, model config, tags, favorites, and search.

Music scope:

- track metadata
- lyric storage
- tags and favorites
- search
- frontend library page

Emotion scope:

- mood or emotion records
- extraction from conversation and manual entry
- timeline view
- search and dashboard summaries

## Model And Provider Configuration

Model configuration expands beyond current chat provider profiles.

Provider profiles cover:

- chat completions
- embeddings
- vision
- rerank
- speech or audio where needed
- external search providers

Every profile includes:

- provider type
- base URL or provider-specific endpoint
- model
- encrypted secret fields
- timeout
- test status
- last error
- user scope
- active/default flags per capability

Runtime config resolution chooses capability-specific profiles instead of one global chat profile.

## Background Jobs

Celery workers process:

- parsing
- OCR
- vision description
- embeddings
- Elasticsearch indexing
- Neo4j graph sync
- memory extraction
- duplicate and conflict detection
- research task steps
- notification dispatch
- source refresh
- projection rebuilds
- cleanup

Celery beat schedules:

- stale job recovery
- periodic health snapshots
- source refreshes
- reminder and review generation
- retry backoff checks

Every long-running workflow writes progress to PostgreSQL and exposes it through APIs.

## API Shape

API route families:

- `/api/auth`
- `/api/users`
- `/api/knowledge-bases`
- `/api/sources`
- `/api/images`
- `/api/search`
- `/api/chat`
- `/api/memories`
- `/api/graph`
- `/api/tags`
- `/api/favorites`
- `/api/shares`
- `/api/model-profiles`
- `/api/agent-profiles`
- `/api/agent-tasks`
- `/api/tools`
- `/api/mcp`
- `/api/skills`
- `/api/research`
- `/api/personas`
- `/api/group-chat`
- `/api/notifications`
- `/api/music`
- `/api/emotions`
- `/api/status`
- `/api/maintenance`

Existing endpoints can remain temporarily, but new parity work should move toward these route families.

## Migration Strategy

Migration happens in phases and keeps the app runnable.

1. Add multi-service compose and health checks.
2. Add user model and authentication.
3. Add `user_id` to existing tables and backfill a bootstrap local user.
4. Add knowledge-base model and assign existing sources to a default knowledge base.
5. Add Elasticsearch projection services and rebuild command.
6. Add real embedding provider profiles and migrate chunk indexing to ES.
7. Add Neo4j projection services and rebuild command.
8. Add LLM memory extraction and graph sync.
9. Expand Agent, Skills, MCP, research, persona, and product modules.

Data migration rules:

- Existing local data is preserved.
- A bootstrap user owns existing records after auth is introduced.
- Rebuild commands are idempotent.
- Projection failures do not corrupt primary PostgreSQL records.

## Program Phases

### Phase 0: Parity Audit And Runtime Foundation

Deliverables:

- Comet module parity matrix in repo docs.
- Docker Compose with PostgreSQL, Redis, Elasticsearch, Neo4j, backend, worker, beat, frontend.
- Health APIs for all services.
- Environment and README updates.
- Tests for service health aggregation.

Acceptance:

- `docker compose up --build` starts the full stack.
- Status page shows all service health.
- Existing ingestion and chat smoke flows still work.

### Phase 1: Auth, Users, And Data Isolation

Deliverables:

- User model, auth APIs, JWT/session flow.
- Frontend login and protected routes.
- `user_id` backfill for existing records.
- Repository-level user scoping.
- Tests proving cross-user isolation.

Acceptance:

- Two users cannot see each other's sources, memories, conversations, jobs, tags, or favorites.
- Existing local data is assigned to a bootstrap user.

### Phase 2: Knowledge Bases And Elasticsearch Retrieval

Deliverables:

- Knowledge-base model and UI.
- ES index templates and projection service.
- Real embedding provider profile.
- Hybrid BM25/vector search.
- Reranker integration in the actual retrieval path.
- Rebuild and backfill commands.

Acceptance:

- Search and chat retrieve through ES.
- Evaluation suite reports hit metrics.
- Deleting ES data and running rebuild restores search.

### Phase 3: Image And Document Knowledge Parity

Deliverables:

- Image library route.
- OCR and vision indexing pipeline.
- Source detail expansion.
- Multi-knowledge-base ingestion.
- File asset metadata and retryable parse/index states.

Acceptance:

- Images can be uploaded, described, searched, cited, tagged, and favorited.
- Document and image failures are visible and retryable.

### Phase 4: Neo4j Memory Graph Parity

Deliverables:

- Neo4j connection, schema constraints, and projection layer.
- Structured LLM memory extraction.
- Entity, relation, event, provenance, and timeline graph.
- Graph rebuild command.
- Graph visualization backed by Neo4j queries.

Acceptance:

- Confirmed memories create graph nodes and relationships.
- Graph and timeline survive rebuild from PostgreSQL records.
- Provenance path is visible for graph claims.

### Phase 5: Agent, MCP, Skills, And Tools

Deliverables:

- Tool registry.
- MCP server config and discovery.
- Skill CRUD and prompt templates.
- Agent ReAct/function-calling loop.
- Approval policy for write-capable tools.
- Streaming run steps and durable logs.

Acceptance:

- Agent can search knowledge, query memory graph, run allowed MCP tools, and produce cited answers.
- Tool calls are logged and visible.
- Write-capable tools require approval when policy demands it.

### Phase 6: Research And Reports

Deliverables:

- Research task model and UI.
- Planner, retriever, curator, distiller, report generator.
- Report storage, search, and sharing.
- Worker-backed progress.

Acceptance:

- A research task completes asynchronously and produces a cited report.
- Report can be searched and shared.

### Phase 7: Persona And Group Chat

Deliverables:

- Persona profiles and persona groups.
- Group chat route.
- Host orchestration.
- Speaker prompts and persona memory policies.
- Join/share flow.

Acceptance:

- A group chat can run multiple personas with visible message provenance and user-scoped context.

### Phase 8: Comet Product Surface Completion

Deliverables:

- Dashboard parity.
- Notifications.
- Music library.
- Emotion module.
- Profile and share pages.
- Final route and README parity matrix.

Acceptance:

- Every Comet module family has a Lumen route, API, persisted model, and smoke flow.
- README no longer describes Lumen as a local prototype.

## Testing Strategy

Backend tests:

- repository user isolation
- auth flow
- ingestion jobs
- ES projection and search service with fake or test ES adapter where appropriate
- Neo4j projection and graph service with fake or test adapter where appropriate
- memory extraction parser and confirmation flow
- agent tool policy
- research task state machine
- rebuild commands

Frontend tests:

- protected routing
- knowledge-base selection
- search workflows
- memory graph workflows
- agent task panel
- research task panel
- user isolation in client state

Integration and smoke tests:

- full compose health
- upload and index source
- ask with citations
- create and confirm memory
- graph sync
- ES rebuild
- Neo4j rebuild
- agent tool run
- research report generation

## Security And Privacy

- All user data is scoped by authenticated user.
- Secrets are encrypted at rest.
- Logs redact common secret shapes.
- Agent tools receive only the scoped context they are allowed to use.
- Shared links are read-only and tokenized.
- Background jobs store user scope and validate ownership before mutating records.
- Rebuild commands require explicit operator action or admin-scoped API permissions.

## Documentation Updates

Each phase updates:

- README capability list
- environment setup
- Docker Compose service list
- smoke flow
- maintenance commands
- parity matrix status

The README should eventually present Lumen as a full AI knowledge and agent platform, not a local-first prototype.

## Phase Plan Decisions

These are resolved for this program:

- Elasticsearch and Neo4j are required in the target stack.
- Multi-user authentication is required.
- Agent, MCP, Skills, research, persona, group chat, music, emotion, notifications, and sharing are in scope.
- Existing Lumen data must be preserved through migration.

The following implementation choices must be made explicitly in the relevant phase plans:

- The first production embedding provider.
- Whether Ant Design is adopted directly or matched through existing components.
- Exact Neo4j constraint syntax and index names.
- Exact ES analyzer configuration for the local image.
- Exact JWT refresh-token storage strategy.

## Success Criteria

The program is complete when:

- Full stack starts with one Docker Compose command.
- Multiple users can use the app without data leakage.
- Knowledge retrieval uses real embedding, ES hybrid search, and reranking.
- Memory extraction is LLM-structured and graph-backed by Neo4j.
- Agent runs multi-step tool workflows with MCP and Skills support.
- Research tasks produce cited reports.
- Persona and group chat workflows are available.
- Image, search, favorites, tags, shares, dashboard, notifications, music, emotion, model config, profile, and status surfaces exist.
- Projection rebuilds work for ES and Neo4j.
- The README parity matrix shows every Comet module family as implemented or intentionally superseded by an equal or stronger Lumen workflow.
