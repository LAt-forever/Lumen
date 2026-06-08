# Lumen Phase 1.4 Model Runtime UX Design Spec

Date: 2026-06-08

## Summary

Phase 1.4 turns Lumen's optional LLM support from environment-only configuration into a usable local runtime experience. It adds SQLite-backed provider profiles, safe connection diagnostics, and streaming chat while preserving the Phase 1.3 evidence-grounded answer contract.

The phase intentionally does not add agent tool routing. Lumen should first make model configuration, runtime status, and streamed answers dependable before it can safely execute tools.

## Product Scope

### SQLite-Backed Provider Profiles

Users can manage OpenAI-compatible provider profiles from Settings:

- create a provider profile
- edit profile name, base URL, model, timeout, and fallback behavior
- write, replace, or clear the API key
- activate one profile
- delete inactive profiles
- see whether an API key is configured without seeing the raw key

The active SQLite profile becomes the preferred model configuration. If no active profile exists, Lumen falls back to the existing environment-variable settings from Phase 1.2 and Phase 1.3.

### API Key Storage Boundary

Phase 1.4 stores API keys in local SQLite. This is an explicit local-first prototype tradeoff:

- the SQLite database file is the trust boundary
- local filesystem permissions protect the database
- Lumen does not encrypt API keys in this phase
- API responses never return raw API keys
- logs, test responses, settings payloads, and connection-test errors must not include raw API keys
- the Settings UI never displays a saved key; users can only replace or clear it

This design keeps the workflow convenient while making the risk visible.

### Connection Test

Users can test a provider profile from Settings. The backend sends a tiny OpenAI-compatible chat-completions request using that profile.

The test stores safe runtime state:

- `status`: `untested`, `ready`, or `failed`
- `last_error`: a short sanitized error summary
- `last_checked_at`: timestamp of the latest test

The UI displays the result and provides a next action when the active profile is missing a key, model, or base URL.

### Streaming Chat

Lumen adds a non-breaking streaming chat endpoint. The current `/api/chat` endpoint remains supported.

The streaming flow:

1. builds the same evidence pack as normal chat
2. refuses to stream unsupported answers when evidence is weak
3. streams answer text chunks from the active provider when possible
4. falls back to extractive behavior when configuration or provider calls fail and fallback is enabled
5. emits final metadata with conversation ID, message ID, citations, memories, confidence, answer mode, and fallback reason

The frontend can prefer streaming while keeping the existing non-streaming ask path as a fallback.

### Provider Boundary

Phase 1.4 extends the provider boundary without replacing it:

- `AnswerProvider.answer(evidence)` remains the non-streaming path
- streaming support is added as an optional provider capability
- provider construction reads the active SQLite profile first, then environment settings
- only the OpenAI-compatible contract is implemented in this phase

## Non-Goals

- no agent tool routing
- no autonomous multi-step task execution
- no tool permission model or tool approval UI
- no Ollama-specific adapter beyond OpenAI-compatible endpoints
- no provider marketplace
- no multi-user auth or per-user profile ownership
- no API key encryption or OS keychain integration
- no database migration framework
- no answer-quality dashboard

## Backend Design

### Data Model

Add a new SQLAlchemy model:

```text
LLMProviderProfile
- id: int
- name: str
- provider: str
- base_url: str
- model: str
- api_key: str | null
- timeout_seconds: float
- fallback_enabled: bool
- is_active: bool
- status: str
- last_error: str | null
- last_checked_at: datetime | null
- created_at: datetime
- updated_at: datetime
```

Because this is a new table, the existing `Base.metadata.create_all()` startup path can create it without a migration framework.

Only one profile may be active. The repository enforces this by deactivating all other profiles before marking a profile active.

### Schemas

Add safe public schemas:

```text
LLMProviderProfileRead
- id
- name
- provider
- base_url
- model
- api_key_configured
- timeout_seconds
- fallback_enabled
- is_active
- status
- last_error
- last_checked_at
- created_at
- updated_at

LLMProviderProfileCreate
- name
- provider
- base_url
- model
- api_key
- timeout_seconds
- fallback_enabled
- is_active

LLMProviderProfileUpdate
- name
- provider
- base_url
- model
- api_key
- clear_api_key
- timeout_seconds
- fallback_enabled
- is_active
```

`api_key` appears only in create/update request schemas. It never appears in response schemas.

### API Endpoints

Add read/write endpoints under `/api/settings/provider-profiles`:

```text
GET /api/settings/provider-profiles
POST /api/settings/provider-profiles
PATCH /api/settings/provider-profiles/{profile_id}
POST /api/settings/provider-profiles/{profile_id}/activate
POST /api/settings/provider-profiles/{profile_id}/test
DELETE /api/settings/provider-profiles/{profile_id}
```

Rules:

- deleting an active profile returns 400 unless another profile is activated first
- creating a profile with `is_active=true` deactivates all others
- updating with an empty `api_key` leaves the existing key unchanged
- updating with `clear_api_key=true` clears the saved key
- connection-test errors are sanitized before storage and response

### Runtime Settings Resolution

Provider construction resolves settings in this order:

1. active SQLite provider profile with a configured API key and model
2. existing environment variables
3. extractive fallback

`GET /api/settings/runtime` includes:

- source of runtime configuration: `database-profile`, `environment`, or `extractive`
- active profile ID and name when present
- existing non-secret metadata

### Connection Test Client

Reuse the OpenAI-compatible chat completions client. The test request sends a tiny prompt and expects non-empty text.

The connection test must not send user data or evidence chunks. It uses a fixed message such as:

```text
请只回复：ok
```

### Streaming Provider

Add a streaming client path for OpenAI-compatible APIs using the chat completions `stream=true` shape.

The streaming parser should consume Server-Sent Events lines:

```text
data: {"choices":[{"delta":{"content":"..."}}]}
data: [DONE]
```

The parser ignores malformed empty lines but treats invalid provider responses as a stream failure.

### Streaming API

Add:

```text
POST /api/chat/stream
```

The endpoint returns Server-Sent Events. Event names:

```text
event: chunk
data: {"text":"..."}

event: final
data: {ChatResponse JSON without raw secrets}

event: error
data: {"message":"..."}
```

If the backend falls back to extractive mode, it can stream the extractive answer as one chunk followed by `final`.

## Frontend Design

### Settings View

Settings becomes an operational model-control surface:

- runtime summary remains at the top
- provider profile list appears below it
- active profile is visually marked
- edit/create form sits inline in the Settings view
- API key input uses hint text such as `留空则不修改已保存密钥`
- clear key uses an explicit checkbox or button
- connection test button shows loading, success, or sanitized failure

The UI remains dense and work-focused. It should not become a marketing-style onboarding page.

### Chat Streaming UX

The existing chat panel stays. When streaming is available:

- clicking `询问 Lumen` shows a progressively growing answer
- answer metadata appears after the final event
- if streaming fails, the UI falls back to existing `/api/chat` and shows the fallback reason when available

No typing animation beyond actual streamed text is needed.

## Error Handling

- Missing profile returns 404.
- Deleting an active profile returns 400.
- Activating a profile without model or API key is allowed but runtime settings must show it is not usable.
- Connection-test failure stores a sanitized message and never stores response bodies that might contain secrets.
- Streaming transport failure falls back to non-streaming only when safe; otherwise it surfaces a readable Chinese error.
- Weak evidence never asks the model to invent an answer.

## Testing

Backend tests cover:

- profile create/list/read responses omit raw API key
- update without `api_key` preserves saved key
- `clear_api_key=true` clears saved key
- activation deactivates other profiles
- active SQLite profile overrides environment configuration
- no active profile falls back to environment configuration
- deleting active profile returns 400
- connection test stores ready/failed status without leaking secrets
- streaming SSE parser extracts content chunks
- streaming endpoint emits chunk and final events
- weak evidence does not call streaming provider

Frontend tests cover:

- Settings lists provider profiles without showing raw API keys
- creating and activating a provider profile calls the expected endpoints
- editing a profile can replace or clear the key
- connection test displays ready/failed state
- chat can render a streamed answer and final metadata
- streaming failure falls back to existing chat path

## Acceptance Criteria

Phase 1.4 is complete when:

- users can manage SQLite-backed provider profiles from Settings
- raw API keys are never returned to the frontend
- one active profile can drive normal LLM answers
- environment-variable configuration still works when no active profile exists
- provider connection tests are visible and safe
- chat supports streaming without breaking existing non-streaming tests
- agent tool routing remains out of scope
- backend tests pass
- frontend tests pass
- frontend production build succeeds

## Future Expansion

Phase 1.4 prepares for later provider-specific adapters, local model support, and agent tool routing. Agent routing should be designed as a separate phase with permissions, approvals, tool logs, and prompt-injection protections.
