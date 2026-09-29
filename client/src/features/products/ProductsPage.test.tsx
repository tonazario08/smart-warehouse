import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, productRow, categoryRow, supplierRow, renderRoleRoute } from '../../test/renderRoleRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items = [productRow], total = items.length, p = 1) => ({ items, total, page: p, page_size: 20 })

it.each(['warehouse', 'client'] as const)('shows products to %s without mutation controls', async (role) => {
  renderRoleRoute('/products', role, (url) => url.includes('/products?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /create product/i })).not.toBeInTheDocument()
})

it('keeps the authenticated session when the catalogue API returns 403', async () => {
  renderRoleRoute('/products', 'client', () => jsonResponse({ detail: { code: 'CATALOG_DENIED', message: 'Catalogue access is restricted.', fields: null } }, 403))
  expect(await screen.findByRole('alert')).toHaveTextContent('Catalogue access is restricted.')
  expect(localStorage.getItem('smart-warehouse-token')).toBe('client-token')
})

it('filters by supported fields and resets to the first page', async () => {
  const { fetchMock } = renderRoleRoute('/products', 'warehouse', (url) => {
    if (url.includes('/products?')) return jsonResponse(page([productRow], 25, url.includes('page=2') ? 2 : 1))
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 20 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 20 })
    return jsonResponse({})
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  await screen.findByText('Page 2 of 2')
  await user.type(screen.getByLabelText('Search products'), 'bolt')
  await user.selectOptions(screen.getByLabelText('Category filter'), '4')
  await user.selectOptions(screen.getByLabelText('Supplier filter'), '5')
  await user.selectOptions(screen.getByLabelText('Active status filter'), 'true')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
  const url = String(fetchMock.mock.calls.map(([input]) => input).find((input) => String(input).includes('search=bolt')))
  expect(url).toContain('category_id=4')
  expect(url).toContain('supplier_id=5')
  expect(url).toContain('is_active=true')
  expect(url).toContain('page=1')
})

it('loads product relationships, normalizes SKU, validates, creates, edits, and deletes with confirmation', async () => {
  let product = productRow
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['products', 'lookup'], page())
  const { fetchMock } = renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page([product]))
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 20 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 20 })
    if (url.endsWith('/products') && init?.method === 'POST') { product = { ...product, sku: 'BOLT-02' }; return jsonResponse(product, 201) }
    if (url.endsWith('/products/6') && init?.method === 'PUT') { product = { ...product, name: 'Nut' }; return jsonResponse(product) }
    if (url.endsWith('/products/6') && init?.method === 'DELETE') return new Response(null, { status: 204 })
    throw new Error(`Unexpected request ${url}`)
  }, queryClient)
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: /create product/i }))
  expect((await screen.findAllByRole('option', { name: 'Hardware' })).length).toBeGreaterThan(0)
  expect((await screen.findAllByRole('option', { name: 'Northwind' })).length).toBeGreaterThan(0)
  const sku = screen.getByLabelText('SKU')
  await user.type(sku, 'bolt-02')
  expect(sku).toHaveValue('BOLT-02')
  await user.type(screen.getByLabelText('Name'), 'Steel nut')
  await user.selectOptions(screen.getByLabelText('Category'), '4')
  await user.type(screen.getByLabelText('Unit'), 'piece')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('BOLT-02')).toBeInTheDocument()
  expect(queryClient.getQueryState(['products', 'lookup'])?.isInvalidated).toBe(true)
  await user.click(screen.getByRole('button', { name: /edit product bolt-02/i }))
  await user.clear(screen.getByLabelText('Name'))
  await user.type(screen.getByLabelText('Name'), 'Nut')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Nut')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /delete product bolt-02/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Confirm delete product' }))
  expect(await screen.findByText('Product deleted.')).toBeInTheDocument()
})
