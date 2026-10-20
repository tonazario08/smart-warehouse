import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { renderPurchaseRequestRoute } from '../test/renderPurchaseRequestRoute'

afterEach(() => localStorage.clear())
it.each(['/purchase-requests', '/purchase-requests/new', '/purchase-requests/8'])('redirects anonymous %s outside the shell', async path => {
  const { active } = renderPurchaseRequestRoute(path, null)
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  expect(screen.queryByRole('navigation', { name: 'Điều hướng chính' })).not.toBeInTheDocument()
})
for (const role of ['admin', 'warehouse', 'client'] as const) it.each(['/purchase-requests', '/purchase-requests/8'])(role + ' hydrates protected direct %s with active nav', async path => {
  const { active, fetchMock } = renderPurchaseRequestRoute(path, role)
  const nav = await screen.findByRole('navigation', { name: 'Điều hướng chính' })
  await waitFor(() => expect(active.state.location.pathname).toBe(path))
  expect(within(nav).getByRole('link', { name: 'Yêu cầu mua hàng' })).toHaveAttribute('aria-current', 'page')
  expect(within(screen.getByRole('navigation', { name: 'Điều hướng vị trí' })).getByText('Yêu cầu mua hàng')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/auth/me'))).toBe(true)
  expect(fetchMock.mock.calls.some(([url]) => new URL(String(url)).pathname === '/api/v1/users')).toBe(false)
})
it.each(['admin', 'warehouse'] as const)('denies %s creation without a business POST', async role => {
  const { active, fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', role)
  await waitFor(() => expect(active.state.location.pathname).toBe('/inventory'))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
it.each(['0', '-1', '2147483648', '9'.repeat(20), 'bad'])('rejects malformed detail%s locally without business read', async id => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/' + id)
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã yêu cầu không hợp lệ')
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/purchase-requests'))).toBe(false)
})
