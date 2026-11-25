import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

export function AuthLoading() {
  return <main className="auth-state" role="status" aria-live="polite">Loading your account…</main>
}

export function RequireAuth({ children }: { children?: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <AuthLoading />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return children ?? <Outlet />
}
