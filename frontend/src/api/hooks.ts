import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  BulkUploadResult,
  ChatResponse,
  ChunkRead,
  FavoriteRead,
  GlobalSearchResultRead,
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
  SourceDetailRead,
  SourceRead,
  StatusSummaryRead,
  TagAssignmentRead,
  TagRead,
  TagSuggestionRead,
  TargetType,
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

export function useUploadSources() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.uploadSources,
    onSuccess: async (result: BulkUploadResult) => {
      for (const source of result.sources) {
        if (source.status === 'pending') await api.indexSource(source.id)
      }
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useUploadSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const result = await api.uploadSources([file])
      return result.sources[0] as SourceRead
    },
    onSuccess: async (source: SourceRead) => {
      await indexIfPending(source)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useCaptureLink() {
  return useSourceCaptureMutation<string>(api.captureLink)
}

export function useCrawlWeb() {
  return useSourceCaptureMutation<{
    url: string
    max_depth: number
    max_pages: number
    same_domain_only: boolean
  }>(api.crawlWeb)
}

export function useImportBookmarks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.importBookmarks,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
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

export function useRetrySource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.retrySource,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['source'] })
      await queryClient.invalidateQueries({ queryKey: ['global-search'] })
      await queryClient.invalidateQueries({ queryKey: ['status'] })
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

export function useAskLumenStream() {
  const queryClient = useQueryClient()
  return useMutation<ChatResponse, Error, { message: string; onChunk: (text: string) => void }>({
    mutationFn: ({ message, onChunk }) => api.askStream(message, { onChunk }) as Promise<ChatResponse>,
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

export function useGlobalSearch(params: { query: string; type: string; tag: string; favorite: boolean }) {
  const types = params.type === 'all' ? undefined : params.type === 'source' ? 'source,source_chunk' : params.type
  return useQuery<GlobalSearchResultRead[]>({
    queryKey: ['global-search', params],
    queryFn: () =>
      api.globalSearch({
        q: params.query,
        types,
        tag: params.tag || undefined,
        favorite: params.favorite,
      }),
    enabled: params.query.trim().length > 0,
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

export function useTags() {
  return useQuery<TagRead[]>({ queryKey: ['tags'], queryFn: () => api.listTags() })
}

export function useTagSuggestions() {
  return useQuery<TagSuggestionRead[]>({ queryKey: ['tag-suggestions'], queryFn: () => api.listTagSuggestions() })
}

function useOrganizationMutation<TInput, TResult>(mutationFn: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['tags'] })
      await queryClient.invalidateQueries({ queryKey: ['tag-suggestions'] })
      await queryClient.invalidateQueries({ queryKey: ['favorites'] })
      await queryClient.invalidateQueries({ queryKey: ['global-search'] })
      await queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

export function useCreateTag() {
  return useOrganizationMutation<{ name: string; color?: string | null }, TagRead>(api.createTag)
}

export function useAssignTag() {
  return useOrganizationMutation<{ tag_id: number; target_type: TargetType; target_id: number }, TagAssignmentRead>(api.assignTag)
}

export function useConfirmTagSuggestion() {
  return useOrganizationMutation<number, TagAssignmentRead>(api.confirmTagSuggestion)
}

export function useIgnoreTagSuggestion() {
  return useOrganizationMutation<number, TagSuggestionRead>(api.ignoreTagSuggestion)
}

export function useFavorites() {
  return useQuery<FavoriteRead[]>({ queryKey: ['favorites'], queryFn: () => api.listFavorites() })
}

export function useFavoriteTarget() {
  return useOrganizationMutation<{ target_type: TargetType; target_id: number }, FavoriteRead>(api.favorite)
}

export function useUnfavoriteTarget() {
  return useOrganizationMutation<{ target_type: TargetType; target_id: number }, void>(({ target_type, target_id }) =>
    api.unfavorite(target_type, target_id),
  )
}

export function useStatusSummary() {
  return useQuery<StatusSummaryRead>({ queryKey: ['status'], queryFn: () => api.status() })
}

export function useRuntimeSettings() {
  return useQuery<RuntimeSettingsRead>({
    queryKey: ['settings', 'runtime'],
    queryFn: () => api.runtimeSettings(),
  })
}

function useProviderProfileMutation<TInput>(mutationFn: (input: TInput) => Promise<LLMProviderProfileRead | void>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['settings', 'provider-profiles'] })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'runtime'] })
    },
  })
}

export function useProviderProfiles() {
  return useQuery<LLMProviderProfileRead[]>({
    queryKey: ['settings', 'provider-profiles'],
    queryFn: () => api.listProviderProfiles(),
  })
}

export function useCreateProviderProfile() {
  return useProviderProfileMutation<LLMProviderProfileCreate>(api.createProviderProfile)
}

export function useUpdateProviderProfile() {
  return useProviderProfileMutation<{ profileId: number; payload: LLMProviderProfileUpdate }>(({ profileId, payload }) =>
    api.updateProviderProfile(profileId, payload),
  )
}

export function useActivateProviderProfile() {
  return useProviderProfileMutation<number>(api.activateProviderProfile)
}

export function useTestProviderProfile() {
  return useProviderProfileMutation<number>(api.testProviderProfile)
}

export function useDeleteProviderProfile() {
  return useProviderProfileMutation<number>(api.deleteProviderProfile)
}

export function useMemoryRelations(memoryId?: number) {
  return useQuery<MemoryRelationRead[]>({
    queryKey: ['memory-relations', memoryId],
    queryFn: () => api.listMemoryRelations(memoryId as number),
    enabled: typeof memoryId === 'number',
  })
}

export function useCreateMemoryRelation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, payload }: { memoryId: number; payload: MemoryRelationCreate }) =>
      api.createMemoryRelation(memoryId, payload),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['memory-relations', variables.memoryId] })
      await queryClient.invalidateQueries({ queryKey: ['memory-graph'] })
    },
  })
}

export function useForgetMemoryRelation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, relationId }: { memoryId: number; relationId: number }) =>
      api.forgetMemoryRelation(memoryId, relationId),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['memory-relations', variables.memoryId] })
      await queryClient.invalidateQueries({ queryKey: ['memory-graph'] })
    },
  })
}

export function useMemoryGraph(memoryId?: number, depth = 2) {
  return useQuery<MemoryGraphRead>({
    queryKey: ['memory-graph', memoryId, depth],
    queryFn: () => api.memoryGraph(memoryId as number, depth),
    enabled: typeof memoryId === 'number',
  })
}

export function usePromoteDuplicateToRelation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceMemoryId, targetMemoryId }: { sourceMemoryId: number; targetMemoryId: number }) =>
      api.promoteDuplicateToRelation(sourceMemoryId, targetMemoryId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memories', 'duplicates'] })
      await queryClient.invalidateQueries({ queryKey: ['memory-graph'] })
    },
  })
}
