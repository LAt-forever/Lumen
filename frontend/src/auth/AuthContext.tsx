import { createContext, useContext, useEffect, useMemo, useState } from 'react'

import { api, clearAccessToken, getAccessToken, setAccessToken, setUnauthorizedHandler } from '../api/client'
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
  const [user, setUser] = useState<UserRead | null>(() => provisionalUser())
  const [isChecking, setIsChecking] = useState(() => Boolean(getAccessToken()))

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      setIsChecking(false)
    })
    return () => setUnauthorizedHandler(undefined)
  }, [])

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
          clearAccessToken()
          setUser(null)
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
        setAccessToken(result.access_token)
        setUser(result.user)
        setIsChecking(false)
      },
      logout: async () => {
        try {
          if (getAccessToken()) await api.logout()
        } finally {
          clearAccessToken()
          setUser(null)
          setIsChecking(false)
        }
      },
    }),
    [user, isChecking],
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
