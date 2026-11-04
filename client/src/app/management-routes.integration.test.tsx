import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { jsonResponse, renderManagementRoute } from '../test/renderManagementRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const paths = [
  ['/users', 'Người dùng', ['admin']], ['/categories', 'Danh mục', ['admin', 'warehouse', 'client']],
  ['/suppliers', 'Nhà cung cấp', ['admin', 'warehouse']], ['/transactions', 'Giao dịch', ['admin', 'warehouse']], ['/audit', 'Nhật ký quản trị', ['admin']],
] as const

it.each(paths)('redirects anonymous %s to login', async path => {
  const { active } = renderManagementRoute(path, null, () => jsonResponse({}))
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeInTheDocument()
})
for (const role of ['admin', 'warehouse', 'client'] as const) {
  it.each(paths)(`${role} navigation and direct URL %s respects server grants`, async (path, label, roles) => {
    const { active, fetchMock } = renderManagementRoute(path, role, url => jsonResponse(url.includes('/dashboard/stats') ? { product_count: 0, total_stock: 0, low_stock_count: 0 } : { items: [], total: 0, page: 1, page_size: 100 }))
    const allowed = (roles as readonly string[]).includes(role)
    await waitFor(() => expect(active.state.location.pathname).toBe(allowed ? path : role === 'client' ? '/products' : '/inventory'))
    const nav = await screen.findByRole('navigation', { name: 'Điều hướng chính' })
    if (allowed) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page')
      expect(within(screen.getByRole('navigation', { name: 'Điều hướng vị trí' })).getByText(label)).toBeInTheDocument()
    } else {
      expect(within(nav).queryByRole('link', { name: label })).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url]) => new URL(String(url)).pathname === '/api/v1' + path)).toBe(false)
    }
  })
}
