import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AppRouter } from '../app/router'
import { AuthProvider } from '../features/auth/AuthProvider'

export const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})

export const categoryRow = { id: 4, name: 'Hardware', parent_id: null }
export const supplierRow = { id: 5, name: 'Northwind', email: null, phone: null, address: null }
export const productRow = {
  id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4,
  supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true,
}
export const warehouseRow = {
  id: 7, code: 'WH-01', name: 'Main warehouse', address: '1 Bay Street',
  latitude: null, longitude: null, created_at: '2026-09-29T09:00:00Z', updated_at: '2026-09-29T09:00:00Z',
}

export function renderRoleRoute(path: string, role: 'admin' | 'warehouse' | 'client', handler: (url: string, init?: RequestInit) => Response | Promise<Response>, queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  localStorage.setItem('smart-warehouse-token', `${role}-token`)
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return Promise.resolve(jsonResponse({ id: 1, email: `${role}@example.com`, role, is_active: true }))
    return Promise.resolve(handler(url, init))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={queryClient}><AuthProvider><MemoryRouter initialEntries={[path]}><AppRouter /></MemoryRouter></AuthProvider></QueryClientProvider>)
  return { fetchMock, queryClient }
}
