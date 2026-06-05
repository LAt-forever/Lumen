import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { ChatResponse, MemoryCandidateRead, ReviewRead, SourceRead } from './types'

export function useSources() {
  return useQuery<SourceRead[]>({ queryKey: ['sources'], queryFn: () => api.listSources() as Promise<SourceRead[]> })
}

export function useCreateSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.createSource,
    onSuccess: async (source: unknown) => {
      const created = source as SourceRead
      await api.indexSource(created.id)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useAskLumen() {
  const queryClient = useQueryClient()
  return useMutation<ChatResponse, Error, string>({
    mutationFn: (message) => api.ask(message) as Promise<ChatResponse>,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'pending'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function usePendingMemories() {
  return useQuery<MemoryCandidateRead[]>({
    queryKey: ['memories', 'pending'],
    queryFn: () => api.pendingMemories() as Promise<MemoryCandidateRead[]>,
  })
}

export function useReview() {
  return useQuery<ReviewRead>({ queryKey: ['review'], queryFn: () => api.review() as Promise<ReviewRead> })
}
