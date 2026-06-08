# Lumen Phase 1.2 Evidence-Grounded Answers Design Spec

Date: 2026-06-08

## Summary

Phase 1.2 makes Lumen answer more like a personal AI assistant while keeping the local-first prototype simple. The app gains a provider adapter boundary for answers:

- `extractive` remains the default and still works without model credentials.
- `llm` becomes an optional mode enabled by environment variables.
- LLM answers must be grounded in retrieved source chunks and confirmed memories.
- If the LLM is not configured, fails, or evidence is too weak, Lumen falls back to the existing extractive answer path.

This phase is intentionally the simplest useful version of model-backed answers. It prepares the architecture for later provider selection, streaming, local models, and agent tools without implementing those larger features now.

## Product Scope

### Evidence-Grounded Answers

When the user asks a question, Lumen builds an evidence pack before generating an answer:

- the user question
- top retrieved chunks with source titles and citation IDs
- recalled active memories
- confidence from the retrieval result

The answer provider receives this evidence pack and returns:

- answer text in Chinese
- answer mode, such as `extractive` or `llm`
- confidence, preserving the existing values `grounded`, `memory-only`, and `weak`
- a fallback reason when a fallback occurred

LLM mode must not answer from general knowledge when there is no supporting source or memory evidence. If evidence is weak, the answer should say Lumen does not have enough evidence and suggest adding or confirming relevant information.

### Optional LLM Configuration

The backend reads model configuration from environment variables:

- `LUMEN_LLM_MODE`: `extractive` or `llm`
- `LUMEN_LLM_PROVIDER`: initially `openai-compatible`
- `LUMEN_LLM_BASE_URL`: optional base URL for OpenAI-compatible APIs
- `LUMEN_LLM_MODEL`: model name
- `LUMEN_LLM_API_KEY`: API key
- `LUMEN_LLM_TIMEOUT_SECONDS`: request timeout
- `LUMEN_LLM_FALLBACK_ENABLED`: whether to use extractive fallback after LLM failure

The default configuration remains credential-free:

```text
LUMEN_LLM_MODE=extractive
```

### Settings Visibility

The Settings view shows the current runtime answer configuration:

- answer mode
- provider name
- model name, when configured
- whether an API key is present
- whether fallback is enabled
- short Chinese copy explaining that keys are read from local environment variables

The Settings view does not allow editing or storing API keys in Phase 1.2.

## Non-Goals

- no streaming chat
- no model configuration form
- no database storage for model credentials
- no provider marketplace or multi-provider switching UI
- no local Ollama integration unless it is reachable through the same OpenAI-compatible contract
- no agent tool routing
- no autonomous multi-step tasks
- no answer quality evaluation dashboard

## Backend Design

### Answer Provider Boundary

`service.core.llm` becomes the home for a small answer provider interface:

```text
AnswerProvider.answer(evidence_pack) -> AnswerResult
```

The existing `ExtractiveAnswerProvider` is adapted to the same interface. A new `OpenAICompatibleAnswerProvider` handles optional model-backed answers using the OpenAI-compatible chat completions shape.

Provider construction stays outside the orchestrator. The API layer or a small factory chooses the provider from settings:

```text
extractive -> ExtractiveAnswerProvider
llm + complete config -> OpenAICompatibleAnswerProvider with extractive fallback
llm + missing config -> ExtractiveAnswerProvider with visible fallback reason
```

### Evidence Pack

The evidence pack is a typed internal object, not a database table. It contains enough structured context for both extractive and LLM providers:

```text
question
chunks: id, source_id, source_title, text, score
memories: id, text, memory_type
retrieval_confidence
```

The orchestrator still stores messages and citations exactly as Phase 1.1 does. Phase 1.2 changes answer generation, not the conversation schema.

### LLM Prompt Contract

The LLM prompt must be strict and short:

- answer in Chinese
- only use provided sources and memories
- cite uncertainty when evidence is incomplete
- do not invent facts, dates, sources, or user preferences
- prefer a concise answer, then supporting details when useful

The provider does not need citation markup in the model output. The existing API response continues to return structured citations separately.

### Fallback Behavior

Fallback is part of normal behavior, not an error:

- missing API key in `llm` mode falls back to extractive mode
- timeout or HTTP failure falls back when `LUMEN_LLM_FALLBACK_ENABLED=true`
- weak evidence uses the weak answer path instead of asking the model to guess

The chat response includes answer metadata so the UI can show whether the answer came from LLM mode or fallback.

### Runtime Settings Endpoint

Add a read-only backend endpoint:

```text
GET /api/settings/runtime
```

It returns safe runtime metadata only. It must never return the raw API key.

## Frontend Design

The frontend keeps the Phase 1.1 layout. The main visible changes are:

- Chat panel shows whether the answer used LLM mode or extractive mode.
- Context panel can show a concise fallback reason when present.
- Settings panel fetches runtime metadata from the backend instead of hardcoding answer mode copy.

All visible copy remains Chinese.

## API Shape

Extend `ChatResponse` with optional metadata:

```text
answer_mode: "extractive" | "llm"
fallback_reason: string | null
```

Add runtime settings response:

```text
{
  "llm_mode": "extractive" | "llm",
  "llm_provider": "openai-compatible",
  "llm_model": string | null,
  "llm_configured": boolean,
  "llm_fallback_enabled": boolean,
  "embedding_mode": string
}
```

Existing Phase 1.1 clients can ignore the added chat fields.

## Testing

Backend tests cover:

- extractive mode still answers without credentials
- LLM mode uses a fake OpenAI-compatible client when evidence is grounded
- weak evidence does not ask the LLM to invent an answer
- missing LLM config falls back to extractive mode
- provider HTTP failure falls back when fallback is enabled
- runtime settings endpoint omits secrets

Frontend tests cover:

- Settings view displays runtime answer mode and model configuration status
- Chat view displays LLM mode metadata
- Chat view displays fallback metadata when the backend reports it
- existing Phase 1.1 source, search, memory, and review tests still pass

## Future Expansion

This design deliberately leaves room for more complex later phases:

- editable provider settings in the UI
- multiple provider profiles
- OpenAI-specific and local-model-specific adapters
- streaming chat
- answer quality evaluation sets
- citation-aware reranking
- agent tool routing

Those features should build on the same provider boundary and evidence pack rather than replacing them.

## Acceptance Criteria

Phase 1.2 is complete when:

- the app still runs with no model credentials in extractive mode
- `LUMEN_LLM_MODE=llm` can use a configured OpenAI-compatible chat model
- LLM answers are generated only when source or memory evidence exists
- missing config or provider failure has a visible fallback path
- Settings shows safe runtime model status without exposing secrets
- backend tests pass
- frontend tests pass
- frontend production build succeeds
