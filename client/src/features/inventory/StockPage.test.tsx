import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderRoleRoute, jsonResponse } from '../../test/renderRoleRoute'
import { warehouseRow } from '../../test/renderRoleRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

const product = { id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4, supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true }
const stock = { id: 15, warehouse_id: 7, product_id: 6, quantity: 28, created_at: '2026-09-28T20:15:00Z' }
const page = (items = [stock], total = items.length, current = 1) => ({ items, total, page: current, page_size: 20 })

function inventoryHandler(url: string) {
  if (url.includes('/stock?')) return jsonResponse(page())
  if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
  if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
  return jsonResponse({})
}

describe('stock ledger', () => {
  it.each(['admin', 'warehouse', 'client'] as const)('shows the stock ledger to %s with resolved product and warehouse labels', async (role) => {
    renderRoleRoute('/stock', role, inventoryHandler)

    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
    expect(screen.getByText('Steel bolt')).toBeInTheDocument()
    expect(screen.getByText('WH-01')).toBeInTheDocument()
    expect(screen.getByText('28')).toBeInTheDocument()
    expect(screen.getByText(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(stock.created_at)))).toBeInTheDocument()
  })

  it('resolves referenced records outside the first lookup page instead of showing another label', async () => {
    const { fetchMock } = renderRoleRoute('/stock', 'client', (url) => {
      if (url.includes('/stock?')) return jsonResponse(page())
      if (url.includes('/products?')) return jsonResponse({ items: [{ ...product, id: 3, sku: 'SKU-OTHER', name: 'Other item' }], total: 125, page: 1, page_size: 100 })
      if (url.includes('/warehouses?')) return jsonResponse({ items: [{ ...warehouseRow, id: 2, code: 'WH-OTHER', name: 'Other site' }], total: 45, page: 1, page_size: 100 })
      if (url.endsWith('/products/6')) return jsonResponse(product)
      if (url.endsWith('/warehouses/7')) return jsonResponse(warehouseRow)
      throw new Error(`Unexpected request ${url}`)
    })

    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
    expect(await screen.findByText('WH-01')).toBeInTheDocument()
    expect(screen.queryByText('SKU-OTHER')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/products/6'))).toBe(true)
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/warehouses/7'))).toBe(true)
  })

  it('resolves many missing labels with at most four detail requests in flight', async () => {
    const rows = Array.from({ length: 20 }, (_, index) => ({
      ...stock,
      id: 100 + index,
      product_id: 1000 + index,
      warehouse_id: 2000 + index,
    }))
    const held: Array<() => void> = []
    let active = 0
    let peak = 0
    const { fetchMock } = renderRoleRoute('/stock', 'client', (url) => {
      if (url.includes('/stock?')) return jsonResponse(page(rows))
      if (url.includes('/products?')) return jsonResponse({ items: [], total: 1200, page: 1, page_size: 100 })
      if (url.includes('/warehouses?')) return jsonResponse({ items: [], total: 2200, page: 1, page_size: 100 })
      const productMatch = url.match(/\/products\/(\d+)$/)
      const warehouseMatch = url.match(/\/warehouses\/(\d+)$/)
      if (productMatch || warehouseMatch) {
        const id = Number((productMatch ?? warehouseMatch)![1])
        active += 1
        peak = Math.max(peak, active)
        return new Promise<Response>((resolve) => {
          held.push(() => {
            resolve(jsonResponse(productMatch
              ? { ...product, id, sku: `SKU-${id}`, name: `Product ${id}` }
              : { ...warehouseRow, id, code: `WH-${id}`, name: `Warehouse ${id}` }))
          })
        }).finally(() => { active -= 1 })
      }
      throw new Error(`Unexpected request ${url}`)
    })

    await waitFor(() => expect(held).toHaveLength(4))
    expect(peak).toBe(4)
    for (let index = 0; index < 40; index += 1) {
      held[index]()
      await waitFor(() => expect(held.length).toBe(Math.min(index + 5, 40)))
      expect(peak).toBeLessThanOrEqual(4)
    }

    for (const row of rows) {
      expect(await screen.findByText(`SKU-${row.product_id}`)).toBeInTheDocument()
      expect(screen.getByText(`WH-${row.warehouse_id}`)).toBeInTheDocument()
    }
    expect(fetchMock.mock.calls.filter(([url]) => /\/(products|warehouses)\/\d+$/.test(String(url)))).toHaveLength(40)
    expect(peak).toBe(4)
  })

  it('filters by warehouse, product, and timezone-aware date range, resetting pagination', async () => {
    let pageCalls = 0
    const { fetchMock } = renderRoleRoute('/stock', 'warehouse', (url) => {
      if (url.includes('/stock?')) {
        pageCalls += 1
        const second = url.includes('page=2')
        return jsonResponse(page([stock], 25, second ? 2 : 1))
      }
      return inventoryHandler(url)
    })
    const user = userEvent.setup()
    await screen.findByText('SKU-001')
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Warehouse'), '7')
    await user.selectOptions(screen.getByLabelText('Product'), '6')
    await user.type(screen.getByLabelText('Created from'), '2026-09-28T08:00')
    await user.type(screen.getByLabelText('Created to'), '2026-09-29T08:00')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))

    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => {
      const value = String(url)
      return value.includes('warehouse_id=7') && value.includes('product_id=6') && value.includes('created_from=') && value.includes('created_to=') && value.includes('page=1')
    })).toBe(true))
    expect(pageCalls).toBeGreaterThan(2)
  })

  it('rejects an inverted date range before requesting stock', async () => {
    const { fetchMock } = renderRoleRoute('/stock', 'client', inventoryHandler)
    const user = userEvent.setup()
    await screen.findByText('SKU-001')
    const stockCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes('/stock?')).length
    await user.type(screen.getByLabelText('Created from'), '2026-09-29T12:00')
    await user.type(screen.getByLabelText('Created to'), '2026-09-28T12:00')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/start.*before.*end/i)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/stock?'))).toHaveLength(stockCalls)
  })

  it('shows lookup failures with retry while keeping stock rows safe to identify', async () => {
    let productAttempts = 0
    renderRoleRoute('/stock', 'client', (url) => {
      if (url.includes('/stock?')) return jsonResponse(page())
      if (url.includes('/products?')) {
        productAttempts += 1
        return productAttempts === 1 ? jsonResponse({ detail: { code: 'LOOKUP_DOWN', message: 'Product lookup unavailable.', fields: null } }, 503) : jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
      }
      if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
      return jsonResponse({})
    })
    const retryLabels = await screen.findByRole('button', { name: 'Retry label lookup' })
    expect(retryLabels.parentElement).toHaveTextContent('Product lookup unavailable.')
    await userEvent.click(retryLabels)
    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
    expect(within(screen.getByRole('row', { name: /SKU-001/ })).getByText('WH-01')).toBeInTheDocument()
  })

  it('shows stock request errors and recovers the ledger through its retry action', async () => {
    let attempts = 0
    renderRoleRoute('/stock', 'warehouse', (url) => {
      if (url.includes('/stock?')) {
        attempts += 1
        return attempts === 1 ? jsonResponse({ detail: { code: 'STOCK_DOWN', message: 'Stock service unavailable.', fields: null } }, 503) : jsonResponse(page())
      }
      return inventoryHandler(url)
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Stock service unavailable.')
    await userEvent.click(screen.getByRole('button', { name: 'Retry stock' }))
    expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  })
})
