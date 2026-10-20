import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider, useAuth } from '../app/AuthProvider'
import { router } from '../app/router'
import type { Role } from '../types'
import type { PurchaseRequest } from '../features/purchaseRequests/types'

export const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
export const purchaseProduct = { id: 3, sku: 'B2B-003', name: 'Bu lông', description: null, category_id: 1, supplier_id: null, unit: 'cái', reorder_level: 0, is_active: true }
export const purchaseWarehouses = [
  { id: 1, code: 'KHO-A', name: 'Kho yêu cầu', address: 'Fixture', latitude: null, longitude: null },
  { id: 2, code: 'KHO-B', name: 'Kho khác', address: 'Fixture', latitude: null, longitude: null },
]
export const purchase: PurchaseRequest = { id: 8, request_number: 'PR-0008', warehouse_id: 1, product_id: 3, quantity: 3, requested_by_id: 1, status: 'pending', note: 'Giao trong tuần', workflow_managed: true, created_at: '2026-10-19T00:00:00Z', updated_at: '2026-10-19T00:00:00Z', decision: null, fulfillment: null }
export const approvedPurchase: PurchaseRequest = { ...purchase, status: 'approved', updated_at: '2026-10-19T01:00:00Z', decision: { kind: 'approved', actor_id: 7, decided_at: '2026-10-19T01:00:00Z', rejection_reason: null } }
export const fulfilledPurchase: PurchaseRequest = { ...approvedPurchase, status: 'fulfilled', updated_at: '2026-10-19T02:00:00Z', fulfillment: { outbound_id: 11, transaction_id: 21, actor_id: 9, fulfilled_at: '2026-10-19T02:00:00Z', quantity_before: 10, quantity_after: 7 } }
export const purchasePage = (items = [purchase], total = items.length, page = 1) => ({ items, total, page, page_size: 20 })
export function purchaseHandler(url: string): Response {
  const path = new URL(url).pathname
  if (path.endsWith('/products/3')) return jsonResponse(purchaseProduct)
  if (path.endsWith('/products')) return jsonResponse({ items: [purchaseProduct], total: 1, page: 1, page_size: 100 })
  if (path.endsWith('/warehouses')) return jsonResponse({ items: purchaseWarehouses, total: 2, page: 1, page_size: 100 })
  if (path.endsWith('/stock')) return jsonResponse({ items: [{ id: 1, warehouse_id: 1, product_id: 3, quantity: 10 }], total: 1, page: 1, page_size: 100 })
  if (path.endsWith('/purchase-requests/8')) return jsonResponse(purchase)
  if (path.endsWith('/purchase-requests')) return jsonResponse(purchasePage())
  return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 })
}
function SessionControls() {
  const auth = useAuth()
  return <button onClick={() => void auth.login('replacement@example.com', 'fixture-only-password')}>Đổi phiên kiểm thử</button>
}
export function deferredResponse() {
  let resolve!: (response: Response) => void
  const promise = new Promise<Response>(done => { resolve = done })
  return { promise, resolve }
}
export function renderPurchaseRequestRoute(path: string, role: Role | null = 'client', handler: (url: string, init?: RequestInit) => Response | Promise<Response> = purchaseHandler) {
  if (!HTMLDialogElement.prototype.showModal) HTMLDialogElement.prototype.showModal = function () { this.open = true }
  if (!HTMLDialogElement.prototype.close) HTMLDialogElement.prototype.close = function () { this.open = false }
  if (role) localStorage.setItem('smart-warehouse-token', role + '-purchase-token')
  else localStorage.removeItem('smart-warehouse-token')
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/login')) return jsonResponse({ access_token: 'replacement-purchase-token', user: { id: 2, email: 'replacement@example.com', role: 'client', is_active: true } })
    if (url.endsWith('/auth/me')) {
      const replacement = new Headers(init?.headers).get('Authorization')?.includes('replacement-purchase-token')
      return jsonResponse({ id: replacement ? 2 : 1, email: replacement ? 'replacement@example.com' : role + '@example.com', role: replacement ? 'client' : role, is_active: true })
    }
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  const active = createMemoryRouter(router.routes, { initialEntries: [path] })
  return { ...render(<AuthProvider><SessionControls /><RouterProvider router={active} /></AuthProvider>), active, fetchMock }
}
