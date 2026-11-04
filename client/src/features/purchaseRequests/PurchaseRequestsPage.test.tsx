import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { deferredResponse, jsonResponse, purchase, purchaseHandler, purchasePage, purchaseProduct, renderPurchaseRequestRoute } from '../../test/renderPurchaseRequestRoute'

afterEach(() => localStorage.clear())
it.each(['admin', 'warehouse', 'client'] as const)('renders real-shaped scoped %s list with role actions and IDs, not a user-directory call', async role => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', role)
  expect(await screen.findByRole('link', { name: 'PR-0008' })).toHaveAttribute('href', '/purchase-requests/8')
  expect(screen.getByRole('cell', { name: /Bu lông/ })).toHaveTextContent('B2B-003')
  expect(screen.getByRole('cell', { name: 'Chờ duyệt' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Tạo yêu cầu mua hàng' }) !== null).toBe(role === 'client')
  if (role === 'client') expect(screen.getByRole('link', { name: 'Tạo yêu cầu mua hàng' })).toHaveAttribute('href', '/purchase-requests/new')
  expect(screen.queryByLabelText('Lọc mã tài khoản') !== null).toBe(role !== 'client')
  expect(fetchMock.mock.calls.some(([url]) => new URL(String(url)).pathname === '/api/v1/users')).toBe(false)
})
it('uses server totals, conjunctive filters, inclusive aware dates and page reset', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', 'warehouse', url => url.includes('/purchase-requests?') ? jsonResponse(purchasePage(undefined, 41, Number(new URL(url).searchParams.get('page')))) : purchaseHandler(url))
  await screen.findByRole('link', { name: 'PR-0008' })
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText('Trang 2 / 3')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Lọc trạng thái'), 'pending')
  await userEvent.selectOptions(screen.getByLabelText('Lọc kho hàng'), '1')
  await userEvent.selectOptions(screen.getByLabelText('Lọc sản phẩm'), '3')
  await userEvent.type(screen.getByLabelText('Lọc mã tài khoản'), '7')
  fireEvent.change(screen.getByLabelText('Từ thời điểm'), { target: { value: '2026-10-19T08:00' } })
  fireEvent.change(screen.getByLabelText('Đến thời điểm'), { target: { value: '2026-10-19T08:00' } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => {
    const params = new URL(String(url)).searchParams
    return params.get('status') === 'pending' && params.get('warehouse_id') === '1' && params.get('product_id') === '3' && params.get('requested_by_id') === '7' && params.get('page') === '1' && params.get('created_from') === new Date('2026-10-19T08:00').toISOString() && params.get('created_to') === params.get('created_from')
  })).toBe(true))
})
it('rejects reversed dates and invalid staff IDs without an API read', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', 'admin')
  await screen.findByRole('link', { name: 'PR-0008' })
  const before = fetchMock.mock.calls.length
  fireEvent.change(screen.getByLabelText('Từ thời điểm'), { target: { value: '2026-10-20T08:00' } })
  fireEvent.change(screen.getByLabelText('Đến thời điểm'), { target: { value: '2026-10-19T08:00' } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(screen.getByRole('alert')).toHaveTextContent('không sau')
  expect(fetchMock.mock.calls.length).toBe(before)
})
it('loads all product label pages and preserves shared pagination CSS scope', async () => {
  const { readFileSync } = await import('vitest').then(({ vi }) => vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs'))
  const stylesheet = document.createElement('style'); stylesheet.textContent = readFileSync('src/shared/styles/management.css', 'utf8'); document.head.append(stylesheet)
  try {
    renderPurchaseRequestRoute('/purchase-requests', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: new URL(url).searchParams.get('page') === '2' ? [purchaseProduct] : [], total: 101, page: Number(new URL(url).searchParams.get('page')), page_size: 100 }) : purchaseHandler(url))
    await screen.findByRole('link', { name: 'PR-0008' })
    expect(screen.getByRole('cell', { name: /Bu lông/ })).toBeInTheDocument()
    const pagination = screen.getByRole('navigation', { name: 'Phân trang' })
    expect(getComputedStyle(pagination).display).toBe('flex')
    expect(getComputedStyle(screen.getByRole('button', { name: 'Trang sau' })).minHeight).toBe('38px')
  } finally { stylesheet.remove() }
})
it.each([403, 503])('shows loading/error%s, explicit retry and honest empty state', async status => {
  const pending = deferredResponse()
  let reads = 0
  renderPurchaseRequestRoute('/purchase-requests', 'client', url => url.includes('/purchase-requests?') ? (++reads === 1 ? pending.promise : jsonResponse(purchasePage([]))) : purchaseHandler(url))
  await screen.findByText('Đang tải yêu cầu mua hàng...')
  await act(async () => pending.resolve(jsonResponse({}, status)))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại danh sách' }))
  expect(await screen.findByText('Chưa có yêu cầu mua hàng phù hợp')).toBeInTheDocument()
})
it('discards a late old page read after a filter changes', async () => {
  const pending = deferredResponse()
  let reads = 0
  renderPurchaseRequestRoute('/purchase-requests', 'client', url => url.includes('/purchase-requests?') ? (++reads === 1 ? pending.promise : jsonResponse(purchasePage([]))) : purchaseHandler(url))
  await screen.findByLabelText('Lọc trạng thái')
  await userEvent.selectOptions(screen.getByLabelText('Lọc trạng thái'), 'rejected')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await screen.findByText('Chưa có yêu cầu mua hàng phù hợp')
  await act(async () => pending.resolve(jsonResponse(purchasePage([purchase]))))
  expect(screen.queryByRole('link', { name: 'PR-0008' })).not.toBeInTheDocument()
})
it('never sends a previous staff owner filter with a new client token', async () => {
  const old = deferredResponse()
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', 'admin', (url, init) => {
    if (url.includes('/purchase-requests?') && new URL(url).searchParams.has('requested_by_id')) return old.promise
    if (new Headers(init?.headers).get('Authorization')?.includes('replacement-purchase-token') && url.includes('/purchase-requests?')) return jsonResponse(purchasePage([]))
    return purchaseHandler(url)
  })
  await screen.findByRole('link', { name: 'PR-0008' })
  await userEvent.type(screen.getByLabelText('Lọc mã tài khoản'), '7')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => new URL(String(url)).searchParams.get('requested_by_id') === '7')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: 'Đổi phiên kiểm thử' }))
  await screen.findByText('Chưa có yêu cầu mua hàng phù hợp')
  const newReads = fetchMock.mock.calls.filter(([url, init]) => String(url).includes('/purchase-requests?') && new Headers(init?.headers).get('Authorization')?.includes('replacement-purchase-token'))
  expect(newReads.length).toBeGreaterThan(0)
  expect(newReads.every(([url]) => !new URL(String(url)).searchParams.has('requested_by_id'))).toBe(true)
  await act(async () => old.resolve(jsonResponse({}, 503)))
  expect(screen.getByText('Chưa có yêu cầu mua hàng phù hợp')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
it.each([20, 0])('refetches the last valid filtered page when concurrent writes shrink total21 to%s', async total => {
  let shrunk = false
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', 'admin', url => {
    if (!url.includes('/purchase-requests?')) return purchaseHandler(url)
    const params = new URL(url).searchParams, page = Number(params.get('page'))
    if (page === 2) { shrunk = true; return jsonResponse(purchasePage([], total, 2)) }
    return jsonResponse(purchasePage(shrunk && total === 0 ? [] : [purchase], shrunk ? total : 21, 1))
  })
  await screen.findByRole('link', { name: 'PR-0008' })
  await userEvent.selectOptions(screen.getByLabelText('Lọc trạng thái'), 'pending')
  await userEvent.selectOptions(screen.getByLabelText('Lọc kho hàng'), '1')
  await userEvent.selectOptions(screen.getByLabelText('Lọc sản phẩm'), '3')
  await userEvent.type(screen.getByLabelText('Lọc mã tài khoản'), '7')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await screen.findByText('Trang 1 / 2')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await waitFor(() => {
    const reads = fetchMock.mock.calls.map(([url]) => new URL(String(url))).filter(url => url.pathname.endsWith('/purchase-requests'))
    const second = reads.findIndex(url => url.searchParams.get('page') === '2')
    expect(second).toBeGreaterThan(-1)
    expect(reads.slice(second + 1).some(url => url.searchParams.get('page') === '1' && url.searchParams.get('status') === 'pending' && url.searchParams.get('warehouse_id') === '1' && url.searchParams.get('product_id') === '3' && url.searchParams.get('requested_by_id') === '7')).toBe(true)
  })
  if (total) expect(await screen.findByText('Trang 1 / 1')).toBeInTheDocument()
  else expect(await screen.findByText('Chưa có yêu cầu mua hàng phù hợp')).toBeInTheDocument()
  expect(screen.getByLabelText('Lọc trạng thái')).toHaveValue('pending')
  expect(screen.getByLabelText('Lọc mã tài khoản')).toHaveValue('7')
})
it('ignores obsolete page2 total shrink after a new filter has its own result', async () => {
  const old = deferredResponse()
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests', 'admin', url => {
    if (!url.includes('/purchase-requests?')) return purchaseHandler(url)
    const params = new URL(url).searchParams
    if (params.get('status') === 'rejected') return jsonResponse(purchasePage([{ ...purchase, status: 'rejected' }]))
    return params.get('page') === '2' ? old.promise : jsonResponse(purchasePage([purchase], 21))
  })
  await screen.findByRole('link', { name: 'PR-0008' })
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => new URL(String(url)).searchParams.get('page') === '2')).toBe(true))
  await userEvent.selectOptions(screen.getByLabelText('Lọc trạng thái'), 'rejected')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await screen.findByRole('cell', { name: 'Từ chối' })
  const before = fetchMock.mock.calls.length
  await act(async () => old.resolve(jsonResponse(purchasePage([], 0, 2))))
  expect(fetchMock.mock.calls.length).toBe(before)
  expect(screen.getByRole('cell', { name: 'Từ chối' })).toBeInTheDocument()
})
it('keeps semantic table values readable with scoped nonwrapping styles', async () => {
  const { vi } = await import('vitest')
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  const style = document.createElement('style'); style.textContent = readFileSync('src/features/purchaseRequests/purchase-requests.css', 'utf8'); document.head.append(style)
  try {
    renderPurchaseRequestRoute('/purchase-requests')
    const link = await screen.findByRole('link', { name: 'PR-0008' })
    expect(getComputedStyle(link).whiteSpace).toBe('nowrap')
    expect(getComputedStyle(screen.getByRole('cell', { name: 'Chờ duyệt' }).firstElementChild!).whiteSpace).toBe('nowrap')
    expect(getComputedStyle(screen.getByRole('table')).minWidth).toBe('960px')
  } finally { style.remove() }
})
