import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Permission } from '../shared/lib/permissions'
import { can } from '../shared/lib/permissions'
import { useAuth } from './AuthProvider'

export function RouteGuard({ permission }: { permission?: Permission }) {
  const { loading, user } = useAuth()
  const location = useLocation()
  if (loading) return <main className="route-status">Đang xác thực phiên làm việc...</main>
  if (!user) return <Navigate replace state={{ from: location }} to="/login" />
  if (permission && !can(user.role, permission)) return <Navigate replace to={user.role === 'client' ? '/products' : '/inventory'} />
  return <Outlet />
}
