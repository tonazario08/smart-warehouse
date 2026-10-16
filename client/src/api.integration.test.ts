import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules() })

describe('active Figma API contract', () => {
  it('authenticates catalogue list, detail and category reads explicitly', async () => {
    const seen: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      seen.push(new URL(String(input)).pathname)
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer catalogue-token')
      return response(String(input).includes('/products/7') ? { id: 7 } : { items: [], total: 0, page: 1, page_size: 100 })
    }))
    await api.products('catalogue-token', 1)
    await api.product('catalogue-token', 7)
    await api.categories('catalogue-token')
    expect(seen).toEqual(['/api/v1/products', '/api/v1/products/7', '/api/v1/categories'])
  })

  it.each(['productsAll', 'categories', 'suppliers', 'warehouses', 'stock', 'transactions', 'inbounds', 'outbounds'] as const)(
    'collects later pages for %s without returning a partial collection',
    async (method) => {
      const pages: number[] = []
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input)), page = Number(url.searchParams.get('page'))
        pages.push(page)
        expect(url.searchParams.get('page_size')).toBe('100')
        expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer page-token')
        return response({ items: page === 1 ? Array.from({ length: 100 }, (_, index) => ({ id: index + 1 })) : [{ id: 101 }], total: 101, page, page_size: 100 })
      }))
      const result = await api[method]('page-token')
      const items = Array.isArray(result) ? result : result.items
      expect(items).toHaveLength(101)
      expect(items[100].id).toBe(101)
      expect(pages).toEqual([1, 2])
    },
  )

  it('keeps structured status/code/fields but never renders raw server text', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: { code: 'REQUEST_VALIDATION_ERROR', message: 'Sensitive internal English detail', fields: { reference: ['Invalid value.'] } } }, 422)))
    const failure = await api.createInbound('token', { warehouse_id: 1, product_id: 2, quantity: 3, reference: null, note: null }).catch(error => error)
    expect(failure).toBeInstanceOf(ApiError)
    expect(failure.status).toBe(422)
    expect(failure.code).toBe('REQUEST_VALIDATION_ERROR')
    expect(failure.fields).toEqual({ reference: ['Invalid value.'] })
    expect(failure.serverMessage).toBe('Sensitive internal English detail')
    expect(failure.message).toMatch(/Dữ liệu|Thông tin/)
    expect(failure.message).not.toContain('Sensitive')
  })

  it.each([
    ['PRODUCT_SKU_CONFLICT', /Mã SKU/],
    ['WAREHOUSE_CONFLICT', /Mã hoặc tên kho/],
  ])('localizes the real backend conflict code %s', async (code, message) => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: { code, message: 'English backend message', fields: null } }, 409)))
    await expect(api.deleteProduct('token', 1)).rejects.toMatchObject({ code, message: expect.stringMatching(message as RegExp) })
  })

  it('localizes a stock ceiling conflict and keeps the mutation payload intact', async () => {
    const payload = { warehouse_id: 1, product_id: 2, quantity: 3, reference: 'PN-001', note: 'Ghi chú' }
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(JSON.parse(String(init?.body))).toEqual(payload)
      return response({ detail: { code: 'STOCK_QUANTITY_LIMIT_EXCEEDED', message: 'Stock quantity would exceed the supported limit.', fields: null } }, 409)
    }))
    await expect(api.createInbound('token', payload)).rejects.toMatchObject({ status: 409, code: 'STOCK_QUANTITY_LIMIT_EXCEEDED', message: expect.stringMatching(/giới hạn/) })
  })

  it('uses VITE_API_BASE_URL for the isolated backend', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:55440/api/v1/')
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => response({ id: 7 }))
    vi.stubGlobal('fetch', fetchMock)
    const configured = await import('./api')
    await configured.api.me('token')
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://127.0.0.1:55440/api/v1/auth/me')
  })
})
