import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { advanceApiSession, ApiError, api, onApiUnauthorized } from '../api'
import type { User } from '../types'
import { getAuthErrorMessage } from '../shared/lib/auth-errors'

const tokenKey = 'smart-warehouse-token'
type AuthContextValue = { user: User | null; token: string | null; loading: boolean; error: string; login: (email: string, password: string) => Promise<boolean>; logout: () => void; passwordChanged: boolean; capturePasswordChange: () => () => boolean; clearError: () => void }
const AuthContext = createContext<AuthContextValue | null>(null)
const errorMessage = (error: unknown) => getAuthErrorMessage(error instanceof ApiError ? error : undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey))
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(token))
  const [error, setError] = useState('')
  const [passwordChanged, setPasswordChanged] = useState(false)
  const generation = useRef(0)
  const unauthorizedSession = useRef<{ generation: number; token: string } | null>(null)
  const hydratedToken = useRef<string | null>(null)
  const hydration = useRef<{ token: string; promise: Promise<User> } | null>(null)

  const logout = useCallback(() => {
    generation.current++
    unauthorizedSession.current = null
    advanceApiSession()
    hydration.current = null
    hydratedToken.current = null
    localStorage.removeItem(tokenKey)
    setPasswordChanged(false)
    setToken(null); setUser(null); setError(''); setLoading(false)
  }, [])

  const capturePasswordChange = useCallback(() => {
    const current = generation.current
    const stored = localStorage.getItem(tokenKey)
    return () => {
      const activeToken = localStorage.getItem(tokenKey)
      const alreadyRevoked = generation.current === current + 1 && activeToken === null
        && unauthorizedSession.current?.generation === current
        && unauthorizedSession.current.token === stored
      if (!alreadyRevoked) {
        if (generation.current !== current || activeToken !== stored) return false
        logout()
      }
      setPasswordChanged(true)
      return true
    }
  }, [logout])

  useEffect(() => onApiUnauthorized(requestToken => {
    if (requestToken === token && requestToken === localStorage.getItem(tokenKey)) {
      const revoked = { generation: generation.current, token: requestToken }
      logout()
      unauthorizedSession.current = revoked
    }
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
    unauthorizedSession.current = null
    advanceApiSession()
    hydration.current = null
    hydratedToken.current = null
    localStorage.removeItem(tokenKey)
    setPasswordChanged(false)
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
  const value = useMemo(() => ({ user, token, loading, error, login, logout, passwordChanged, capturePasswordChange, clearError: () => setError('') }), [capturePasswordChange, error, loading, login, logout, passwordChanged, token, user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error('useAuth phải được sử dụng trong AuthProvider'); return context }
export type LoginSubmitEvent = FormEvent<HTMLFormElement>
