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

export type ChatResponse = {
  conversation_id: number
  message_id: number
  answer: string
  citations: Array<{ source_id: number; source_title: string; chunk_id: number; quote: string }>
  memories: Array<{ id: number; text: string; memory_type: string }>
  confidence: string
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

export type ReviewRead = {
  sources_added: SourceRead[]
  memories_confirmed: MemoryRead[]
  pending_memories: MemoryCandidateRead[]
  recent_questions: string[]
  suggested_actions: string[]
}
