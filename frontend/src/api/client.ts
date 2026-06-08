import type { ChatResponse, ChunkRead, MemoryCandidateRead, MemoryRead, MemoryUpdate, ReviewRead, SourceRead } from './types'

const viteEnv = (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
export const API_BASE = viteEnv?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    headers: isFormData ? init?.headers : { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

export const api = {
  listSources: () => request<SourceRead[]>('/api/sources'),
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
  search: (query: string) => request<ChunkRead[]>(`/api/search?${new URLSearchParams({ q: query }).toString()}`),
  ask: (message: string, conversationId?: number) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
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
  review: () => request<ReviewRead>('/api/review'),
}
