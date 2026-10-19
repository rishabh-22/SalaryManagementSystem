import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, login as loginRequest } from '../api/hooks'
import { tokenStore } from '../api/client'
import { qk } from '../api/queryKeys'
import type { Role, User } from '../api/types'

interface AuthState {
  user: User | null
  /** True while a stored token is being validated via /auth/me. */
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasRole: (...roles: Role[]) => boolean
  /** admin and hr_manager may write; viewer is read-only. */
  canWrite: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [token, setToken] = useState<string | null>(() => tokenStore.get())

  const meQuery = useQuery({
    queryKey: qk.me,
    queryFn: fetchMe,
    enabled: !!token,
    retry: false,
    staleTime: 5 * 60_000,
  })

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await loginRequest(email, password)
      tokenStore.set(access_token)
      qc.removeQueries({ queryKey: qk.me })
      setToken(access_token)
    },
    [qc],
  )

  const logout = useCallback(() => {
    tokenStore.clear()
    setToken(null)
    qc.clear()
  }, [qc])

  const value = useMemo<AuthState>(() => {
    const user = token ? (meQuery.data ?? null) : null
    return {
      user,
      isLoading: !!token && meQuery.isPending,
      isAuthenticated: !!user,
      login,
      logout,
      hasRole: (...roles) => !!user && roles.includes(user.role),
      canWrite: user?.role === 'admin' || user?.role === 'hr_manager',
    }
  }, [token, meQuery.data, meQuery.isPending, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
