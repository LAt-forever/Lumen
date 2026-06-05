import type { ChatResponse, MemoryCandidateRead, ReviewRead, SourceRead } from './types'

const viteEnv = (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
const API_BASE = viteEnv?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
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
  indexSource: (sourceId: number) => request<SourceRead>(`/api/sources/${sourceId}/index`, { method: 'POST' }),
  ask: (message: string, conversationId?: number) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
  pendingMemories: () => request<MemoryCandidateRead[]>('/api/memories/candidates'),
  confirmMemory: (candidateId: number, payload: { text: string; memory_type: string }) =>
    request(`/api/memories/candidates/${candidateId}/confirm`, { method: 'POST', body: JSON.stringify(payload) }),
  ignoreMemory: (candidateId: number) =>
    request(`/api/memories/candidates/${candidateId}/ignore`, { method: 'POST' }),
  review: () => request<ReviewRead>('/api/review'),
}
