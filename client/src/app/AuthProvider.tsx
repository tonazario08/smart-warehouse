import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ApiError, api } from '../api'
import type { User } from '../types'
import { getAuthErrorMessage } from '../shared/lib/auth-errors'

const tokenKey = 'smart-warehouse-token'
type AuthContextValue = { user: User | null; token: string | null; loading: boolean; error: string; login: (email: string, password: string) => Promise<boolean>; logout: () => void; clearError: () => void }
const AuthContext = createContext<AuthContextValue | null>(null)
const errorMessage = (error: unknown) => getAuthErrorMessage(error instanceof ApiError ? error : undefined)
const isAuthenticationFailure = (error: unknown) => error instanceof ApiError && error.status === 401

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey))
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(token))
  const [error, setError] = useState('')
  const logout = useCallback(() => { localStorage.removeItem(tokenKey); setToken(null); setUser(null); setError(''); setLoading(false) }, [])
  useEffect(() => { if (!token) return; let active = true; void api.me(token).then((nextUser) => { if (active) setUser(nextUser) }).catch((cause) => { if (active) { if (isAuthenticationFailure(cause)) logout(); else setError(errorMessage(cause)) } }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [logout, token])
  const login = useCallback(async (email: string, password: string) => { setLoading(true); setError(''); try { const result = await api.login(email, password); localStorage.setItem(tokenKey, result.access_token); setToken(result.access_token); const nextUser = await api.me(result.access_token); setUser(nextUser); return true } catch (cause) { setError(errorMessage(cause)); localStorage.removeItem(tokenKey); setToken(null); setUser(null); return false } finally { setLoading(false) } }, [])
  const value = useMemo(() => ({ user, token, loading, error, login, logout, clearError: () => setError('') }), [error, loading, login, logout, token, user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error('useAuth phải được sử dụng trong AuthProvider'); return context }
export type LoginSubmitEvent = FormEvent<HTMLFormElement>
