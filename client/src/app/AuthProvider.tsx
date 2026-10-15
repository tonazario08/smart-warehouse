import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { advanceApiSession, ApiError, api, onApiUnauthorized } from '../api'
import type { User } from '../types'
import { getAuthErrorMessage } from '../shared/lib/auth-errors'

const tokenKey = 'smart-warehouse-token'
type AuthContextValue = { user: User | null; token: string | null; loading: boolean; error: string; login: (email: string, password: string) => Promise<boolean>; logout: () => void; clearError: () => void }
const AuthContext = createContext<AuthContextValue | null>(null)
const errorMessage = (error: unknown) => getAuthErrorMessage(error instanceof ApiError ? error : undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey))
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(token))
  const [error, setError] = useState('')
  const generation = useRef(0)
  const hydratedToken = useRef<string | null>(null)
  const hydration = useRef<{ token: string; promise: Promise<User> } | null>(null)

  const logout = useCallback(() => {
    generation.current++
    advanceApiSession()
    hydration.current = null
    hydratedToken.current = null
    localStorage.removeItem(tokenKey)
    setToken(null); setUser(null); setError(''); setLoading(false)
  }, [])

  useEffect(() => onApiUnauthorized(requestToken => {
    if (requestToken === token && requestToken === localStorage.getItem(tokenKey)) logout()
  }), [logout, token])

  useEffect(() => {
    if (!token || hydratedToken.current === token) return
    const current = generation.current
    let active = true
    const request = hydration.current?.token === token ? hydration.current.promise : api.me(token)
    hydration.current = { token, promise: request }
    void request.then(nextUser => {
      if (active && generation.current === current) {
        hydratedToken.current = token
        setUser(nextUser)
      }
    }).catch(cause => {
      if (!active || generation.current !== current) return
      if (cause instanceof ApiError && cause.status === 401 && !cause.staleSession) logout()
      else setError(errorMessage(cause))
    }).finally(() => { if (active && generation.current === current) setLoading(false) })
    return () => { active = false }
  }, [logout, token])

  const login = useCallback(async (email: string, password: string) => {
    const current = ++generation.current
    advanceApiSession()
    hydration.current = null
    hydratedToken.current = null
    localStorage.removeItem(tokenKey)
    setToken(null); setUser(null); setLoading(true); setError('')
    try {
      const result = await api.login(email, password)
      if (generation.current !== current) return false
      localStorage.setItem(tokenKey, result.access_token)
      const nextUser = await api.me(result.access_token)
      if (generation.current !== current) return false
      hydratedToken.current = result.access_token
      setToken(result.access_token)
      setUser(nextUser)
      return true
    } catch (cause) {
      if (generation.current === current) {
        localStorage.removeItem(tokenKey)
        setToken(null); setUser(null); setError(errorMessage(cause))
      }
      return false
    } finally { if (generation.current === current) setLoading(false) }
  }, [])
  const value = useMemo(() => ({ user, token, loading, error, login, logout, clearError: () => setError('') }), [error, loading, login, logout, token, user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error('useAuth phải được sử dụng trong AuthProvider'); return context }
export type LoginSubmitEvent = FormEvent<HTMLFormElement>
