import type { ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './AppShell'
import { landingPathForRole, navigationForRole, navigationItems } from './navigation'
import { useAuth } from '../features/auth/useAuth'
import { AuthLoading, RequireAuth } from '../features/auth/RequireAuth'
import { RequireRole } from '../features/auth/RequireRole'
import { LoginPage } from '../features/auth/LoginPage'
import { RegisterPage } from '../features/auth/RegisterPage'

const featureRoutes = navigationItems.map((item) => ({
  path: item.href,
  label: item.label,
  roles: item.roles,
}))

function AnonymousOnly({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <AuthLoading />
  if (user) {
    const state = location.state as { from?: { pathname?: string; search?: string; hash?: string } } | null
    const path = state?.from?.pathname
    const destination = path?.startsWith('/') && !path.startsWith('//')
      ? `${path}${state?.from?.search ?? ''}${state?.from?.hash ?? ''}`
      : landingPathForRole(user.role)
    return <Navigate to={destination} replace />
  }
  return children
}

function ProtectedShell() {
  const auth = useAuth()
  const location = useLocation()
  if (!auth.user) return <AuthLoading />

  return (
    <AppShell
      title="Smart Warehouse"
      activePath={location.pathname}
      navigationItems={navigationForRole(auth.user.role)}
      utility={
        <>
          <span className="current-account">{auth.user.email}<span className="role-chip">{auth.user.role}</span></span>
          <button className="quiet" type="button" onClick={auth.logout}>Sign out</button>
        </>
      }
    >
      <Outlet />
    </AppShell>
  )
}

function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={user ? landingPathForRole(user.role) : '/login'} replace />
}

function FeaturePlaceholder({ label }: { label: string }) {
  return (
    <section className="route-placeholder" aria-labelledby="feature-heading">
      <p className="kicker">Phase 1 workspace</p>
      <h2 id="feature-heading">{label}</h2>
      <p>This screen will be completed in a later Phase 1 workstream.</p>
    </section>
  )
}

function ForbiddenPage() {
  return (
    <section className="route-placeholder" aria-labelledby="permission-heading">
      <p className="kicker">Access control</p>
      <h2 id="permission-heading">Permission required</h2>
      <p>You do not have permission to view this section.</p>
    </section>
  )
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<AnonymousOnly><LoginPage /></AnonymousOnly>} />
      <Route path="/register" element={<AnonymousOnly><RegisterPage /></AnonymousOnly>} />
      <Route element={<RequireAuth />}>
        <Route element={<ProtectedShell />}>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />
        {featureRoutes.map((route) => (
            <Route key={route.path} path={route.path} element={
              <RequireRole allow={route.roles}>
                <FeaturePlaceholder label={route.label} />
              </RequireRole>
            } />
        ))}
          <Route path="*" element={<HomeRedirect />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/products" replace />} />
    </Routes>
  )
}
