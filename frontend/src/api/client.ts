import type {
  ChatResponse,
  ChunkRead,
  AgentProfileCreate,
  AgentProfileRead,
  AgentProfileUpdate,
  AgentRunResponse,
  AgentToolLogRead,
  FavoriteRead,
  GlobalSearchResultRead,
  IngestionBatchRead,
  IngestionJobRead,
  LLMProviderProfileCreate,
  LLMProviderProfileRead,
  LLMProviderProfileUpdate,
  MemoryCandidateRead,
  MemoryDuplicateSuggestionRead,
  MemoryGraphRead,
  MemoryRead,
  MemoryRelationCreate,
  MemoryRelationRead,
  MemoryUpdate,
  ReviewRead,
  RuntimeSettingsRead,
  RerankerProfileCreate,
  RerankerProfileRead,
  RerankerProfileUpdate,
  SourceDetailRead,
  BulkUploadResult,
  SourceRead,
  StatusSummaryRead,
  TagAssignmentRead,
  TagRead,
  TagSuggestionRead,
  TargetType,
} from './types'

const viteEnv = (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
export const API_BASE = viteEnv?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

type ChatStreamHandlers = {
  onChunk?: (text: string) => void
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    headers: isFormData ? init?.headers : { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    method: init?.method ?? 'GET',
    ...init,
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

async function readChatStream(response: Response, handlers: ChatStreamHandlers): Promise<ChatResponse> {
  if (!response.body) {
    throw new Error('Streaming response body unavailable')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResponse: ChatResponse | undefined

  const dispatchEvent = (eventText: string) => {
    const lines = eventText.split(/\r?\n/)
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice('event:'.length).trim()
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trimStart())
      }
    }
    if (dataLines.length === 0) return
    const payload = JSON.parse(dataLines.join('\n'))
    if (eventName === 'chunk' && typeof payload.text === 'string') {
      handlers.onChunk?.(payload.text)
    }
    if (eventName === 'final') {
      finalResponse = payload as ChatResponse
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() ?? ''
    for (const eventText of events) {
      if (eventText.trim()) {
        dispatchEvent(eventText)
      }
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    dispatchEvent(buffer)
  }
  if (!finalResponse) {
    throw new Error('Streaming response did not include a final event')
  }
  return finalResponse
}

export const api = {
  listSources: () => request<SourceRead[]>('/api/sources'),
  getSource: (sourceId: number) => request<SourceDetailRead>(`/api/sources/${sourceId}`),
  createSource: (payload: { title: string; source_type: 'note'; content: string }) =>
    request<SourceRead>('/api/sources', { method: 'POST', body: JSON.stringify(payload) }),
  createIngestionNote: (payload: { title: string; source_type: 'note'; content: string }) =>
    request<IngestionBatchRead>('/api/ingestion-jobs/notes', { method: 'POST', body: JSON.stringify(payload) }),
  uploadIngestionSources: (files: File[]) => {
    const body = new FormData()
    files.forEach((f) => body.append('files', f))
    return request<IngestionBatchRead>('/api/ingestion-jobs/uploads', { method: 'POST', body })
  },
  crawlIngestionWeb: (payload: { url: string; max_depth: number; max_pages: number; same_domain_only: boolean }) =>
    request<IngestionBatchRead>('/api/ingestion-jobs/crawls', { method: 'POST', body: JSON.stringify(payload) }),
  importIngestionBookmarks: (htmlContent: string) =>
    request<IngestionBatchRead>('/api/ingestion-jobs/bookmarks', {
      method: 'POST',
      body: JSON.stringify({ html_content: htmlContent }),
    }),
  captureIngestionLink: (url: string) =>
    request<IngestionBatchRead>('/api/ingestion-jobs/links', { method: 'POST', body: JSON.stringify({ url }) }),
  listIngestionJobs: (params: { status?: string; batch_id?: string; limit?: number } = {}) => {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    if (params.batch_id) search.set('batch_id', params.batch_id)
    if (params.limit) search.set('limit', String(params.limit))
    const suffix = search.toString() ? `?${search.toString()}` : ''
    return request<IngestionJobRead[]>(`/api/ingestion-jobs${suffix}`)
  },
  cancelIngestionJob: (jobId: number) =>
    request<IngestionJobRead>(`/api/ingestion-jobs/${jobId}/cancel`, { method: 'POST' }),
  retryIngestionJob: (jobId: number) =>
    request<IngestionBatchRead>(`/api/ingestion-jobs/${jobId}/retry`, { method: 'POST' }),
  uploadSources: (files: File[]) => {
    const body = new FormData()
    files.forEach((f) => body.append('files', f))
    return request<BulkUploadResult>('/api/sources/upload', { method: 'POST', body })
  },
  crawlWeb: (payload: { url: string; max_depth: number; max_pages: number; same_domain_only: boolean }) =>
    request<SourceRead>('/api/sources/crawl', { method: 'POST', body: JSON.stringify(payload) }),
  importBookmarks: (htmlContent: string) =>
    request<BulkUploadResult>('/api/sources/bookmarks', {
      method: 'POST',
      body: JSON.stringify({ html_content: htmlContent }),
    }),
  captureLink: (url: string) =>
    request<SourceRead>('/api/sources/link', { method: 'POST', body: JSON.stringify({ url }) }),
  indexSource: (sourceId: number) => request<SourceRead>(`/api/sources/${sourceId}/index`, { method: 'POST' }),
  retrySource: (sourceId: number) => request<SourceDetailRead>(`/api/sources/${sourceId}/retry`, { method: 'POST' }),
  deleteSource: (sourceId: number) => request<void>(`/api/sources/${sourceId}`, { method: 'DELETE' }),
  search: (query: string) => request<ChunkRead[]>(`/api/search?${new URLSearchParams({ q: query }).toString()}`),
  globalSearch: (params: { q: string; types?: string; tag?: string; favorite?: boolean }) => {
    const search = new URLSearchParams({ q: params.q })
    if (params.types) search.set('types', params.types)
    if (params.tag) search.set('tag', params.tag)
    if (params.favorite) search.set('favorite', 'true')
    return request<GlobalSearchResultRead[]>(`/api/global-search?${search.toString()}`)
  },
  ask: (message: string, conversationId?: number) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
  askStream: async (message: string, handlers: ChatStreamHandlers = {}, conversationId?: number) => {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    })
    if (!response.ok) {
      throw new Error(await response.text())
    }
    return readChatStream(response, handlers)
  },
  pendingMemories: () => request<MemoryCandidateRead[]>('/api/memories/candidates'),
  listMemories: () => request<MemoryRead[]>('/api/memories'),
  confirmMemory: (candidateId: number, payload: { text: string; memory_type: string }) =>
    request<MemoryRead>(`/api/memories/candidates/${candidateId}/confirm`, { method: 'POST', body: JSON.stringify(payload) }),
  ignoreMemory: (candidateId: number) =>
    request<{ status: string }>(`/api/memories/candidates/${candidateId}/ignore`, { method: 'POST' }),
  updateMemory: (memoryId: number, payload: MemoryUpdate) =>
    request<MemoryRead>(`/api/memories/${memoryId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  forgetMemory: (memoryId: number) => request<MemoryRead>(`/api/memories/${memoryId}/forget`, { method: 'POST' }),
  mergeMemory: (memoryId: number, targetMemoryId: number) =>
    request<MemoryRead>(`/api/memories/${memoryId}/merge`, { method: 'POST', body: JSON.stringify({ target_memory_id: targetMemoryId }) }),
  duplicateMemorySuggestions: () => request<MemoryDuplicateSuggestionRead[]>('/api/memories/duplicate-suggestions'),
  review: () => request<ReviewRead>('/api/review'),
  listTags: () => request<TagRead[]>('/api/tags'),
  createTag: (payload: { name: string; color?: string | null }) =>
    request<TagRead>('/api/tags', { method: 'POST', body: JSON.stringify(payload) }),
  assignTag: (payload: { tag_id: number; target_type: TargetType; target_id: number }) =>
    request<TagAssignmentRead>('/api/tags/assignments', { method: 'POST', body: JSON.stringify(payload) }),
  deleteTagAssignment: (assignmentId: number) =>
    request<void>(`/api/tags/assignments/${assignmentId}`, { method: 'DELETE' }),
  listTagSuggestions: () => request<TagSuggestionRead[]>('/api/tag-suggestions'),
  confirmTagSuggestion: (suggestionId: number) =>
    request<TagAssignmentRead>(`/api/tag-suggestions/${suggestionId}/confirm`, { method: 'POST' }),
  ignoreTagSuggestion: (suggestionId: number) =>
    request<TagSuggestionRead>(`/api/tag-suggestions/${suggestionId}/ignore`, { method: 'POST' }),
  listFavorites: () => request<FavoriteRead[]>('/api/favorites'),
  favorite: (payload: { target_type: TargetType; target_id: number }) =>
    request<FavoriteRead>('/api/favorites', { method: 'POST', body: JSON.stringify(payload) }),
  unfavorite: (targetType: TargetType, targetId: number) =>
    request<void>(`/api/favorites/${targetType}/${targetId}`, { method: 'DELETE' }),
  runtimeSettings: () => request<RuntimeSettingsRead>('/api/settings/runtime'),
  status: () => request<StatusSummaryRead>('/api/status'),
  listProviderProfiles: () => request<LLMProviderProfileRead[]>('/api/settings/provider-profiles'),
  createProviderProfile: (payload: LLMProviderProfileCreate) =>
    request<LLMProviderProfileRead>('/api/settings/provider-profiles', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateProviderProfile: (profileId: number, payload: LLMProviderProfileUpdate) =>
    request<LLMProviderProfileRead>(`/api/settings/provider-profiles/${profileId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  activateProviderProfile: (profileId: number) =>
    request<LLMProviderProfileRead>(`/api/settings/provider-profiles/${profileId}/activate`, { method: 'POST' }),
  testProviderProfile: (profileId: number) =>
    request<LLMProviderProfileRead>(`/api/settings/provider-profiles/${profileId}/test`, { method: 'POST' }),
  deleteProviderProfile: (profileId: number) =>
    request<void>(`/api/settings/provider-profiles/${profileId}`, { method: 'DELETE' }),

  listMemoryRelations: (memoryId: number) =>
    request<MemoryRelationRead[]>(`/api/memories/${memoryId}/relations`),

  createMemoryRelation: (memoryId: number, payload: MemoryRelationCreate) =>
    request<MemoryRelationRead>(`/api/memories/${memoryId}/relations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  forgetMemoryRelation: (memoryId: number, relationId: number) =>
    request<MemoryRelationRead>(`/api/memories/${memoryId}/relations/${relationId}/forget`, { method: 'POST' }),

  memoryGraph: (memoryId: number, depth = 2) =>
    request<MemoryGraphRead>(`/api/memories/${memoryId}/graph?depth=${depth}`),

  memoryHubGraph: (limit = 5) =>
    request<MemoryGraphRead>(`/api/memories/graph/hubs?limit=${limit}`),

  promoteDuplicateToRelation: (sourceMemoryId: number, targetMemoryId: number) =>
    request<MemoryRelationRead>(`/api/memories/duplicate-suggestions/${sourceMemoryId}/${targetMemoryId}/relate`, {
      method: 'POST',
    }),

  listAgentProfiles: () => request<AgentProfileRead[]>('/api/agent/profiles'),
  createAgentProfile: (payload: AgentProfileCreate) =>
    request<AgentProfileRead>('/api/agent/profiles', { method: 'POST', body: JSON.stringify(payload) }),
  updateAgentProfile: (profileId: number, payload: AgentProfileUpdate) =>
    request<AgentProfileRead>(`/api/agent/profiles/${profileId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  activateAgentProfile: (profileId: number) =>
    request<AgentProfileRead>(`/api/agent/profiles/${profileId}/activate`, { method: 'POST' }),
  runAgent: (message: string) =>
    request<AgentRunResponse>('/api/agent/runs', { method: 'POST', body: JSON.stringify({ message }) }),
  listAgentToolLogs: () => request<AgentToolLogRead[]>('/api/agent/tool-logs'),
  listRerankerProfiles: () => request<RerankerProfileRead[]>('/api/agent/reranker-profiles'),
  createRerankerProfile: (payload: RerankerProfileCreate) =>
    request<RerankerProfileRead>('/api/agent/reranker-profiles', { method: 'POST', body: JSON.stringify(payload) }),
  updateRerankerProfile: (profileId: number, payload: RerankerProfileUpdate) =>
    request<RerankerProfileRead>(`/api/agent/reranker-profiles/${profileId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  activateRerankerProfile: (profileId: number) =>
    request<RerankerProfileRead>(`/api/agent/reranker-profiles/${profileId}/activate`, { method: 'POST' }),
}
