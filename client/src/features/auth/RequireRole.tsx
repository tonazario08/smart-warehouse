import type { PropsWithChildren } from 'react'
import { Navigate } from 'react-router-dom'
import type { Role } from './types'
import { useAuth } from './useAuth'

export function RequireRole({ allow, children }: PropsWithChildren<{ allow: readonly Role[] }>) {
  const { status, user } = useAuth()
  if (status === 'loading') return <main className="auth-state" role="status" aria-live="polite">Loading your account…</main>
  if (!user) return <Navigate to="/login" replace />
  if (!allow.includes(user.role)) return <Navigate to="/forbidden" replace />
  return children
}
