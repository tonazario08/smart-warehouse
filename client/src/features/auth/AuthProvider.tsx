import { useCallback, useEffect, useMemo, useRef, useState, createContext, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiClient } from '../../shared/api/ApiClient'
import { ApiError } from '../../shared/api/ApiError'
import { createAuthApi } from './api'
import type { AuthContextValue, AuthStatus, User } from './types'

export const AUTH_TOKEN_KEY = 'smart-warehouse-token'

export const AuthContext = createContext<AuthContextValue | null>(null)

interface Session {
  status: AuthStatus
  user: User | null
}

const initialSession = (): Session => ({
  status: localStorage.getItem(AUTH_TOKEN_KEY) ? 'loading' : 'anonymous',
  user: null,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session>(initialSession)
  const revision = useRef(0)
  const sessionGeneration = useRef(0)
  const hydrationRequest = useRef<Promise<User> | null>(null)

  const clearSession = useCallback(() => {
    revision.current += 1
    sessionGeneration.current += 1
    hydrationRequest.current = null
    localStorage.removeItem(AUTH_TOKEN_KEY)
    queryClient.clear()
    setSession({ status: 'anonymous', user: null })
  }, [queryClient])

  const [client] = useState(() => new ApiClient(
    undefined,
    () => localStorage.getItem(AUTH_TOKEN_KEY),
    (requestToken, requestGeneration) => {
      if (
        requestGeneration === sessionGeneration.current
        && requestToken === localStorage.getItem(AUTH_TOKEN_KEY)
      ) clearSession()
    },
    () => sessionGeneration.current,
  ))
  const authApi = useMemo(() => createAuthApi(client), [client])

  useEffect(() => {
    if (session.status !== 'loading' || !localStorage.getItem(AUTH_TOKEN_KEY)) return
    const currentRevision = revision.current
    const request = hydrationRequest.current ?? (hydrationRequest.current = authApi.me())
    let active = true

    void request.then((user) => {
      if (active && revision.current === currentRevision) setSession({ status: 'authenticated', user })
    }).catch((error: unknown) => {
      if (!active || revision.current !== currentRevision) return
      if (error instanceof ApiError && error.status === 403) setSession({ status: 'anonymous', user: null })
      else if (!(error instanceof ApiError && error.status === 401)) clearSession()
    })

    return () => { active = false }
  }, [authApi, clearSession, session.status])

  const login = useCallback(async (input: Parameters<AuthContextValue['login']>[0]) => {
    clearSession()
    const loginRevision = revision.current
    setSession({ status: 'loading', user: null })

    try {
      const result = await authApi.login(input)
      if (revision.current !== loginRevision) throw new Error('The sign-in attempt is no longer active.')
      sessionGeneration.current += 1
      localStorage.setItem(AUTH_TOKEN_KEY, result.access_token)
      const user = await authApi.me()
      if (revision.current !== loginRevision) throw new Error('The sign-in attempt is no longer active.')
      setSession({ status: 'authenticated', user })
      return user
    } catch (error) {
      if (revision.current === loginRevision) clearSession()
      throw error
    }
  }, [authApi, clearSession])

  const register = useCallback((input: Parameters<AuthContextValue['register']>[0]) => authApi.register(input), [authApi])
  const logout = useCallback(() => clearSession(), [clearSession])

  const value = useMemo<AuthContextValue>(() => ({
    status: session.status,
    user: session.user,
    login,
    register,
    logout,
    client,
  }), [client, login, logout, register, session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
