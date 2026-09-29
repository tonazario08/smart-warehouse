import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { screen, within } from '@testing-library/react'
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
  expect((await screen.findAllByRole('alert')).some((alert) => alert.textContent?.includes('Catalogue access is restricted.'))).toBe(true)
  expect(localStorage.getItem('smart-warehouse-token')).toBe('client-token')
})

it('does not request supplier lookups for clients', async () => {
  const { fetchMock } = renderRoleRoute('/products', 'client', (url) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 20 })
    return jsonResponse({})
  })
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/suppliers?'))).toBe(false)
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

it('associates every remaining product backend field error with its control', async () => {
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 20 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 20 })
    if (url.endsWith('/products') && init?.method === 'POST') return jsonResponse({ detail: { code: 'PRODUCT_FIELDS_INVALID', message: 'Product values were rejected.', fields: {
      description: ['Description is not accepted.'], supplier_id: ['Supplier is not approved.'], unit: ['Unit is not supported.'],
      reorder_level: ['Reorder level exceeds policy.'], is_active: ['Status cannot be changed.'],
    } } }, 422)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: /create product/i }))
  await screen.findByLabelText('Category')
  await user.type(screen.getByLabelText('SKU'), 'NEW-01')
  await user.type(screen.getByLabelText('Name'), 'New part')
  await user.type(screen.getByLabelText('Description'), 'Description')
  await user.selectOptions(screen.getByLabelText('Category'), '4')
  await user.selectOptions(screen.getByLabelText('Supplier'), '5')
  await user.type(screen.getByLabelText('Unit'), 'box')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Product values were rejected.')).toBeInTheDocument()
  const editor = within(screen.getByRole('form', { name: 'Create product' }))
  for (const [label, message] of [
    ['Description', 'Description is not accepted.'], ['Supplier', 'Supplier is not approved.'], ['Unit', 'Unit is not supported.'],
    ['Reorder level', 'Reorder level exceeds policy.'], ['Active', 'Status cannot be changed.'],
  ]) {
    const control = editor.getByLabelText(new RegExp(`^${label}`))
    expect(control).toHaveAttribute('aria-invalid', 'true')
    expect(control).toHaveAccessibleDescription(message)
  }
})

it('disables product submission and prevents a second create while pending', async () => {
  let resolveCreate: (() => void) | undefined
  let posts = 0
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 20 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 20 })
    if (url.endsWith('/products') && init?.method === 'POST') {
      posts += 1
      return new Promise((resolve) => { resolveCreate = () => resolve(jsonResponse(productRow, 201)) })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: /create product/i }))
  await user.type(screen.getByLabelText('SKU'), 'NEW-02')
  await user.type(screen.getByLabelText('Name'), 'New part')
  await user.selectOptions(screen.getByLabelText('Category'), '4')
  await user.type(screen.getByLabelText('Unit'), 'box')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  const saving = await screen.findByRole('button', { name: /saving/i })
  expect(saving).toBeDisabled()
  await user.click(saving)
  expect(posts).toBe(1)
  resolveCreate?.()
})

it('shows category and supplier lookup loading and retry states, and blocks submit when categories fail', async () => {
  let failCategories = true
  let failSuppliers = true
  let categoryReads = 0
  let supplierReads = 0
  renderRoleRoute('/products', 'admin', (url) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) {
      categoryReads += 1
      return failCategories ? jsonResponse({ detail: { code: 'CATEGORY_LOOKUP_FAILED', message: 'Categories are unavailable.', fields: null } }, 503) : jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    }
    if (url.includes('/suppliers?')) {
      supplierReads += 1
      return failSuppliers ? jsonResponse({ detail: { code: 'SUPPLIER_LOOKUP_FAILED', message: 'Suppliers are unavailable.', fields: null } }, 503) : jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  expect(await screen.findByText('Categories are unavailable.')).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: /retry categories/i })).toBeInTheDocument()
  expect(screen.getByText('Suppliers are unavailable.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /retry suppliers/i })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /create product/i }))
  expect(screen.getByRole('button', { name: 'Save product' })).toBeDisabled()
  expect(categoryReads).toBe(1)
  failCategories = false
  await user.click(screen.getByRole('button', { name: /retry categories/i }))
  expect(await within(screen.getByRole('form', { name: 'Create product' })).findByRole('option', { name: 'Hardware' })).toBeInTheDocument()
  expect(categoryReads).toBe(2)
  failSuppliers = false
  await user.click(screen.getByRole('button', { name: /retry suppliers/i }))
  expect(await within(screen.getByRole('form', { name: 'Create product' })).findByRole('option', { name: 'Northwind' })).toBeInTheDocument()
  expect(supplierReads).toBe(2)
})

it('announces pending category and supplier relationship lookups', async () => {
  let resolveCategories: ((response: Response) => void) | undefined
  let resolveSuppliers: ((response: Response) => void) | undefined
  renderRoleRoute('/products', 'admin', (url) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return new Promise((resolve) => { resolveCategories = resolve })
    if (url.includes('/suppliers?')) return new Promise((resolve) => { resolveSuppliers = resolve })
    throw new Error(`Unexpected request ${url}`)
  })

  await screen.findByText('SKU-001')
  expect(screen.getByRole('status', { name: /category options/i })).toHaveTextContent('Loading category options')
  expect(screen.getByRole('status', { name: /supplier options/i })).toHaveTextContent('Loading supplier options')

  resolveCategories?.(jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 }))
  resolveSuppliers?.(jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 }))
  expect(await screen.findByRole('option', { name: 'Hardware' })).toBeInTheDocument()
})

it.each(['admin', 'warehouse'] as const)('shows and retries supplier lookup failures for %s', async (role) => {
  let supplierReads = 0
  renderRoleRoute('/products', role, (url) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) {
      supplierReads += 1
      return supplierReads === 1
        ? jsonResponse({ detail: { code: 'SUPPLIER_LOOKUP_FAILED', message: 'Supplier options failed to load.', fields: null } }, 503)
        : jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 })
    }
    throw new Error(`Unexpected request ${url}`)
  })

  await screen.findByText('SKU-001')
  expect(await screen.findByText('Supplier options failed to load.')).toBeInTheDocument()
  expect(supplierReads).toBe(1)
  await userEvent.setup().click(screen.getByRole('button', { name: /retry suppliers/i }))
  expect(await screen.findByRole('option', { name: 'Northwind' })).toBeInTheDocument()
  expect(supplierReads).toBe(2)
})

it('explains an empty required category lookup and prevents product submission', async () => {
  let productCreates = 0
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page([], 0))
    if (url.includes('/categories?')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 })
    if (url.endsWith('/products') && init?.method === 'POST') {
      productCreates += 1
      return jsonResponse(productRow, 201)
    }
    throw new Error(`Unexpected request ${url}`)
  })

  await screen.findByText('No products match these filters.')
  expect(await screen.findByText(/no categories available/i)).toBeInTheDocument()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /create product/i }))
  expect(screen.getByRole('button', { name: 'Save product' })).toBeDisabled()
  expect(productCreates).toBe(0)
})

it('reports empty relationship lookups and keeps supplier optional', async () => {
  let createdInput: Record<string, unknown> | undefined
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page([], 0))
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 })
    if (url.endsWith('/products') && init?.method === 'POST') {
      createdInput = JSON.parse(String(init.body)) as Record<string, unknown>
      return jsonResponse(productRow, 201)
    }
    throw new Error(`Unexpected request ${url}`)
  })
  await screen.findByText('No products match these filters.')
  expect(await screen.findByRole('option', { name: 'Hardware' })).toBeInTheDocument()
  expect(screen.getByText(/supplier is optional/i)).toBeInTheDocument()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /create product/i }))
  await user.type(screen.getByLabelText('SKU'), 'NEW-03')
  await user.type(screen.getByLabelText('Name'), 'Optional source')
  await user.selectOptions(within(screen.getByRole('form', { name: 'Create product' })).getByLabelText('Category'), '4')
  await user.type(screen.getByLabelText('Unit'), 'box')
  expect(screen.getByRole('button', { name: 'Save product' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Product created.')).toBeInTheDocument()
  expect(createdInput?.supplier_id).toBeNull()
})

it('blocks editing a product with a supplier until a failed lookup is retried successfully', async () => {
  let supplierReads = 0
  let resolveInitialLookup: ((response: Response) => void) | undefined
  renderRoleRoute('/products', 'admin', (url) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) {
      supplierReads += 1
      if (supplierReads === 1) return new Promise((resolve) => { resolveInitialLookup = resolve })
      return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 })
    }
    throw new Error(`Unexpected request ${url}`)
  })

  await screen.findByText('SKU-001')
  expect(screen.getByRole('status', { name: /supplier options/i })).toHaveTextContent('Loading supplier options')
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /edit product sku-001/i }))
  const editor = within(screen.getByRole('form', { name: 'Edit product' }))
  expect(editor.getByRole('button', { name: 'Save product' })).toBeDisabled()

  resolveInitialLookup?.(jsonResponse({ detail: { code: 'SUPPLIER_LOOKUP_FAILED', message: 'Supplier lookup is temporarily unavailable.', fields: null } }, 503))
  expect(await screen.findByText('Supplier lookup is temporarily unavailable.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /retry suppliers/i })).toBeInTheDocument()
  expect(editor.getByRole('button', { name: 'Save product' })).toBeDisabled()

  await user.click(screen.getByRole('button', { name: /retry suppliers/i }))
  expect(await editor.findByRole('option', { name: 'Northwind' })).toBeInTheDocument()
  expect(editor.getByRole('button', { name: 'Save product' })).toBeEnabled()
  expect(supplierReads).toBe(2)
})

it('preserves the current supplier when its id is missing from lookup results', async () => {
  let updatedInput: Record<string, unknown> | undefined
  const otherSupplier = { ...supplierRow, id: 9, name: 'Eastwind' }
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [otherSupplier], total: 1, page: 1, page_size: 100 })
    if (url.endsWith('/products/6') && init?.method === 'PUT') {
      updatedInput = JSON.parse(String(init.body)) as Record<string, unknown>
      return jsonResponse(productRow)
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: /edit product sku-001/i }))
  const editor = within(screen.getByRole('form', { name: 'Edit product' }))
  const supplier = editor.getByLabelText('Supplier')
  expect(await editor.findByRole('option', { name: 'Current supplier #5' })).toBeInTheDocument()
  expect(supplier).toHaveValue('5')
  await user.click(editor.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Product updated.')).toBeInTheDocument()
  expect(updatedInput?.supplier_id).toBe(5)
})

it('removes an existing supplier only after the admin chooses no supplier', async () => {
  let updatedInput: Record<string, unknown> | undefined
  renderRoleRoute('/products', 'admin', (url, init) => {
    if (url.includes('/products?')) return jsonResponse(page())
    if (url.includes('/categories?')) return jsonResponse({ items: [categoryRow], total: 1, page: 1, page_size: 100 })
    if (url.includes('/suppliers?')) return jsonResponse({ items: [supplierRow], total: 1, page: 1, page_size: 100 })
    if (url.endsWith('/products/6') && init?.method === 'PUT') {
      updatedInput = JSON.parse(String(init.body)) as Record<string, unknown>
      return jsonResponse({ ...productRow, supplier_id: null })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: /edit product sku-001/i }))
  const editor = within(screen.getByRole('form', { name: 'Edit product' }))
  const supplier = await editor.findByLabelText('Supplier')
  expect(supplier).toHaveValue('5')
  await user.selectOptions(supplier, '')
  expect(supplier).toHaveValue('')
  await user.click(editor.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Product updated.')).toBeInTheDocument()
  expect(updatedInput?.supplier_id).toBeNull()
})
