import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { renderTransferRoute } from '../test/renderTransferRoute'

afterEach(() => localStorage.clear())
const routes = ['/transfers', '/transfers/new', '/transfers/8']
it.each(routes)('redirects anonymous direct access %s outside AppShell', async path => {
  const { active } = renderTransferRoute(path, null)
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  expect(screen.queryByRole('navigation', { name: 'Điều hướng chính' })).not.toBeInTheDocument()
})
it.each(routes)('denies client direct access %s without a transfer read or write', async path => {
  const { active, fetchMock } = renderTransferRoute(path, 'client')
  await waitFor(() => expect(active.state.location.pathname).toBe('/products'))
  expect(screen.queryByRole('link', { name: 'Chuyển kho' })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/transfers'))).toBe(false)
})
for (const role of ['admin', 'warehouse'] as const) {
  it.each(routes)(role + ' keeps authorized direct transfer route %s and active navigation', async path => {
    const { active } = renderTransferRoute(path, role)
    const nav = await screen.findByRole('navigation', { name: 'Điều hướng chính' })
    await waitFor(() => expect(active.state.location.pathname).toBe(path))
    expect(within(nav).getByRole('link', { name: 'Chuyển kho' })).toHaveAttribute('aria-current', 'page')
    expect(within(screen.getByRole('navigation', { name: 'Điều hướng vị trí' })).getByText('Chuyển kho')).toBeInTheDocument()
    for (const name of ['Tồn kho', 'Kho hàng', 'Nhập kho', 'Xuất kho', 'Danh mục', 'Nhà cung cấp', 'Giao dịch']) expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
    if (role === 'admin') for (const name of ['Bảng điều khiển', 'Sản phẩm', 'Người dùng', 'Nhật ký quản trị']) expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
  })
}
