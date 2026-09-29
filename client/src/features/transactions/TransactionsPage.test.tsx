import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderRoleRoute, warehouseRow } from '../../test/renderRoleRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

const product = { id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4, supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true }
const event = { id: 88, transaction_type: 'inbound', warehouse_id: 7, product_id: 6, quantity: 5, inbound_id: 30, outbound_id: null, created_by_id: 12, created_at: '2026-09-29T02:45:00Z' }
const page = (items = [event], total = items.length, current = 1) => ({ items, total, page: current, page_size: 20 })

it('shows transaction direction, resolved labels, actor, linked movement, quantity, and local time', async () => {
  renderRoleRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })

  expect(await screen.findByText('Inbound', { selector: '.movement-direction' })).toBeInTheDocument()
  expect(screen.getByText('SKU-001')).toBeInTheDocument()
  expect(screen.getByText('WH-01')).toBeInTheDocument()
  expect(screen.getByText('Actor 12')).toBeInTheDocument()
  expect(screen.getByText('Inbound #30')).toBeInTheDocument()
  expect(screen.getByText('5')).toBeInTheDocument()
  expect(screen.getByText(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.created_at)))).toBeInTheDocument()
})

it('resolves labels by ID when product and warehouse are outside lookup pages', async () => {
  const { fetchMock } = renderRoleRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [{ ...product, id: 2, sku: 'SKU-OTHER', name: 'Different item' }], total: 121, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [{ ...warehouseRow, id: 3, code: 'WH-OTHER' }], total: 44, page: 1, page_size: 100 })
    if (url.endsWith('/products/6')) return jsonResponse(product)
    if (url.endsWith('/warehouses/7')) return jsonResponse(warehouseRow)
    return jsonResponse({})
  })

  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(await screen.findByText('WH-01')).toBeInTheDocument()
  expect(screen.queryByText('SKU-OTHER')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/products/6'))).toBe(true)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/warehouses/7'))).toBe(true)
})

it('retains transaction details while retrying only a failed warehouse label', async () => {
  let productRequests = 0
  let warehouseRequests = 0
  let resolveRetry: ((response: Response) => void) | undefined
  const warehouse = { ...warehouseRow, id: 7, code: 'WH-01', name: 'Main warehouse' }
  const { fetchMock } = renderRoleRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
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
    return jsonResponse({})
  })

  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(await screen.findByText('Warehouse #7')).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('Warehouse detail unavailable.')
  expect(screen.getByText('Actor 12')).toBeInTheDocument()
  expect(screen.getByText('Inbound #30')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Retry label lookup' }))
  expect(await screen.findByText('Resolving product and warehouse labels for transaction history…')).toHaveAttribute('role', 'status')
  expect(screen.getByText('SKU-001')).toBeInTheDocument()
  expect(screen.getByText('Actor 12')).toBeInTheDocument()
  expect(screen.getByText('Inbound #30')).toBeInTheDocument()
  expect(productRequests).toBe(1)
  expect(warehouseRequests).toBe(2)
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/products/6'))).toHaveLength(1)

  resolveRetry?.(jsonResponse(warehouse))
  expect(await screen.findByText('WH-01')).toBeInTheDocument()
})

it('filters transaction type and timezone-aware date range and resets pagination', async () => {
  const { fetchMock } = renderRoleRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page([event], 41, url.includes('page=2') ? 2 : 1))
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  await screen.findByText('Page 2 of 3')
  await user.selectOptions(screen.getByLabelText('Transaction type'), 'outbound')
  await user.selectOptions(screen.getByLabelText('Warehouse'), '7')
  await user.selectOptions(screen.getByLabelText('Product'), '6')
  await user.type(screen.getByLabelText('Created from'), '2026-09-28T08:00')
  await user.type(screen.getByLabelText('Created to'), '2026-09-29T08:00')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))

  expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => {
    const value = String(url)
    return value.includes('transaction_type=outbound') && value.includes('warehouse_id=7') && value.includes('product_id=6') && value.includes('created_from=') && value.includes('created_to=') && value.includes('page=1')
  })).toBe(true)
})

it('rejects inverted transaction dates without sending another request', async () => {
  const { fetchMock } = renderRoleRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  const requests = fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?')).length
  await user.type(screen.getByLabelText('Created from'), '2026-09-29T12:00')
  await user.type(screen.getByLabelText('Created to'), '2026-09-28T12:00')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/start.*before.*end/i)
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?'))).toHaveLength(requests)
})

it.each(['admin', 'warehouse'] as const)('provides bounded transaction pagination to %s', async (role) => {
  renderRoleRoute('/transactions', role, (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page([event], 61, url.includes('page=2') ? 2 : 1))
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('Page 2 of 4')).toBeInTheDocument()
})

it('shows transaction service errors and lets the user retry the history query', async () => {
  let attempts = 0
  renderRoleRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) {
      attempts += 1
      return attempts === 1
        ? jsonResponse({ detail: { code: 'HISTORY_DOWN', message: 'Transaction history unavailable.', fields: null } }, 503)
        : jsonResponse(page())
    }
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })

  expect(await screen.findByRole('alert')).toHaveTextContent('Transaction history unavailable.')
  await userEvent.click(screen.getByRole('button', { name: 'Retry transactions' }))
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
})
