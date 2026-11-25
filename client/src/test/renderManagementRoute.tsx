import { render } from '@testing-library/react'
import { cloneElement, isValidElement, useState, type ReactNode } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider } from '../app/AuthProvider'
import { router } from '../app/router'
import { ManagementProvider } from '../app/ManagementProvider'
import type { Role } from '../types'
export { categoryRow, supplierRow, productRow, warehouseRow, jsonResponse } from './renderRoleRoute'

export function renderManagementRoute(path: string, role: Role | null, handler: (url: string, init?: RequestInit) => Response | Promise<Response>, prepare?: (cache: QueryClient) => void) {
  // jsdom has no native dialog implementation; browser/E2E owns focus/inert verification.
  if (!HTMLDialogElement.prototype.showModal) HTMLDialogElement.prototype.showModal = function () { this.open = true }
  if (!HTMLDialogElement.prototype.close) HTMLDialogElement.prototype.close = function () { this.open = false }
  let queryClient: QueryClient
  function Capture({ children }: { children: ReactNode }) {
    queryClient = useQueryClient()
    useState(() => { prepare?.(queryClient); return true })
    return children
  }
  const capture = (rows: RouteObject[]): RouteObject[] => rows.map(row => {
    const element = row.element
    return { ...row, ...(row.children ? { children: capture(row.children) } : {}), ...(isValidElement<{ children: ReactNode }>(element) && element.type === ManagementProvider ? { element: cloneElement(element, {}, <Capture>{element.props.children}</Capture>) } : {}) } as RouteObject
  })
  if (role) localStorage.setItem('smart-warehouse-token', `${role}-test-token`)
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return new Response(JSON.stringify({ id: 1, email: `${role}@example.com`, role, is_active: true }), { status: 200 })
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  const active = createMemoryRouter(capture(router.routes), { initialEntries: [path] })
  const view = render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  return { ...view, active, fetchMock, get queryClient() { return queryClient } }
}
