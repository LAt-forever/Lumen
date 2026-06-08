export type SourceRead = {
  id: number
  title: string
  source_type: string
  status: string
  url: string | null
  filename: string | null
  error_message: string | null
  created_at: string
}

export type SourceDetailRead = SourceRead & {
  chunk_count: number
}

export type EvidenceMatch = {
  matched_terms: string[]
  matched_date: string | null
  match_reason: string
}

export type ChatResponse = {
  conversation_id: number
  message_id: number
  answer: string
  citations: Array<{ source_id: number; source_title: string; chunk_id: number; quote: string } & EvidenceMatch>
  memories: Array<{ id: number; text: string; memory_type: string }>
  confidence: string
  answer_mode: 'extractive' | 'llm'
  fallback_reason: string | null
}

export type RuntimeSettingsRead = {
  llm_mode: 'extractive' | 'llm'
  llm_provider: string
  llm_model: string | null
  llm_configured: boolean
  llm_fallback_enabled: boolean
  embedding_mode: string
  configuration_hint: string | null
  latest_fallback_reason: string | null
  runtime_source: 'environment' | 'database-profile'
  active_profile_id: number | null
  active_profile_name: string | null
}

export type LLMProviderProfileRead = {
  id: number
  name: string
  provider: string
  base_url: string
  model: string
  api_key_configured: boolean
  timeout_seconds: number
  fallback_enabled: boolean
  is_active: boolean
  status: 'untested' | 'ready' | 'failed'
  last_error: string | null
  last_checked_at: string | null
  created_at: string
  updated_at: string
}

export type LLMProviderProfileCreate = {
  name: string
  provider: string
  base_url: string
  model: string
  api_key?: string | null
  timeout_seconds: number
  fallback_enabled: boolean
  is_active: boolean
}

export type LLMProviderProfileUpdate = Partial<LLMProviderProfileCreate> & {
  clear_api_key?: boolean
}

export type ChunkRead = EvidenceMatch & {
  id: number
  source_id: number
  source_title: string
  text: string
  score: number
}

export type MemoryCandidateRead = {
  id: number
  text: string
  memory_type: string
  source_kind: string
  source_ref: string
  confidence: number
  status: string
  created_at: string
}

export type MemoryRead = {
  id: number
  text: string
  memory_type: string
  provenance: string
  status: string
  created_at: string
}

export type MemoryDuplicateSuggestionRead = {
  source_memory_id: number
  target_memory_id: number
  source_text: string
  target_text: string
  overlap_score: number
}

export type MemoryUpdate = {
  text: string
  memory_type: string
}

export type ReviewRead = {
  sources_added: SourceRead[]
  memories_confirmed: MemoryRead[]
  pending_memories: MemoryCandidateRead[]
  recent_questions: string[]
  suggested_actions: string[]
}
