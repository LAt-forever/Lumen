export type SourceType = 'note' | 'text' | 'markdown' | 'pdf' | 'image' | 'docx' | 'epub' | 'link' | 'bookmark' | 'web_crawl'

export type SourceRead = {
  id: number
  title: string
  source_type: SourceType
  status: string
  url: string | null
  filename: string | null
  error_message: string | null
  created_at: string
}

export interface BulkUploadResult {
  total: number
  succeeded: number
  failed: number
  sources: SourceRead[]
}

export type SourceDetailRead = SourceRead & {
  chunk_count: number
}

export type IngestionJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

export type IngestionJobType = 'note' | 'upload' | 'link' | 'crawl' | 'bookmark' | 'index' | 'retry'

export type IngestionJobRead = {
  id: number
  batch_id: string
  source_id: number | null
  source_title: string | null
  job_type: IngestionJobType
  status: IngestionJobStatus
  progress_current: number
  progress_total: number
  message: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export type IngestionJobCountsRead = Record<IngestionJobStatus, number>

export type IngestionBatchRead = {
  batch_id: string
  total: number
  queued: number
  running: number
  succeeded: number
  failed: number
  canceled: number
  jobs: IngestionJobRead[]
  sources: SourceRead[]
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
  runtime_source: 'environment' | 'database-profile' | 'extractive'
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

export type TargetType = 'source' | 'memory' | 'message'

export type TagRead = {
  id: number
  name: string
  color: string | null
  created_at: string
}

export type TagAssignmentRead = {
  id: number
  tag: TagRead
  target_type: TargetType
  target_id: number
  source: 'user' | 'ai-confirmed'
  created_at: string
}

export type TagSuggestionRead = {
  id: number
  label: string
  target_type: TargetType
  target_id: number
  reason: string
  confidence: number
  status: 'pending' | 'confirmed' | 'ignored'
  created_at: string
}

export type FavoriteRead = {
  id: number
  target_type: TargetType
  target_id: number
  created_at: string
}

export type GlobalSearchResultRead = EvidenceMatch & {
  result_type: 'source_chunk' | 'source' | 'memory' | 'message'
  target_id: number
  title: string
  snippet: string
  score: number
  tags: TagRead[]
  is_favorite: boolean
  created_at: string
}

export type ServiceHealthRead = {
  name: string
  label: string
  status: 'ok' | 'degraded' | 'unavailable' | 'not_configured'
  detail: string
  latency_ms: number | null
  checked_at: string
}

export type StatusSummaryRead = {
  runtime: RuntimeSettingsRead
  services: ServiceHealthRead[]
  source_counts: {
    total: number
    indexed: number
    failed: number
    pending: number
    parsing: number
  }
  ingestion_jobs: IngestionJobCountsRead
  failed_sources: Array<Pick<SourceRead, 'id' | 'title' | 'source_type' | 'error_message' | 'created_at'>>
  pending_tag_suggestion_count: number
  latest_fallback_reason: string | null
  suggested_actions: Array<{ label: string; target_view: string; target_id: number | null }>
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

export type RelationType = 'related_to' | 'part_of' | 'caused_by' | 'supports' | 'contradicts' | 'merged_into'

export type RelationStatus = 'active' | 'forgotten'

export type MemoryRelationRead = {
  id: number
  source_memory_id: number
  target_memory_id: number
  relation_type: RelationType
  provenance: string
  strength: number
  status: RelationStatus
  created_at: string
}

export type MemoryRelationCreate = {
  target_memory_id: number
  relation_type: RelationType
  provenance?: string
  strength?: number
}

export type MemoryGraphNode = {
  id: number
  text: string
  memory_type: string
  status: string
}

export type MemoryGraphEdge = {
  id: number
  source_memory_id: number
  target_memory_id: number
  relation_type: RelationType
  provenance: string
  strength: number
  status: RelationStatus
}

export type MemoryGraphRead = {
  center_memory_id: number
  nodes: MemoryGraphNode[]
  edges: MemoryGraphEdge[]
}

export type AgentToolName = 'global_search' | 'memory_search' | 'memory_graph'

export type AgentProfileRead = {
  id: number
  name: string
  instructions: string
  enabled_tools: AgentToolName[]
  require_approval: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export type AgentProfileCreate = {
  name: string
  instructions: string
  enabled_tools: AgentToolName[]
  require_approval: boolean
  is_active: boolean
}

export type AgentProfileUpdate = Partial<AgentProfileCreate>

export type AgentToolLogRead = {
  id: number
  profile_id: number | null
  tool_name: AgentToolName
  action: string
  input_json: string
  result_summary: string | null
  status: string
  error_message: string | null
  created_at: string
}

export type AgentRunResponse = {
  answer: string
  used_tools: AgentToolName[]
  search_results: GlobalSearchResultRead[]
  memories: MemoryRead[]
  graph: MemoryGraphRead | null
  tool_logs: AgentToolLogRead[]
}

export type RerankerProfileRead = {
  id: number
  name: string
  provider: string
  base_url: string | null
  model: string | null
  api_key_configured: boolean
  top_n: number
  is_active: boolean
  status: string
  last_error: string | null
  created_at: string
  updated_at: string
}

export type RerankerProfileCreate = {
  name: string
  provider: string
  base_url?: string | null
  model?: string | null
  api_key?: string | null
  top_n: number
  is_active: boolean
}

export type RerankerProfileUpdate = Partial<RerankerProfileCreate> & {
  clear_api_key?: boolean
}
