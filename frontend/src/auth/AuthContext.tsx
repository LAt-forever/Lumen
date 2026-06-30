import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react'

import { api, clearAccessToken, getAccessToken, setAccessToken, setUnauthorizedHandler } from '../api/client'
import { clearActiveKnowledgeBaseSelection } from '../knowledgeBase/KnowledgeBaseContext'
import type { UserRead } from '../api/types'

type AuthContextValue = {
  user: UserRead | null
  isChecking: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function provisionalUser(): UserRead | null {
  return getAccessToken()
    ? {
        id: 0,
        email: '正在验证账户',
        is_admin: false,
        created_at: new Date(0).toISOString(),
      }
    : null
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserRead | null>(() => provisionalUser())
  const [isChecking, setIsChecking] = useState(() => Boolean(getAccessToken()))

  const clearSessionState = useCallback(() => {
    clearAccessToken()
    clearActiveKnowledgeBaseSelection()
    queryClient.clear()
    setUser(null)
    setIsChecking(false)
  }, [queryClient])

  useLayoutEffect(() => {
    setUnauthorizedHandler(clearSessionState)
    return () => setUnauthorizedHandler(undefined)
  }, [clearSessionState])

  useEffect(() => {
    if (!getAccessToken()) {
      setIsChecking(false)
      return
    }
    let active = true
    api
      .me()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch(() => {
        if (active) {
          clearSessionState()
        }
      })
      .finally(() => {
        if (active) setIsChecking(false)
      })
    return () => {
      active = false
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isChecking,
      login: async (email: string, password: string) => {
        const result = await api.login({ email, password })
        queryClient.clear()
        clearActiveKnowledgeBaseSelection()
        setAccessToken(result.access_token)
        setUser(result.user)
        setIsChecking(false)
      },
      logout: async () => {
        try {
          if (getAccessToken()) await api.logout()
        } finally {
          clearSessionState()
        }
      },
    }),
    [user, isChecking, clearSessionState, queryClient],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return value
}
