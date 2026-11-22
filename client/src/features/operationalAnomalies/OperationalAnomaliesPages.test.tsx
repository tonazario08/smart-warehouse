import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../app/AuthProvider'
import { router } from '../../app/router'

const prefix = '/api/v1/operational-anomalies'
const route = '/anomalies/operational'
const blank = {
  transaction_id: 41, state: 'unavailable', reason_code: 'NO_APPROVED_MODEL', evaluated_at: null,
  score: null, threshold: null, model_version: null, feature_version: null, base_value: null, contributions: null,
}
const flagged = {
  ...blank, state: 'flagged', reason_code: null, score: 0.75, threshold: 0.5, base_value: 0.5,
  contributions: [0.25, 0, 0, 0, 0, 0], model_version: 'verified-release', feature_version: 'feature/1',
}
const voucher = {
  outbound_id: 82, product_name: 'Sản phẩm A', product_sku: 'SKU-A', warehouse_code: 'KHO-A', warehouse_name: 'Kho A',
  quantity: 3, unit: 'each', occurred_at: '2026-11-22T09:22:00Z', performed_by_id: 12,
}
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
let active: ReturnType<typeof createMemoryRouter> | undefined
function mount(path: string, role: 'admin' | 'warehouse' | 'client' | null, endpoint: (url: URL) => Response) {
  if (role) localStorage.setItem('smart-warehouse-token', 'ops-token')
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    if (new Headers(init?.headers).get('Authorization') !== 'Bearer ops-token') return Promise.resolve(reply({}, 401))
    if (url.pathname.endsWith('/auth/me')) return Promise.resolve(reply({ id: 1, email: 'operator@example.test', role, is_active: true }))
    if (url.pathname.startsWith(prefix)) return Promise.resolve(endpoint(url))
    return Promise.resolve(reply({ items: [], total: 0, page: 1, page_size: 20 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  active = createMemoryRouter(router.routes, { initialEntries: [path] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  return { active, fetchMock }
}
afterEach(() => {
  active?.dispose()
  localStorage.clear()
  vi.unstubAllGlobals()
})

it('keeps lack of approved model distinct from a normal verdict and does not request the voucher', async () => {
  const { fetchMock } = mount(route, 'warehouse', url => url.pathname === prefix
    ? reply({ items: [blank], total: 1, page: 1, page_size: 20 })
    : reply({ ...blank, score: 0.5 })) // A stray score must never be shown for unavailable.
  expect(await screen.findByText('Chưa có mô hình để chấm.')).toBeVisible()
  fireEvent.click(screen.getByRole('link', { name: 'Giao dịch #41' }))
  expect(await screen.findByRole('heading', { name: 'Giao dịch xuất #41' })).toBeVisible()
  expect(await screen.findByText('Chưa có mô hình để chấm.')).toBeVisible()
  expect(screen.queryByText('Không vượt ngưỡng')).not.toBeInTheDocument()
  expect(screen.queryByText('Điểm bất thường')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/outbound'))).toBe(false)
})

it('shows SHAP and opens the server-verified voucher, never inferring voucher ID from transaction ID', async () => {
  mount(route + '/41', 'admin', url => url.pathname === prefix + '/41/outbound' ? reply(voucher) : reply(flagged))
  expect(await screen.findByRole('heading', { name: 'Giải thích đóng góp SHAP' })).toBeVisible()
  expect(screen.getByText('verified-release')).toBeVisible()
  const link = await screen.findByRole('link', { name: 'Mở phiếu xuất #82' })
  expect(link).toHaveAttribute('href', route + '/41/outbound')
  fireEvent.click(link)
  expect(await screen.findByRole('heading', { name: 'Phiếu xuất #82' })).toBeVisible()
  expect(screen.getByText('Sản phẩm A (SKU-A)')).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Phiếu xuất #41' })).not.toBeInTheDocument()
})

it.each([
  [404, 'Chưa liên kết được phiếu xuất đối chiếu.'],
  [403, 'Bạn không có quyền xem phiếu xuất.'],
])('does not expose voucher link after server status %s', async (status, copy) => {
  mount(route + '/41', 'warehouse', url => url.pathname.endsWith('/outbound')
    ? reply({ detail: { message: 'debug text' } }, status) : reply(flagged))
  expect(await screen.findByText(copy)).toBeVisible()
  expect(screen.queryByRole('link', { name: /Mở phiếu xuất/ })).not.toBeInTheDocument()
  expect(screen.queryByText('debug text')).not.toBeInTheDocument()
})

it.each([
  ['client', '/products'],
  [null, '/login'],
] as const)('blocks %s from hitting either endpoint on a direct voucher URL', async (role, landing) => {
  const { active: current, fetchMock } = mount(route + '/41/outbound', role, () => reply(voucher))
  await waitFor(() => expect(current.state.location.pathname).toBe(landing))
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes(prefix))).toBe(false)
  expect(screen.queryByText('Sản phẩm A (SKU-A)')).not.toBeInTheDocument()
})

it.each([
  ['pending', 'Chờ chấm', null],
  ['normal', 'Không vượt ngưỡng', 0.5],
  ['failed', 'Chấm không thành công', null],
])('shows %s without attaching a voucher', async (state, label, score) => {
  const { fetchMock } = mount(route + '/41', 'warehouse', () =>
    reply({ ...blank, state, reason_code: null, score, threshold: 0.5 }))
  expect(await screen.findByText(label)).toBeVisible()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/outbound'))).toBe(false)
})

it('labels synthetic test data consistently on the results list, detail and verified voucher', async () => {
  const synthetic = { ...flagged, dataset_class: 'synthetic_test' }
  mount(route, 'warehouse', url => {
    if (url.pathname === prefix) return reply({ items: [synthetic, { ...blank, transaction_id: 42 }], total: 2, page: 1, page_size: 20 })
    if (url.pathname.endsWith('/outbound')) return reply({ ...voucher, dataset_class: 'synthetic_test' })
    return reply(synthetic)
  })
  const badge = await screen.findByText('Dữ liệu tổng hợp kiểm thử')
  expect(badge.closest('tr')).toHaveTextContent('Giao dịch #41')
  fireEvent.click(screen.getByRole('link', { name: 'Giao dịch #41' }))
  expect(await screen.findByText('Dữ liệu tổng hợp kiểm thử')).toBeVisible()
  fireEvent.click(await screen.findByRole('link', { name: 'Mở phiếu xuất #82' }))
  expect(await screen.findByRole('heading', { name: 'Phiếu xuất #82' })).toBeVisible()
  expect(screen.getByText('Dữ liệu tổng hợp kiểm thử')).toBeVisible()
})
