import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderRoleRoute, warehouseRow } from '../../test/renderRoleRoute'
import { movementSchema } from './schemas'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

const product = { id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4, supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true }
const page = { items: [], total: 0, page: 1, page_size: 20 }
const lookupPage = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 100 })

function lookup(url: string) {
  if (url.includes('/products?')) return jsonResponse(lookupPage([product]))
  if (url.includes('/warehouses?')) return jsonResponse(lookupPage([warehouseRow]))
  if (url.includes('/inbounds?') || url.includes('/outbounds?')) return jsonResponse(page)
  return jsonResponse({})
}

describe('movement schema and manifest', () => {
  it('loads movement and filter options beyond the first lookup page', async () => {
    const lateProduct = { ...product, id: 106, sku: 'SKU-101', name: 'Late product' }
    const lateWarehouse = { ...warehouseRow, id: 107, code: 'WH-101', name: 'Late warehouse' }
    const { fetchMock } = renderRoleRoute('/inbounds', 'warehouse', (url) => {
      const parsed = new URL(url, 'http://localhost')
      if (parsed.pathname.endsWith('/products')) {
        return parsed.searchParams.get('page') === '2'
          ? jsonResponse({ items: [lateProduct], total: 101, page: 2, page_size: 100 })
          : jsonResponse({ items: [product], total: 101, page: 1, page_size: 100 })
      }
      if (parsed.pathname.endsWith('/warehouses')) {
        return parsed.searchParams.get('page') === '2'
          ? jsonResponse({ items: [lateWarehouse], total: 101, page: 2, page_size: 100 })
          : jsonResponse({ items: [warehouseRow], total: 101, page: 1, page_size: 100 })
      }
      if (url.includes('/inbounds?')) return jsonResponse(page)
      return jsonResponse({})
    })

    expect(await screen.findAllByRole('option', { name: 'SKU-101 · Late product' })).toHaveLength(2)
    expect(await screen.findAllByRole('option', { name: 'WH-101 · Late warehouse' })).toHaveLength(2)
    const lookupUrls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(lookupUrls.some((url) => url.includes('/products?') && url.includes('page=2'))).toBe(true)
    expect(lookupUrls.some((url) => url.includes('/warehouses?') && url.includes('page=2'))).toBe(true)
  })

  it('accepts positive integer quantities and rejects zero, negative, fractional, and extra values', () => {
    const valid = { warehouse_id: '7', product_id: '6', quantity: '5' }
    expect(movementSchema.safeParse(valid).success).toBe(true)
    for (const quantity of ['0', '-1', '1.5']) expect(movementSchema.safeParse({ ...valid, quantity }).success).toBe(false)
    expect(movementSchema.safeParse({ ...valid, debug: true }).success).toBe(false)
  })

  it('trims optional reference and note and omits values that are blank', () => {
    const parsed = movementSchema.parse({ warehouse_id: '7', product_id: '6', quantity: '5', reference: '  ASN 12  ', note: '   ' })
    expect(parsed).toEqual({ warehouse_id: 7, product_id: 6, quantity: 5, reference: 'ASN 12', note: '' })
    expect(movementSchema.safeParse({ warehouse_id: '7', product_id: '6', quantity: '1', reference: 'x'.repeat(120), note: 'y'.repeat(2000) }).success).toBe(true)
    expect(movementSchema.safeParse({ warehouse_id: '7', product_id: '6', quantity: '1', reference: 'x'.repeat(121) }).success).toBe(false)
    expect(movementSchema.safeParse({ warehouse_id: '7', product_id: '6', quantity: '1', note: 'y'.repeat(2001) }).success).toBe(false)
  })

  it('posts a positive inbound, omits blank optional values, and invalidates only the inbound dependency set', async () => {
    const { fetchMock, queryClient } = renderRoleRoute('/inbounds', 'warehouse', (url, init) => {
      if (url.includes('/products?') || url.includes('/warehouses?') || url.includes('/inbounds?')) return lookup(url)
      if (url.endsWith('/inbounds') && init?.method === 'POST') return jsonResponse({ id: 30, warehouse_id: 7, product_id: 6, quantity: 5, reference: 'ASN 12', note: null }, 201)
      throw new Error(`Unexpected request ${url}`)
    })
    const invalidation = vi.spyOn(queryClient, 'invalidateQueries')
    const user = userEvent.setup()
    await screen.findByText('No inbound records match these filters.')
    await user.selectOptions(screen.getByLabelText('Warehouse for inbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for inbound'), '6')
    await user.type(screen.getByLabelText('Inbound quantity'), '5')
    await user.type(screen.getByLabelText('Reference'), '  ASN 12  ')
    await user.type(screen.getByLabelText('Note'), '   ')
    await user.click(screen.getByRole('button', { name: 'Record inbound' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Inbound recorded. Movement #30.')
    const request = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith('/inbounds') && init?.method === 'POST')?.[1]
    expect(JSON.parse(String(request?.body))).toEqual({ warehouse_id: 7, product_id: 6, quantity: 5, reference: 'ASN 12' })
    await waitFor(() => expect(invalidation).toHaveBeenCalledTimes(4))
    expect(invalidation.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([
      ['stock'], ['inbounds'], ['transactions'], ['dashboard', 'stats'],
    ])
  })

  it('posts an outbound then invalidates its outbound dependencies', async () => {
    const { fetchMock, queryClient } = renderRoleRoute('/outbounds', 'admin', (url, init) => {
      if (url.includes('/products?') || url.includes('/warehouses?') || url.includes('/outbounds?')) return lookup(url)
      if (url.endsWith('/outbounds') && init?.method === 'POST') return jsonResponse({ id: 31, warehouse_id: 7, product_id: 6, quantity: 2, reference: null, note: null }, 201)
      throw new Error(`Unexpected request ${url}`)
    })
    const invalidation = vi.spyOn(queryClient, 'invalidateQueries')
    const user = userEvent.setup()
    await screen.findByText('No outbound records match these filters.')
    await user.selectOptions(screen.getByLabelText('Warehouse for outbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for outbound'), '6')
    await user.type(screen.getByLabelText('Outbound quantity'), '2')
    await user.click(screen.getByRole('button', { name: 'Record outbound' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Outbound recorded. Movement #31.')
    const request = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith('/outbounds') && init?.method === 'POST')?.[1]
    expect(JSON.parse(String(request?.body))).toEqual({ warehouse_id: 7, product_id: 6, quantity: 2 })
    await waitFor(() => expect(invalidation).toHaveBeenCalledTimes(4))
    expect(invalidation.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([
      ['stock'], ['outbounds'], ['transactions'], ['dashboard', 'stats'],
    ])
  })

  it('associates backend field errors and retains insufficient-stock code and message', async () => {
    renderRoleRoute('/outbounds', 'warehouse', (url, init) => {
      if (url.includes('/products?') || url.includes('/warehouses?') || url.includes('/outbounds?')) return lookup(url)
      if (url.endsWith('/outbounds') && init?.method === 'POST') return jsonResponse({ detail: {
        code: 'INSUFFICIENT_STOCK', message: 'Only 1 piece is available.', fields: {
          warehouse_id: ['Warehouse is unavailable.'], product_id: ['Product is unavailable.'], quantity: ['Quantity exceeds available stock.'],
          reference: ['Reference was rejected.'], note: ['Note was rejected.'],
        },
      } }, 409)
      return jsonResponse({})
    })
    const user = userEvent.setup()
    await screen.findByText('No outbound records match these filters.')
    await user.selectOptions(screen.getByLabelText('Warehouse for outbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for outbound'), '6')
    await user.type(screen.getByLabelText('Outbound quantity'), '5')
    await user.click(screen.getByRole('button', { name: 'Record outbound' }))

    const quantity = screen.getByRole('spinbutton', { name: 'Outbound quantity' })
    expect(await screen.findByText('INSUFFICIENT_STOCK: Only 1 piece is available.')).toBeInTheDocument()
    for (const [control, message] of [
      [screen.getByLabelText('Warehouse for outbound'), 'Warehouse is unavailable.'],
      [screen.getByLabelText('Product for outbound'), 'Product is unavailable.'],
      [quantity, 'Quantity exceeds available stock.'],
      [screen.getByLabelText('Reference'), 'Reference was rejected.'],
      [screen.getByLabelText('Note'), 'Note was rejected.'],
    ]) {
      expect(control).toHaveAttribute('aria-invalid', 'true')
      expect(control).toHaveAccessibleDescription(message)
    }
  })

  it('shows backend 403 while preserving the authenticated session', async () => {
    renderRoleRoute('/inbounds', 'warehouse', (url, init) => {
      if (url.includes('/products?') || url.includes('/warehouses?') || url.includes('/inbounds?')) return lookup(url)
      if (url.endsWith('/inbounds') && init?.method === 'POST') return jsonResponse({ detail: { code: 'MOVEMENT_FORBIDDEN', message: 'Inbound is not permitted now.', fields: null } }, 403)
      return jsonResponse({})
    })
    const user = userEvent.setup()
    await screen.findByText('No inbound records match these filters.')
    await user.selectOptions(screen.getByLabelText('Warehouse for inbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for inbound'), '6')
    await user.type(screen.getByLabelText('Inbound quantity'), '5')
    await user.click(screen.getByRole('button', { name: 'Record inbound' }))

    expect(await screen.findByText('MOVEMENT_FORBIDDEN: Inbound is not permitted now.')).toBeInTheDocument()
    expect(screen.getByText(/warehouse@example.com/)).toBeInTheDocument()
    expect(localStorage.getItem('smart-warehouse-token')).toBe('warehouse-token')
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('blocks repeated submission while the first movement is pending', async () => {
    let resolvePost: ((response: Response) => void) | undefined
    let posts = 0
    renderRoleRoute('/inbounds', 'admin', (url, init) => {
      if (url.includes('/products?') || url.includes('/warehouses?') || url.includes('/inbounds?')) return lookup(url)
      if (url.endsWith('/inbounds') && init?.method === 'POST') {
        posts += 1
        return new Promise<Response>((resolve) => { resolvePost = (response) => resolve(response) })
      }
      return jsonResponse({})
    })
    const user = userEvent.setup()
    await screen.findByText('No inbound records match these filters.')
    await user.selectOptions(screen.getByLabelText('Warehouse for inbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for inbound'), '6')
    await user.type(screen.getByLabelText('Inbound quantity'), '5')
    await user.click(screen.getByRole('button', { name: 'Record inbound' }))
    expect(await screen.findByRole('button', { name: /recording/i })).toBeDisabled()
    expect(posts).toBe(1)
    resolvePost?.(jsonResponse({ id: 30, warehouse_id: 7, product_id: 6, quantity: 5, reference: null, note: null }, 201))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Inbound recorded. Movement #30.'))
  })

  it('requires a successfully loaded, nonempty lookup before movement can be submitted', async () => {
    let warehouseAttempts = 0
    const { fetchMock } = renderRoleRoute('/inbounds', 'warehouse', (url, init) => {
      if (url.includes('/products?')) return jsonResponse(lookupPage([product]))
      if (url.includes('/warehouses?')) {
        warehouseAttempts += 1
        return warehouseAttempts === 1
          ? jsonResponse({ detail: { code: 'LOOKUP_DOWN', message: 'Warehouse lookup unavailable.', fields: null } }, 503)
          : jsonResponse(lookupPage([warehouseRow]))
      }
      if (url.includes('/inbounds?')) return jsonResponse(page)
      if (url.endsWith('/inbounds') && init?.method === 'POST') return jsonResponse({}, 201)
      return jsonResponse({})
    })
    const user = userEvent.setup()
    await screen.findByText('No inbound records match these filters.')
    expect(await screen.findByText('Warehouse lookup unavailable.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Record inbound' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Retry warehouse lookup' }))
    await user.selectOptions(await screen.findByLabelText('Warehouse for inbound'), '7')
    await user.selectOptions(screen.getByLabelText('Product for inbound'), '6')
    await user.type(screen.getByLabelText('Inbound quantity'), '1')
    await user.click(screen.getByRole('button', { name: 'Record inbound' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true))
  })

  it('does not submit a movement when either successful lookup is empty', async () => {
    const { fetchMock } = renderRoleRoute('/inbounds', 'warehouse', (url, init) => {
      if (url.includes('/products?')) return jsonResponse(lookupPage([]))
      if (url.includes('/warehouses?')) return jsonResponse(lookupPage([warehouseRow]))
      if (url.includes('/inbounds?')) return jsonResponse(page)
      return jsonResponse({}, init?.method === 'POST' ? 201 : 200)
    })
    await screen.findByText('No products are available for movements.')
    expect(screen.getByRole('button', { name: 'Record inbound' })).toBeDisabled()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it.each([
    ['/inbounds', '/inbounds?', 'Inbound'],
    ['/outbounds', '/outbounds?', 'Outbound'],
  ] as const)('filters %s history with supported IDs and aware date bounds, resets page, and renders local time', async (path, endpoint, label) => {
    const movement = { id: 32, warehouse_id: 7, product_id: 6, quantity: 3, reference: 'REF-32', note: 'Checked', created_by_id: 14, created_at: '2026-09-29T02:45:00Z' }
    const { fetchMock } = renderRoleRoute(path, 'warehouse', (url) => {
      if (url.includes(endpoint)) return jsonResponse({ items: [movement], total: 41, page: url.includes('page=2') ? 2 : 1, page_size: 20 })
      if (url.includes('/products?')) return jsonResponse(lookupPage([product]))
      if (url.includes('/warehouses?')) return jsonResponse(lookupPage([warehouseRow]))
      return jsonResponse({})
    })
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: label })).toBeInTheDocument()
    expect(await screen.findByText('REF-32')).toBeInTheDocument()
    expect(screen.getByText(`Actor 14`)).toBeInTheDocument()
    expect(screen.getByText(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(movement.created_at)))).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await screen.findByText('Page 2 of 3')
    await user.selectOptions(screen.getByLabelText('Warehouse'), '7')
    await user.selectOptions(screen.getByLabelText('Product'), '6')
    await user.type(screen.getByLabelText('Created from'), '2026-09-28T08:00')
    await user.type(screen.getByLabelText('Created to'), '2026-09-29T08:00')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))

    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    const filteredUrl = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => {
      const parsed = new URL(url, 'http://localhost')
      return parsed.pathname.endsWith(endpoint.slice(0, -1)) && parsed.searchParams.get('warehouse_id') === '7'
    })
    expect(filteredUrl).toBeDefined()
    const params = new URL(filteredUrl!, 'http://localhost').searchParams
    expect(params.get('product_id')).toBe('6')
    expect(params.get('created_from')).toMatch(/Z$/)
    expect(params.get('created_to')).toMatch(/Z$/)
    expect(params.get('page')).toBe('1')
  })

  it.each([
    ['/inbounds', '/inbounds?', 'inbound'],
    ['/outbounds', '/outbounds?', 'outbound'],
  ] as const)('exposes a retry when %s history cannot load', async (path, endpoint, direction) => {
    let attempts = 0
    renderRoleRoute(path, 'warehouse', (url) => {
      if (url.includes(endpoint)) {
        attempts += 1
        return attempts === 1
          ? jsonResponse({ detail: { code: 'HISTORY_DOWN', message: `${direction} history is unavailable.`, fields: null } }, 503)
          : jsonResponse(page)
      }
      if (url.includes('/products?')) return jsonResponse(lookupPage([product]))
      if (url.includes('/warehouses?')) return jsonResponse(lookupPage([warehouseRow]))
      return jsonResponse({})
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(`${direction} history is unavailable.`)
    await userEvent.click(screen.getByRole('button', { name: `Retry ${direction} history` }))
    expect(await screen.findByText(`No ${direction} records match these filters.`)).toBeInTheDocument()
  })
})
