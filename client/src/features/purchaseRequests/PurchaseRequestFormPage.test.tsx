import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { deferredResponse, jsonResponse, purchase, purchaseHandler, purchaseProduct, renderPurchaseRequestRoute } from '../../test/renderPurchaseRequestRoute'

afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })
async function fill() {
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), '3')
  await userEvent.type(screen.getByLabelText('Ghi chú'), '  Giao trong tuần  ')
}
async function review() { await userEvent.click(screen.getByRole('button', { name: 'Xem lại yêu cầu' })); return screen.getByRole('dialog') }
it('shows only active products and readonly current actor; allocates no key until a valid confirmation', async () => {
  const uuid = vi.spyOn(crypto, 'randomUUID')
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: [purchaseProduct, { ...purchaseProduct, id: 4, sku: 'INACTIVE', is_active: false }], total: 2, page: 1, page_size: 100 }) : purchaseHandler(url))
  await fill()
  expect(screen.queryByRole('option', { name: /INACTIVE/ })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Tài khoản yêu cầu')).toHaveAttribute('readonly')
  expect(screen.getByRole('status')).toHaveTextContent('không giữ chỗ')
  expect(screen.getByRole('link', { name: 'Hủy' })).toHaveAttribute('href', '/purchase-requests')
  const trigger = screen.getByRole('button', { name: 'Xem lại yêu cầu' })
  const dialog = await review()
  expect(within(dialog).getByRole('button', { name: 'Hủy' })).toHaveFocus()
  expect(uuid).not.toHaveBeenCalled()
  fireEvent(dialog, new Event('cancel', { cancelable: true }))
  expect(trigger).toHaveFocus()
  expect(uuid).not.toHaveBeenCalled()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
it.each(['0', '-1', '1.5', '2147483648'])('keeps invalid quantity %s editable without creating a key or request', async quantity => {
  const uuid = vi.spyOn(crypto, 'randomUUID')
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new')
  await fill(); fireEvent.change(screen.getByLabelText('Số lượng'), { target: { value: quantity } })
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại yêu cầu' }))
  expect(screen.getByRole('alert')).toBeInTheDocument()
  expect(uuid).not.toHaveBeenCalled()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
it.each([409, 422])('preserves editable normalized draft after definitive %s failure', async status => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', (url, init) => init?.method === 'POST' ? jsonResponse({ error: { code: 'PRODUCT_NOT_REQUESTABLE' } }, status) : purchaseHandler(url))
  await fill(); const dialog = await review()
  await userEvent.click(within(dialog).getByRole('button', { name: 'Gửi yêu cầu mua hàng' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Ghi chú')).toHaveValue('  Giao trong tuần  ')
  expect(screen.getByLabelText('Số lượng')).toBeEnabled()
})
it('locks pending context and submits exactly one accepted body despite double confirmation', async () => {
  const pending = deferredResponse()
  const { fetchMock, active } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', (url, init) => init?.method === 'POST' ? pending.promise : purchaseHandler(url))
  await fill(); const dialog = await review()
  await userEvent.dblClick(within(dialog).getByRole('button', { name: 'Gửi yêu cầu mua hàng' }))
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  expect(within(dialog).getByRole('button', { name: 'Hủy' })).toBeDisabled()
  const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(posts).toHaveLength(1)
  expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ warehouse_id: 1, product_id: 3, quantity: 3, note: 'Giao trong tuần' })
  await act(async () => pending.resolve(jsonResponse(purchase, 201)))
  await waitFor(() => expect(active.state.location.pathname).toBe('/purchase-requests/8'))
})
it.each([408, 503, 'network'] as const)('retains the exact key/body after %s and lookup404; never automatically resubmits', async failure => {
  let writes = 0
  const { fetchMock, active } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', (url, init) => {
    if (init?.method === 'POST') { if (++writes > 1) return jsonResponse({ ...purchase, status: 'approved' }); if (failure === 'network') return Promise.reject(new TypeError('offline')); return jsonResponse({}, failure) }
    if (url.includes('/by-key/')) return jsonResponse({}, 404)
    return purchaseHandler(url)
  })
  await fill(); await userEvent.click(within(await review()).getByRole('button', { name: 'Gửi yêu cầu mua hàng' }))
  await screen.findByRole('heading', { name: 'Chưa xác định kết quả' })
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  expect(writes).toBe(1)
  await userEvent.click(screen.getByRole('button', { name: 'Tra cứu kết quả' }))
  await screen.findByText(/có thể vẫn đang xử lý/)
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  expect(writes).toBe(1)
  expect(screen.getByText(/tải lại hoặc rời trang sẽ mất/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại cùng yêu cầu' }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/purchase-requests/8'))
  const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(posts).toHaveLength(2)
  expect(posts[1][1]?.body).toBe(posts[0][1]?.body)
  expect(new Headers(posts[1][1]?.headers).get('Idempotency-Key')).toBe(new Headers(posts[0][1]?.headers).get('Idempotency-Key'))
  expect(localStorage.getItem('smart-warehouse-token')).toBe('client-purchase-token')
  expect(localStorage.length).toBe(1)
})
it.each(['write', 'lookup'])('ignores old %s success/error/finally after a real session change', async stage => {
  const pending = deferredResponse()
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', (url, init) => {
    if (init?.method === 'POST') return stage === 'write' ? pending.promise : jsonResponse({}, 503)
    if (url.includes('/by-key/')) return pending.promise
    return purchaseHandler(url)
  })
  await fill(); await userEvent.click(within(await review()).getByRole('button', { name: 'Gửi yêu cầu mua hàng' }))
  if (stage === 'lookup') { await screen.findByRole('heading', { name: 'Chưa xác định kết quả' }); await userEvent.click(screen.getByRole('button', { name: 'Tra cứu kết quả' })) }
  await userEvent.click(screen.getByRole('button', { name: 'Đổi phiên kiểm thử' }))
  await waitFor(() => expect(screen.getByLabelText('Tài khoản yêu cầu')).toHaveValue('replacement@example.com'))
  await act(async () => pending.resolve(jsonResponse(purchase)))
  expect(screen.getByRole('heading', { name: 'Tạo yêu cầu mua hàng' })).toBeInTheDocument()
  expect(screen.getByLabelText('Số lượng')).toHaveValue(null)
  expect(screen.queryByRole('heading', { name: 'Chưa xác định kết quả' })).not.toBeInTheDocument()
})
it('renders long confirmation content using scoped wrapping', async () => {
  const longName = 'S'.repeat(200)
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  const style = document.createElement('style'); style.textContent = readFileSync('src/features/purchaseRequests/purchase-requests.css', 'utf8'); document.head.append(style)
  try {
    renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: [{ ...purchaseProduct, name: longName }], total: 1, page: 1, page_size: 100 }) : purchaseHandler(url))
    await fill(); const dialog = await review()
    expect(getComputedStyle(within(dialog).getByText(new RegExp(longName))).overflowWrap).toBe('anywhere')
  } finally { style.remove() }
})
it.each(['empty', 'inactive'])('shows %s product choices honestly and prevents confirmation', async kind => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: kind === 'empty' ? [] : [{ ...purchaseProduct, is_active: false }], total: kind === 'empty' ? 0 : 1, page: 1, page_size: 100 }) : purchaseHandler(url))
  expect(await screen.findByText('Chưa có sản phẩm đang hoạt động để yêu cầu.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Xem lại yêu cầu' })).toBeDisabled()
  expect(within(screen.getByRole('combobox', { name: 'Sản phẩm' })).getAllByRole('option')).toHaveLength(1)
})
