import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { approvedPurchase, deferredResponse, fulfilledPurchase, jsonResponse, purchase, purchaseHandler, renderPurchaseRequestRoute } from '../../test/renderPurchaseRequestRoute'

afterEach(() => localStorage.clear())
it.each([
  ['pending', 'Chờ duyệt'], ['approved', 'Đã duyệt'], ['rejected', 'Từ chối'], ['fulfilled', 'Đã xuất hàng'],
] as const)('shows persisted %s status and honest metadata', async (status, label) => {
  renderPurchaseRequestRoute('/purchase-requests/8', 'client', url => url.endsWith('/purchase-requests/8') ? jsonResponse(status === 'fulfilled' ? fulfilledPurchase : { ...purchase, status }) : purchaseHandler(url))
  expect(await screen.findByText(label, { exact: true })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Xuất hàng' })).not.toBeInTheDocument()
  if (status === 'fulfilled') { expect(screen.getByRole('heading', { name: 'Tồn kho tại thời điểm xuất' })).toBeInTheDocument(); expect(screen.getByText(/Phiếu xuất #11/)).toHaveTextContent('Giao dịch #21') }
})
it.each(['admin', 'warehouse', 'client'] as const)('keeps legacy %s detail read-only and does not fabricate fulfillment', async role => {
  renderPurchaseRequestRoute('/purchase-requests/8', role, url => url.endsWith('/purchase-requests/8') ? jsonResponse({ ...purchase, status: 'fulfilled', workflow_managed: false, note: null }) : purchaseHandler(url))
  expect(await screen.findByText(/Yêu cầu cũ chỉ có thể xem/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Duyệt yêu cầu|Từ chối yêu cầu|Xuất hàng/ })).not.toBeInTheDocument()
  expect(screen.getByText('Chưa có thông tin xuất hàng được ghi nhận')).toBeInTheDocument()
})
it.each(['admin', 'warehouse', 'client'] as const)('exposes only current %s role actions', async role => {
  renderPurchaseRequestRoute('/purchase-requests/8', role)
  await screen.findByText('PR-0008', { exact: true })
  expect(screen.queryByRole('button', { name: 'Duyệt yêu cầu' }) !== null).toBe(role === 'admin')
  expect(screen.queryByLabelText('Lý do từ chối') !== null).toBe(role === 'admin')
})
it('requires rejection reason; cancellation restores focus and pending locks competing actions', async () => {
  const pending = deferredResponse()
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/8', 'admin', (url, init) => init?.method === 'POST' ? pending.promise : purchaseHandler(url))
  const trigger = await screen.findByRole('button', { name: 'Từ chối yêu cầu' })
  await userEvent.click(trigger)
  expect(screen.getByRole('alert')).toHaveTextContent(/lý do/i)
  await userEvent.type(screen.getByLabelText('Lý do từ chối'), '  Hết nhu cầu  ')
  await userEvent.click(trigger)
  let dialog = screen.getByRole('dialog')
  expect(within(dialog).getByRole('button', { name: 'Hủy' })).toHaveFocus()
  fireEvent(dialog, new Event('cancel', { cancelable: true }))
  expect(trigger).toHaveFocus()
  await userEvent.click(trigger); dialog = screen.getByRole('dialog')
  await userEvent.dblClick(within(dialog).getByRole('button', { name: 'Xác nhận từ chối' }))
  expect(screen.getByLabelText('Lý do từ chối')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Duyệt yêu cầu' })).toBeDisabled()
  expect(within(dialog).getByRole('button', { name: 'Hủy' })).toBeDisabled()
  const writes = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(writes).toHaveLength(1)
  expect(String(writes[0][0])).toMatch(/\/8\/reject$/)
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({ rejection_reason: 'Hết nhu cầu' })
  await act(async () => pending.resolve(jsonResponse({ ...purchase, status: 'rejected', decision: { kind: 'rejected', actor_id: 1, decided_at: '2026-10-19T02:00:00Z', rejection_reason: 'Hết nhu cầu' } })))
  expect(await screen.findByText('Từ chối', { exact: true })).toBeInTheDocument()
})
it.each(['empty', 'error'])('preview %s is explicitly zero or unknown, never fabricated availability', async kind => {
  renderPurchaseRequestRoute('/purchase-requests/8', 'warehouse', url => url.endsWith('/purchase-requests/8') ? jsonResponse(approvedPurchase) : new URL(url).pathname.endsWith('/stock') ? jsonResponse(kind === 'empty' ? { items: [], total: 0, page: 1, page_size: 100 } : {}, kind === 'empty' ? 200 : 503) : purchaseHandler(url))
  await screen.findByRole('heading', { name: 'Tồn kho hiện tại' })
  if (kind === 'empty') expect(await screen.findByText('0 cái', { exact: true })).toBeInTheDocument()
  else { expect(await screen.findByText('Chưa xác định tồn kho')).toBeInTheDocument(); expect(screen.queryByText('0 cái', { exact: true })).not.toBeInTheDocument() }
  await userEvent.click(screen.getByRole('button', { name: 'Xuất hàng' }))
  expect(screen.getByRole('dialog')).toHaveTextContent(/kiểm tra lại/)
})
it.each(['approve', 'reject', 'fulfill'] as const)('unknown %s outcome uses explicit GET then same action/body retry even when state is unchanged', async action => {
  const initial = action === 'fulfill' ? approvedPurchase : purchase
  let posts = 0
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/8', 'admin', (url, init) => {
    if (init?.method === 'POST') return ++posts === 1 ? jsonResponse({}, 503) : jsonResponse(action === 'fulfill' ? fulfilledPurchase : action === 'approve' ? approvedPurchase : { ...purchase, status: 'rejected' })
    return url.endsWith('/purchase-requests/8') ? jsonResponse(initial) : purchaseHandler(url)
  })
  await screen.findByText('PR-0008', { exact: true })
  if (action === 'reject') await userEvent.type(screen.getByLabelText('Lý do từ chối'), '  Giữ lý do  ')
  await userEvent.click(screen.getByRole('button', { name: action === 'approve' ? 'Duyệt yêu cầu' : action === 'reject' ? 'Từ chối yêu cầu' : 'Xuất hàng' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: action === 'approve' ? 'Xác nhận duyệt' : action === 'reject' ? 'Xác nhận từ chối' : 'Xác nhận xuất hàng' }))
  await screen.findByRole('heading', { name: 'Chưa xác định kết quả' })
  expect(posts).toBe(1)
  await userEvent.click(screen.getByRole('button', { name: 'Tra cứu trạng thái' }))
  await screen.findByText(/không chứng minh thao tác trước đã thất bại/)
  expect(posts).toBe(1)
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại cùng thao tác' }))
  await waitFor(() => expect(posts).toBe(2))
  const writes = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(writes[1][0]).toBe(writes[0][0]); expect(writes[1][1]?.body).toBe(writes[0][1]?.body)
  expect(writes.every(([url]) => !String(url).includes('/outbound'))).toBe(true)
})
it('discards stale route read/write/finally instead of overwriting a different request', async () => {
  const pending = deferredResponse()
  const { active } = renderPurchaseRequestRoute('/purchase-requests/8', 'admin', (url, init) => init?.method === 'POST' ? pending.promise : url.endsWith('/purchase-requests/9') ? jsonResponse({ ...purchase, id: 9, request_number: 'PR-0009' }) : purchaseHandler(url))
  await userEvent.click(await screen.findByRole('button', { name: 'Duyệt yêu cầu' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận duyệt' }))
  await act(async () => { await active.navigate('/purchase-requests/9') })
  await screen.findByText('PR-0009', { exact: true })
  await act(async () => pending.resolve(jsonResponse(approvedPurchase)))
  expect(screen.getByText('PR-0009', { exact: true })).toBeInTheDocument()
  expect(screen.queryByText('Đã duyệt', { exact: true })).not.toBeInTheDocument()
})
it.each([200, 503])('old action%s cannot unlock the pending action on a new route', async oldStatus => {
  const old = deferredResponse(), next = deferredResponse()
  const { active, fetchMock } = renderPurchaseRequestRoute('/purchase-requests/8', 'admin', (url, init) => {
    if (init?.method === 'POST') return url.includes('/8/') ? old.promise : next.promise
    return url.endsWith('/purchase-requests/9') ? jsonResponse({ ...purchase, id: 9, request_number: 'PR-0009' }) : purchaseHandler(url)
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Duyệt yêu cầu' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận duyệt' }))
  await act(async () => { await active.navigate('/purchase-requests/9') })
  await userEvent.click(await screen.findByRole('button', { name: 'Duyệt yêu cầu' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận duyệt' }))
  await act(async () => old.resolve(jsonResponse(approvedPurchase, oldStatus)))
  expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Hủy' })).toBeDisabled()
  expect(screen.getByLabelText('Lý do từ chối')).toBeDisabled()
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(2)
  expect(screen.queryByRole('heading', { name: 'Chưa xác định kết quả' })).not.toBeInTheDocument()
  await act(async () => next.resolve(jsonResponse({ ...approvedPurchase, id: 9, request_number: 'PR-0009' })))
  expect(await screen.findByText('Đã duyệt', { exact: true })).toBeInTheDocument()
})
it('ignores a late detail read and a stale stock preview after route change', async () => {
  const oldRead = deferredResponse(), oldStock = deferredResponse()
  let reads = 0
  const { active } = renderPurchaseRequestRoute('/purchase-requests/8', 'warehouse', url => {
    if (url.endsWith('/purchase-requests/8')) return ++reads === 1 ? oldRead.promise : jsonResponse(approvedPurchase)
    if (url.endsWith('/purchase-requests/9')) return jsonResponse({ ...approvedPurchase, id: 9, request_number: 'PR-0009', warehouse_id: 2 })
    if (new URL(url).pathname.endsWith('/stock')) return oldStock.promise
    return purchaseHandler(url)
  })
  await screen.findByText('Đang tải yêu cầu mua hàng...')
  await act(async () => { await active.navigate('/purchase-requests/9') })
  await screen.findByRole('heading', { name: 'PR-0009' })
  await act(async () => oldRead.resolve(jsonResponse(approvedPurchase)))
  expect(screen.queryByRole('heading', { name: 'PR-0008' })).not.toBeInTheDocument()
  await act(async () => oldStock.resolve(jsonResponse({ items: [{ id: 1, warehouse_id: 1, product_id: 3, quantity: 10 }], total: 1, page: 1, page_size: 100 })))
  expect(await screen.findByText('0 cái', { exact: true })).toBeInTheDocument()
  expect(screen.queryByText('10 cái', { exact: true })).not.toBeInTheDocument()
})
it('restores editable reason after a definitive conflict and wraps long reason in the real stylesheet', async () => {
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  const style = document.createElement('style'); style.textContent = readFileSync('src/features/purchaseRequests/purchase-requests.css', 'utf8'); document.head.append(style)
  const reason = 'L'.repeat(1000)
  try {
    renderPurchaseRequestRoute('/purchase-requests/8', 'admin', (url, init) => init?.method === 'POST' ? jsonResponse({ detail: { code: 'PURCHASE_REQUEST_STATE_CONFLICT' } }, 409) : purchaseHandler(url))
    const input = await screen.findByLabelText('Lý do từ chối')
    fireEvent.change(input, { target: { value: reason } })
    await userEvent.click(screen.getByRole('button', { name: 'Từ chối yêu cầu' }))
    expect(getComputedStyle(within(screen.getByRole('dialog')).getByText(reason)).overflowWrap).toBe('anywhere')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận từ chối' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Trạng thái yêu cầu')
    expect(input).toBeEnabled(); expect(input).toHaveValue(reason)
  } finally { style.remove() }
})
it('recovers an actual persisted fulfilled representation by explicit GET without another POST', async () => {
  let reads = 0
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/8', 'warehouse', (url, init) => init?.method === 'POST' ? Promise.reject(new TypeError('lost acknowledgement (component simulation)')) : url.endsWith('/purchase-requests/8') ? jsonResponse(++reads === 1 ? approvedPurchase : fulfilledPurchase) : purchaseHandler(url))
  await userEvent.click(await screen.findByRole('button', { name: 'Xuất hàng' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận xuất hàng' }))
  await screen.findByRole('heading', { name: 'Chưa xác định kết quả' })
  await userEvent.click(screen.getByRole('button', { name: 'Tra cứu trạng thái' }))
  expect(await screen.findByRole('heading', { name: 'Tồn kho tại thời điểm xuất' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Chưa xác định kết quả' })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
})
it.each([403, 404, 503])('shows detail%s and recovers via an explicit read retry', async status => {
  let reads = 0
  renderPurchaseRequestRoute('/purchase-requests/8', 'client', url => url.endsWith('/purchase-requests/8') ? (++reads === 1 ? jsonResponse({}, status) : jsonResponse(purchase)) : purchaseHandler(url))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại chi tiết' }))
  expect(await screen.findByRole('heading', { name: 'PR-0008' })).toBeInTheDocument()
})
it('keeps the newer stock preview when an already-issued old-route stock request resolves last', async () => {
  const oldStock = deferredResponse(), newStock = deferredResponse()
  let stockReads = 0
  const { active } = renderPurchaseRequestRoute('/purchase-requests/8', 'warehouse', url => {
    if (url.endsWith('/purchase-requests/8')) return jsonResponse(approvedPurchase)
    if (url.endsWith('/purchase-requests/9')) return jsonResponse({ ...approvedPurchase, id: 9, request_number: 'PR-0009', warehouse_id: 2 })
    if (new URL(url).pathname.endsWith('/stock')) return ++stockReads === 1 ? oldStock.promise : newStock.promise
    return purchaseHandler(url)
  })
  await screen.findByRole('heading', { name: 'PR-0008' })
  await waitFor(() => expect(stockReads).toBe(1))
  await act(async () => { await active.navigate('/purchase-requests/9') })
  await screen.findByRole('heading', { name: 'PR-0009' })
  await waitFor(() => expect(stockReads).toBe(2))
  await act(async () => newStock.resolve(jsonResponse({ items: [{ id: 2, warehouse_id: 2, product_id: 3, quantity: 4 }], total: 1, page: 1, page_size: 100 })))
  expect(await screen.findByText('4 cái', { exact: true })).toBeInTheDocument()
  await act(async () => oldStock.resolve(jsonResponse({ items: [{ id: 1, warehouse_id: 1, product_id: 3, quantity: 10 }, { id: 2, warehouse_id: 2, product_id: 3, quantity: 99 }], total: 2, page: 1, page_size: 100 })))
  expect(screen.getByText('4 cái', { exact: true })).toBeInTheDocument()
  expect(screen.queryByText('10 cái', { exact: true })).not.toBeInTheDocument()
  expect(screen.queryByText('99 cái', { exact: true })).not.toBeInTheDocument()
})
it('constrains the detail grid and wraps a legal unbroken request number using the feature stylesheet', async () => {
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  const style = document.createElement('style'); style.textContent = readFileSync('src/features/purchaseRequests/purchase-requests.css', 'utf8'); document.head.append(style)
  const requestNumber = 'PR-' + 'A'.repeat(32)
  try {
    renderPurchaseRequestRoute('/purchase-requests/8', 'admin', url => url.endsWith('/purchase-requests/8') ? jsonResponse({ ...purchase, request_number: requestNumber, note: 'N'.repeat(2000) }) : purchaseHandler(url))
    const heading = await screen.findByRole('heading', { name: requestNumber })
    expect(getComputedStyle(heading).overflowWrap).toBe('anywhere')
    expect(getComputedStyle(heading.parentElement!).gridTemplateColumns).toBe('minmax(0, 1fr)')
    expect(getComputedStyle(heading).minWidth).toBe('0px')
  } finally { style.remove() }
})
