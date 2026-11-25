import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider } from '../app/AuthProvider'
import { router } from '../app/router'
import type { Role } from '../types'
import type { Transfer } from '../features/transfers/types'

export const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
export const transferProduct = { id: 3, sku: 'CK-003', name: 'Bu lông', description: null, category_id: 1, supplier_id: null, unit: 'cái', reorder_level: 0, is_active: false }
export const transferWarehouses = [
  { id: 1, code: 'NGUON', name: 'Kho nguồn', address: '1 Fixture', latitude: null, longitude: null },
  { id: 2, code: 'DICH', name: 'Kho đích', address: '2 Fixture', latitude: null, longitude: null },
]
export const transfer: Transfer = { id: 8, source_warehouse_id: 1, destination_warehouse_id: 2, product_id: 3, quantity: 3, reference: 'CK-01', note: null, created_by_id: 1, created_at: '2026-10-17T07:00:00Z', outbound_id: 11, inbound_id: 12, outbound_transaction_id: 21, inbound_transaction_id: 22, source_quantity_before: 10, source_quantity_after: 7, destination_quantity_before: 2, destination_quantity_after: 5 }
export const transferPage = (items = [transfer], total = items.length, page = 1) => ({ items, total, page, page_size: 20 })
export function transferHandler(url: string): Response {
  const path = new URL(url).pathname
  if (path.endsWith('/products/3')) return jsonResponse(transferProduct)
  if (path.endsWith('/products')) return jsonResponse({ items: [transferProduct], total: 1, page: 1, page_size: 100 })
  if (path.endsWith('/warehouses')) return jsonResponse({ items: transferWarehouses, total: 2, page: 1, page_size: 100 })
  if (path.endsWith('/stock')) return jsonResponse({ items: [
    { id: 1, warehouse_id: 1, product_id: 3, quantity: 10 }, { id: 2, warehouse_id: 2, product_id: 3, quantity: 2 },
  ], total: 2, page: 1, page_size: 100 })
  if (path.endsWith('/transfers/8')) return jsonResponse(transfer)
  if (path.endsWith('/transfers')) return jsonResponse(transferPage())
  return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 })
}
export function renderTransferRoute(path: string, role: Role | null = 'warehouse', handler: (url: string, init?: RequestInit) => Response | Promise<Response> = transferHandler) {
  if (!HTMLDialogElement.prototype.showModal) HTMLDialogElement.prototype.showModal = function () { this.open = true }
  if (!HTMLDialogElement.prototype.close) HTMLDialogElement.prototype.close = function () { this.open = false }
  if (role) localStorage.setItem('smart-warehouse-token', role + '-transfer-token')
  else localStorage.removeItem('smart-warehouse-token')
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return jsonResponse({ id: 1, email: role + '@example.com', role, is_active: true })
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  const active = createMemoryRouter(router.routes, { initialEntries: [path] })
  return { ...render(<AuthProvider><RouterProvider router={active} /></AuthProvider>), active, fetchMock }
}
