import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderRoleRoute, warehouseRow } from '../../test/renderRoleRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

const product = { id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4, supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true }
const warehouse = { ...warehouseRow, id: 7, code: 'WH-01', name: 'Main warehouse' }
const movement = { id: 32, warehouse_id: 7, product_id: 6, quantity: 3, reference: 'REF-32', note: 'Checked', created_by_id: 14, created_at: '2026-09-29T02:45:00Z' }

describe('movement history label recovery', () => {
  it('keeps resolved row data and retries only the failed warehouse label', async () => {
    let productRequests = 0
    let warehouseRequests = 0
    let resolveRetry: ((response: Response) => void) | undefined
    const { fetchMock } = renderRoleRoute('/inbounds', 'warehouse', (url) => {
      if (url.includes('/inbounds?')) return jsonResponse({ items: [movement], total: 1, page: 1, page_size: 20 })
      if (url.includes('/products?')) return jsonResponse({ items: [{ ...product, id: 2, sku: 'SKU-OTHER', name: 'Other item' }], total: 121, page: 1, page_size: 100 })
      if (url.includes('/warehouses?')) return jsonResponse({ items: [{ ...warehouse, id: 3, code: 'WH-OTHER' }], total: 44, page: 1, page_size: 100 })
      if (url.endsWith('/products/6')) {
        productRequests += 1
        return jsonResponse(product)
      }
      if (url.endsWith('/warehouses/7')) {
        warehouseRequests += 1
        if (warehouseRequests === 1) return jsonResponse({ detail: { code: 'LOOKUP_DOWN', message: 'Warehouse detail unavailable.', fields: null } }, 503)
        return new Promise<Response>((resolve) => { resolveRetry = resolve })
      }
      return jsonResponse({ items: [], total: 0, page: 1, page_size: 20 })
    })

    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
    expect(await screen.findByText('Warehouse #7')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent('Warehouse detail unavailable.')
    expect(screen.getByText('Actor 14')).toBeInTheDocument()
    expect(screen.getByText('REF-32')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Retry label lookup' }))
    expect(await screen.findByText('Resolving product and warehouse labels for movement history…')).toHaveAttribute('role', 'status')
    expect(screen.getByText('SKU-001')).toBeInTheDocument()
    expect(screen.getByText('Actor 14')).toBeInTheDocument()
    expect(screen.getByText('REF-32')).toBeInTheDocument()
    expect(productRequests).toBe(1)
    expect(warehouseRequests).toBe(2)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/products/6'))).toHaveLength(1)

    resolveRetry?.(jsonResponse(warehouse))
    expect(await screen.findByText('WH-01')).toBeInTheDocument()
  })
})
