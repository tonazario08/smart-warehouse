import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { router } from './router'

const product = { id: 7, sku: 'SP-7', name: 'Sản phẩm thử', description: 'Mô tả cần giữ', category_id: 101, supplier_id: 101, unit: 'cái', reorder_level: 3, is_active: false }
const warehouse = { id: 8, code: 'K-8', name: 'Kho thử', address: 'Địa chỉ', latitude: null, longitude: null, created_at: '2026-10-15T09:00:00Z', updated_at: '2026-10-15T09:00:00Z' }
const movement = { id: 9, warehouse_id: 8, product_id: 7, quantity: 2, reference: 'PN-THAT', note: 'Ghi chú thật', created_by_id: 42, created_at: '2026-10-15T09:00:00Z' }
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const page = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 100 })
let dispose: (() => void) | undefined
function mount(path: string, role?: 'admin' | 'warehouse' | 'client', overrides?: (url: URL, init?: RequestInit) => Response | undefined | Promise<Response | undefined>) {
  if (role) localStorage.setItem('smart-warehouse-token', 'route-token')
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    if (url.pathname.endsWith('/auth/login')) return reply({ access_token: 'route-token', user: { id: 1 } })
    if (new Headers(init?.headers).get('Authorization') !== 'Bearer route-token') return reply({ detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Missing token', fields: null } }, 401)
    const override = await overrides?.(url, init)
    if (override) return override
    if (url.pathname.endsWith('/auth/me')) return reply({ id: 1, email: 'operator@example.com', role: role ?? 'warehouse', is_active: true })
    if (url.pathname.endsWith('/products/7')) return reply(product)
    if (url.pathname.endsWith('/warehouses/8')) return reply(warehouse)
    if (url.pathname.endsWith('/products')) return reply(page([product]))
    if (url.pathname.endsWith('/warehouses')) return reply(page([warehouse]))
    if (url.pathname.endsWith('/categories') || url.pathname.endsWith('/suppliers')) {
      const number = Number(url.searchParams.get('page') ?? 1)
      return reply({ items: number === 1 ? Array.from({ length: 100 }, (_, index) => ({ id: index + 1, name: 'Mục ' + (index + 1), parent_id: null, email: null, phone: null, address: null })) : [{ id: 101, name: 'Mục cuối', parent_id: null, email: null, phone: null, address: null }], total: 101, page: number, page_size: 100 })
    }
    if (url.pathname.endsWith('/stock')) return reply(page([{ id: 1, warehouse_id: 8, product_id: 7, quantity: 5, created_at: '2026-10-15T09:00:00Z' }]))
    if (url.pathname.endsWith('/inbounds')) return reply(page([movement]))
    if (url.pathname.endsWith('/outbounds')) return reply(page([]))
    if (url.pathname.endsWith('/transactions')) return reply(page([{ id: 10, transaction_type: 'inbound', warehouse_id: 8, product_id: 7, quantity: 2, inbound_id: 9, outbound_id: null, created_by_id: 42, created_at: movement.created_at }]))
    if (url.pathname.endsWith('/dashboard/stats')) return reply({ product_count: 1, total_stock: 5, low_stock_count: 0 })
    throw new Error('Unexpected request path: ' + url.pathname)
  })
  vi.stubGlobal('fetch', fetchMock)
  const active = createMemoryRouter(router.routes, { initialEntries: [path] })
  dispose = () => active.dispose()
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  return { active, fetchMock }
}
afterEach(() => { dispose?.(); localStorage.clear(); vi.unstubAllGlobals() })

describe('active Figma routes and data', () => {
  it('redirects anonymous catalogue visits to the Vietnamese login without a shell', async () => {
    mount('/products')
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Điều hướng chính' })).not.toBeInTheDocument()
  })
  it.each([
    ['client', '/products/new', '/products'], ['client', '/warehouses/new', '/products'],
    ['client', '/inbound', '/products'], ['client', '/outbound/new', '/products'],
    ['warehouse', '/dashboard', '/inventory'], ['warehouse', '/products/7/edit', '/inventory'],
  ] as const)('guards %s at %s using the real Figma route tree', async (role, path, landing) => {
    const { active } = mount(path, role)
    await waitFor(() => expect(active.state.location.pathname).toBe(landing))
    expect(await screen.findByRole('navigation', { name: 'Điều hướng chính' })).toBeInTheDocument()
    if (role === 'client') expect(screen.queryAllByRole('link', { name: /Nhập kho|Xuất kho/ })).toHaveLength(0)
  })
  it('reads the real authenticated catalogue for a client without requesting supplier directory', async () => {
    const { fetchMock } = mount('/products', 'client')
    expect(await screen.findByText('Sản phẩm thử')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Xóa sản phẩm/ })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/suppliers'))).toBe(false)
  })
  it('loads all form lookup pages and preserves the complete edit payload', async () => {
    let written: unknown
    mount('/products/7/edit', 'admin', (url, init) => {
      if (url.pathname.endsWith('/products/7') && init?.method === 'PUT') { written = JSON.parse(String(init.body)); return reply(product) }
    })
    await screen.findByRole('button', { name: 'Lưu thay đổi' })
    await waitFor(() => expect(within(screen.getByLabelText('Danh mục')).getByRole('option', { name: 'Mục cuối' })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    await waitFor(() => expect(written).toEqual({ sku: 'SP-7', name: 'Sản phẩm thử', description: 'Mô tả cần giữ', category_id: 101, supplier_id: 101, unit: 'cái', reorder_level: 3, is_active: false }))
  })
  it('renders supported history reference, note and actor ID for operators', async () => {
    mount('/inventory/8/7', 'warehouse')
    expect(await screen.findByText('PN-THAT')).toBeInTheDocument()
    expect(screen.getByText('Ghi chú thật')).toBeInTheDocument()
    expect(screen.getByText('Tài khoản #42')).toBeInTheDocument()
    expect(screen.queryByText('Lịch sử biến động chưa khả dụng')).not.toBeInTheDocument()
  })
  it('never fetches restricted movement history for clients', async () => {
    const { fetchMock } = mount('/inventory/8/7', 'client')
    await screen.findByRole('heading', { name: 'Chi tiết tồn kho' })
    expect(screen.getByText(/không có quyền xem lịch sử/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => /\/(inbounds|outbounds|transactions)(\?|$)/.test(String(url)))).toBe(false)
  })
  it('shows supported transaction time rather than claiming it unavailable', async () => {
    mount('/dashboard', 'admin')
    await screen.findByRole('heading', { name: 'Giao dịch kho gần đây' })
    expect(screen.queryByText(/Thời gian và người thực hiện chưa khả dụng/)).not.toBeInTheDocument()
    expect(screen.getByText('Tài khoản #42')).toBeInTheDocument()
    expect(screen.getByText(/15\/10\/2026/)).toBeInTheDocument()
  })
  it('returns to the protected Figma form after actual provider login', async () => {
    const { active } = mount('/inbound/new')
    fireEvent.change(await screen.findByLabelText('Email'), { target: { value: 'operator@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await waitFor(() => expect(active.state.location.pathname).toBe('/inbound/new'))
    expect(await screen.findByRole('heading', { name: 'Tạo phiếu nhập' })).toBeInTheDocument()
  })
  it('does not let an old page mutation 401 log out a new same-token session', async () => {
    let finish!: (value: Response) => void
    const pending = new Promise<Response>(resolve => { finish = resolve })
    let writes = 0
    mount('/products/7/edit', 'admin', (url, init) => {
      if (url.pathname.endsWith('/products/7') && init?.method === 'PUT') { writes++; return pending }
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu thay đổi' }))
    await waitFor(() => expect(writes).toBe(1))
    const details = document.querySelector('details')!
    details.open = true
    fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }))
    fireEvent.change(await screen.findByLabelText('Email'), { target: { value: 'operator@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await screen.findByRole('button', { name: 'Lưu thay đổi' })
    await act(async () => { finish(reply({ detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Old mutation', fields: null } }, 401)) })
    expect(localStorage.getItem('smart-warehouse-token')).toBe('route-token')
    expect(screen.getByRole('heading', { name: 'Chỉnh sửa sản phẩm' })).toBeInTheDocument()
  })
  it.each([
    ['quantity', '2147483648'],
    ['reference', 'R'.repeat(121)],
  ])('does not submit movement %s beyond the real database bound', async (field, value) => {
    let writes = 0
    mount('/inbound/new', 'warehouse', (url, init) => {
      if (url.pathname.endsWith('/inbounds') && init?.method === 'POST') { writes++; return reply({ id: 1 }) }
    })
    const button = await screen.findByRole('button', { name: 'Xác nhận nhập kho' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Kho hàng' }), { target: { value: '8' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Sản phẩm' }), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Số lượng'), { target: { value: field === 'quantity' ? value : '1' } })
    if (field === 'reference') fireEvent.change(screen.getByLabelText('Mã phiếu'), { target: { value } })
    fireEvent.submit(button.closest('form')!)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(writes).toBe(0)
  })
})
