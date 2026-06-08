import type {
  ChatResponse,
  ChunkRead,
  LLMProviderProfileCreate,
  LLMProviderProfileRead,
  LLMProviderProfileUpdate,
  MemoryCandidateRead,
  MemoryDuplicateSuggestionRead,
  MemoryRead,
  MemoryUpdate,
  ReviewRead,
  RuntimeSettingsRead,
  SourceDetailRead,
  SourceRead,
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
  uploadSource: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<SourceRead>('/api/sources/upload', { method: 'POST', body })
  },
  captureLink: (url: string) =>
    request<SourceRead>('/api/sources/link', { method: 'POST', body: JSON.stringify({ url }) }),
  indexSource: (sourceId: number) => request<SourceRead>(`/api/sources/${sourceId}/index`, { method: 'POST' }),
  deleteSource: (sourceId: number) => request<void>(`/api/sources/${sourceId}`, { method: 'DELETE' }),
  search: (query: string) => request<ChunkRead[]>(`/api/search?${new URLSearchParams({ q: query }).toString()}`),
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
  runtimeSettings: () => request<RuntimeSettingsRead>('/api/settings/runtime'),
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
}
