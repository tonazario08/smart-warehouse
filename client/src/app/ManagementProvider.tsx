import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuth } from './AuthProvider'
import { createManagementApiClient } from '../shared/api/createManagementApiClient'
import type { ApiClient } from '../shared/api/ApiClient'
import type { User } from '../types'
import '../shared/styles/management.css'

const ManagementContext = createContext<{ client: ApiClient; user: User | null } | null>(null)

export function ManagementProvider({ children }: { children: ReactNode }) {
  const { token, user } = useAuth()
  const sequence = useRef(0)
  const scope = useMemo(() => ({
    id: ++sequence.current,
    client: createManagementApiClient(() => token),
    cache: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }),
  }), [token, user?.id, user?.role])
  useEffect(() => () => { void scope.cache.cancelQueries(); scope.cache.clear() }, [scope])
  return <QueryClientProvider client={scope.cache} key={scope.id}>
    <ManagementContext.Provider value={{ client: scope.client, user }}>{children}</ManagementContext.Provider>
  </QueryClientProvider>
}

export function useManagementSession() {
  const session = useContext(ManagementContext)
  if (!session) throw new Error('Phân hệ quản trị cần phiên đăng nhập đang hoạt động.')
  return session
}
