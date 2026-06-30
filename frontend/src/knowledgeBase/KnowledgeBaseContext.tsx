import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react'

import { useKnowledgeBases } from '../api/hooks'
import type { KnowledgeBaseRead } from '../api/types'

const ACTIVE_KB_KEY = 'lumen.activeKnowledgeBaseId'

export function clearActiveKnowledgeBaseSelection() {
  window.localStorage.removeItem(ACTIVE_KB_KEY)
}

type KnowledgeBaseContextValue = {
  knowledgeBases: KnowledgeBaseRead[]
  activeKnowledgeBases: KnowledgeBaseRead[]
  archivedKnowledgeBases: KnowledgeBaseRead[]
  activeKnowledgeBaseId: number | null
  activeKnowledgeBase: KnowledgeBaseRead | null
  setActiveKnowledgeBaseId: (id: number | null) => void
  isLoading: boolean
}

const KnowledgeBaseContext = createContext<KnowledgeBaseContextValue | undefined>(undefined)

function readStoredKnowledgeBaseId() {
  const stored = window.localStorage.getItem(ACTIVE_KB_KEY)
  if (!stored) return null
  const parsed = Number(stored)
  return Number.isFinite(parsed) ? parsed : null
}

export function KnowledgeBaseProvider({ children }: { children: ReactNode }) {
  const { data, isFetched, isLoading } = useKnowledgeBases()
  const knowledgeBases = data ?? []
  const [activeKnowledgeBaseId, setActiveKnowledgeBaseIdState] = useState<number | null>(() => readStoredKnowledgeBaseId())

  const activeKnowledgeBases = useMemo(() => knowledgeBases.filter((kb) => kb.status === 'active'), [knowledgeBases])
  const archivedKnowledgeBases = useMemo(() => knowledgeBases.filter((kb) => kb.status === 'archived'), [knowledgeBases])
  const activeKnowledgeBase = activeKnowledgeBases.find((kb) => kb.id === activeKnowledgeBaseId) ?? null

  useEffect(() => {
    if (isLoading || !isFetched) return
    if (activeKnowledgeBases.length === 0) {
      if (activeKnowledgeBaseId !== null) {
        setActiveKnowledgeBaseIdState(null)
        clearActiveKnowledgeBaseSelection()
      }
      return
    }
    if (activeKnowledgeBase) return
    const defaultKnowledgeBase = activeKnowledgeBases.find((kb) => kb.is_default) ?? activeKnowledgeBases[0]
    setActiveKnowledgeBaseIdState(defaultKnowledgeBase.id)
    window.localStorage.setItem(ACTIVE_KB_KEY, String(defaultKnowledgeBase.id))
  }, [activeKnowledgeBase, activeKnowledgeBaseId, activeKnowledgeBases, isFetched, isLoading])

  const setActiveKnowledgeBaseId = (id: number | null) => {
    setActiveKnowledgeBaseIdState(id)
    if (id === null) {
      clearActiveKnowledgeBaseSelection()
      return
    }
    window.localStorage.setItem(ACTIVE_KB_KEY, String(id))
  }

  const value = useMemo(
    () => ({
      knowledgeBases,
      activeKnowledgeBases,
      archivedKnowledgeBases,
      activeKnowledgeBaseId,
      activeKnowledgeBase,
      setActiveKnowledgeBaseId,
      isLoading,
    }),
    [activeKnowledgeBase, activeKnowledgeBaseId, activeKnowledgeBases, archivedKnowledgeBases, isLoading, knowledgeBases],
  )

  return <KnowledgeBaseContext.Provider value={value}>{children}</KnowledgeBaseContext.Provider>
}

export function useKnowledgeBaseContext() {
  const context = useContext(KnowledgeBaseContext)
  if (!context) {
    throw new Error('useKnowledgeBaseContext must be used within KnowledgeBaseProvider')
  }
  return context
}
