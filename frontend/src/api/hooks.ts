import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  ChatResponse,
  ChunkRead,
  MemoryCandidateRead,
  MemoryDuplicateSuggestionRead,
  MemoryRead,
  MemoryUpdate,
  ReviewRead,
  RuntimeSettingsRead,
  SourceDetailRead,
  SourceRead,
} from './types'

export function useSources() {
  return useQuery<SourceRead[]>({ queryKey: ['sources'], queryFn: () => api.listSources() as Promise<SourceRead[]> })
}

export function useSourceDetail(sourceId?: number) {
  return useQuery<SourceDetailRead>({
    queryKey: ['sources', sourceId],
    queryFn: () => api.getSource(sourceId as number),
    enabled: typeof sourceId === 'number',
  })
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

async function indexIfPending(source: SourceRead) {
  if (source.status === 'pending') {
    await api.indexSource(source.id)
  }
}

function useSourceCaptureMutation<TInput>(mutationFn: (input: TInput) => Promise<SourceRead>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async (source) => {
      await indexIfPending(source)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useUploadSource() {
  return useSourceCaptureMutation<File>(api.uploadSource)
}

export function useCaptureLink() {
  return useSourceCaptureMutation<string>(api.captureLink)
}

export function useIndexSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.indexSource,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useDeleteSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deleteSource,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['search'] })
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

export function useSearch(query: string) {
  return useQuery<ChunkRead[]>({
    queryKey: ['search', query],
    queryFn: () => api.search(query),
    enabled: query.trim().length > 0,
  })
}

export function usePendingMemories() {
  return useQuery<MemoryCandidateRead[]>({
    queryKey: ['memories', 'pending'],
    queryFn: () => api.pendingMemories() as Promise<MemoryCandidateRead[]>,
  })
}

export function useMemories() {
  return useQuery<MemoryRead[]>({
    queryKey: ['memories', 'active'],
    queryFn: () => api.listMemories(),
  })
}

export function useConfirmMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (candidate: MemoryCandidateRead) =>
      api.confirmMemory(candidate.id, { text: candidate.text, memory_type: candidate.memory_type }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'pending'] })
      await queryClient.invalidateQueries({ queryKey: ['memories', 'active'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useIgnoreMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (candidateId: number) => api.ignoreMemory(candidateId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'pending'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useUpdateMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, payload }: { memoryId: number; payload: MemoryUpdate }) => api.updateMemory(memoryId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'active'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useForgetMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.forgetMemory,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'active'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useMergeMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, targetMemoryId }: { memoryId: number; targetMemoryId: number }) => api.mergeMemory(memoryId, targetMemoryId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'active'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useDuplicateMemorySuggestions() {
  return useQuery<MemoryDuplicateSuggestionRead[]>({
    queryKey: ['memories', 'duplicates'],
    queryFn: () => api.duplicateMemorySuggestions(),
  })
}

export function useReview() {
  return useQuery<ReviewRead>({ queryKey: ['review'], queryFn: () => api.review() as Promise<ReviewRead> })
}

export function useRuntimeSettings() {
  return useQuery<RuntimeSettingsRead>({
    queryKey: ['settings', 'runtime'],
    queryFn: () => api.runtimeSettings(),
  })
}
