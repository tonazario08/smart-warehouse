import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { jsonResponse, renderTransferRoute, transfer, transferHandler, transferProduct, transferWarehouses } from '../../test/renderTransferRoute'

afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })
it('wraps legal unbroken product identities in the confirmation summary', async () => {
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  const stylesheet = document.createElement('style')
  stylesheet.textContent = readFileSync('src/features/transfers/transfers.css', 'utf8')
  document.head.append(stylesheet)
  const sku = 'S'.repeat(80), name = 'N'.repeat(200)
  try {
    renderTransferRoute('/transfers/new', 'warehouse', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: [{ ...transferProduct, sku, name }], total: 1, page: 1, page_size: 100 }) : transferHandler(url))
    await fillForm()
    await userEvent.click(screen.getByRole('button', { name: 'Xem lại chuyển kho' }))
    const summary = within(screen.getByRole('dialog')).getByText(sku + ' · ' + name + ' · Ngừng hoạt động')
    expect(getComputedStyle(summary).overflowWrap).toBe('anywhere')
  } finally { stylesheet.remove() }
})
async function fillForm() {
  await screen.findByRole('combobox', { name: 'Kho nguồn' })
  await userEvent.selectOptions(screen.getByLabelText('Kho nguồn'), '1')
  await userEvent.selectOptions(screen.getByLabelText('Kho đích'), '2')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), '3')
}
async function confirm() {
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại chuyển kho' }))
  const dialog = screen.getByRole('dialog')
  await userEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận chuyển kho' }))
}
it('loads all choice pages, labels inactive stock and safely cancels confirmation', async () => {
  const { fetchMock } = renderTransferRoute('/transfers/new', 'warehouse', url => {
    if (new URL(url).pathname.endsWith('/products')) return jsonResponse({ items: new URL(url).searchParams.get('page') === '2' ? [transferProduct] : [{ ...transferProduct, id: 4, sku: 'OTHER', is_active: true }], total: 101, page: Number(new URL(url).searchParams.get('page')), page_size: 100 })
    return transferHandler(url)
  })
  await fillForm()
  expect(screen.getByRole('option', { name: /CK-003.*Ngừng hoạt động/ })).toBeInTheDocument()
  expect(screen.getByLabelText('Tài khoản thực hiện')).toHaveValue('warehouse@example.com')
  expect(screen.getByLabelText('Tài khoản thực hiện')).toHaveAttribute('readonly')
  expect(await screen.findByText('7 cái')).toBeInTheDocument()
  expect(screen.getByText('5 cái')).toBeInTheDocument()
  const trigger = screen.getByRole('button', { name: 'Xem lại chuyển kho' })
  await userEvent.click(trigger)
  const dialog = screen.getByRole('dialog')
  expect(within(dialog).getByText(/CK-003/)).toHaveTextContent('Ngừng hoạt động')
  expect(within(dialog).getByRole('button', { name: 'Hủy' })).toHaveFocus()
  fireEvent(dialog, new Event('cancel', { bubbles: true, cancelable: true }))
  await waitFor(() => expect(trigger).toHaveFocus())
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
it('shows unknown rather than zero when stock lookup fails and retries it explicitly', async () => {
  let failed = true
  renderTransferRoute('/transfers/new', 'warehouse', url => new URL(url).pathname.endsWith('/stock') && failed ? jsonResponse({}, 503) : transferHandler(url))
  await fillForm()
  expect(await screen.findByText('Chưa xác định tồn kho')).toBeInTheDocument()
  expect(screen.queryByText('0 cái')).not.toBeInTheDocument()
  failed = false
  await userEvent.click(screen.getByRole('button', { name: 'Kiểm tra lại tồn kho' }))
  expect(await screen.findByText('7 cái')).toBeInTheDocument()
})
it('locks pending edits/cancel/double submit and navigates only after real success', async () => {
  let finish!: (response: Response) => void
  const { fetchMock, active } = renderTransferRoute('/transfers/new', 'admin', (url, init) => init?.method === 'POST' ? new Promise(resolve => { finish = resolve }) : transferHandler(url))
  await fillForm()
  await confirm()
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Hủy' })).toBeDisabled()
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Xác nhận chuyển kho' }))
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  await act(async () => finish(jsonResponse(transfer, 201)))
  await waitFor(() => expect(active.state.location.pathname).toBe('/transfers/8'))
  expect(await screen.findByText('Phiếu chuyển #8')).toBeInTheDocument()
})
it('retains failed draft and allows a corrected explicit confirmation after definitive rejection', async () => {
  renderTransferRoute('/transfers/new', 'warehouse', (url, init) => init?.method === 'POST' ? jsonResponse({ detail: { code: 'INSUFFICIENT_STOCK', fields: null } }, 409) : transferHandler(url))
  await fillForm()
  await userEvent.type(screen.getByLabelText('Mã phiếu'), 'GIỮ-LẠI')
  await confirm()
  expect(await screen.findByRole('alert')).toHaveTextContent(/Số lượng tồn kho/)
  expect(screen.getByLabelText('Mã phiếu')).toHaveValue('GIỮ-LẠI')
  expect(screen.getByLabelText('Số lượng')).toBeEnabled()
})
it('keeps exact key/body after uncertain POST, own-key404 and explicit retry', async () => {
  let posts = 0
  const { fetchMock, active } = renderTransferRoute('/transfers/new', 'warehouse', (url, init) => {
    if (init?.method === 'POST') return ++posts === 1 ? Promise.reject(new TypeError('connection lost')) : jsonResponse(transfer, 200)
    if (url.includes('/transfers/by-key/')) return jsonResponse({}, 404)
    return transferHandler(url)
  })
  await fillForm()
  await confirm()
  expect(await screen.findByText('Chưa xác định kết quả')).toBeInTheDocument()
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Tra cứu kết quả' }))
  expect(await screen.findByText(/Phiếu chưa được tìm thấy/)).toBeInTheDocument()
  expect(screen.getByLabelText('Số lượng')).toBeDisabled()
  expect(posts).toBe(1)
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại cùng yêu cầu' }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/transfers/8'))
  const calls = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(calls).toHaveLength(2)
  expect(calls[0][1]?.body).toBe(calls[1][1]?.body)
  expect(calls[0][1]?.headers).toEqual(calls[1][1]?.headers)
  expect(new Headers(calls[0][1]?.headers).get('Idempotency-Key')).toMatch(/^[0-9a-f-]{36}$/)
})
it('never submits on refresh and discards a stale stock result after context changes', async () => {
  let finish!: (response: Response) => void
  let reads = 0
  const { fetchMock } = renderTransferRoute('/transfers/new', 'warehouse', url => {
    if (new URL(url).pathname.endsWith('/stock')) return ++reads === 1 ? new Promise(resolve => { finish = resolve }) : jsonResponse({ items: [], total: 0, page: 1, page_size: 100 })
    if (new URL(url).pathname.endsWith('/warehouses')) return jsonResponse({ items: [...transferWarehouses, { ...transferWarehouses[0], id: 5, code: 'OTHER', name: 'Kho khác' }], total: 3, page: 1, page_size: 100 })
    return transferHandler(url)
  })
  await fillForm()
  await userEvent.selectOptions(screen.getByLabelText('Kho nguồn'), '5')
  expect((await screen.findAllByText('0 cái')).length).toBeGreaterThan(0)
  await act(async () => finish(transferHandler('http://localhost/api/v1/stock')))
  expect(screen.queryByText('7 cái')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

it('allocates no UUID until a validated confirmation is accepted', async () => {
  const uuid = vi.spyOn(crypto, 'randomUUID')
  const { active } = renderTransferRoute('/transfers/new', 'warehouse', (url, init) => init?.method === 'POST' ? jsonResponse(transfer, 201) : transferHandler(url))
  await screen.findByRole('combobox', { name: 'Kho nguồn' })
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại chuyển kho' }))
  expect(uuid).not.toHaveBeenCalled()
  await fillForm()
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại chuyển kho' }))
  expect(uuid).not.toHaveBeenCalled()
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Hủy' }))
  expect(uuid).not.toHaveBeenCalled()
  await confirm()
  await waitFor(() => expect(active.state.location.pathname).toBe('/transfers/8'))
  expect(uuid).toHaveBeenCalledTimes(1)
})

it('treats a complete valid empty stock page as observed zero', async () => {
  renderTransferRoute('/transfers/new', 'warehouse', url => new URL(url).pathname.endsWith('/stock') ? jsonResponse({ items: [], total: 0, page: 1, page_size: 100 }) : transferHandler(url))
  await fillForm()
  expect((await screen.findAllByText('0 cái')).length).toBe(2)
  expect(screen.getByText('Số lượng chuyển vượt tồn kho nguồn dự kiến.')).toBeInTheDocument()
})

it.each(['post', 'lookup'])('discards the old session result during pending %s', async stage => {
  let finish!: (response: Response) => void
  const { active, fetchMock } = renderTransferRoute('/transfers/new', 'warehouse', (url, init) => {
    if (init?.method === 'POST') return stage === 'post' ? new Promise(resolve => { finish = resolve }) : jsonResponse({}, 503)
    if (url.includes('/transfers/by-key/')) return new Promise(resolve => { finish = resolve })
    return transferHandler(url)
  })
  await fillForm(); await confirm()
  if (stage === 'lookup') {
    await screen.findByText('Chưa xác định kết quả')
    await userEvent.click(screen.getByRole('button', { name: 'Tra cứu kết quả' }))
  }
  await waitFor(() => expect(finish).toBeDefined())
  // Programmatic sign-out models external session invalidation. Native-modal
  // focus/inert behavior is verified separately in the real browser.
  fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất', hidden: true }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  await act(async () => finish(jsonResponse(transfer, 200)))
  expect(active.state.location.pathname).toBe('/login')
  expect(screen.queryByText('Phiếu chuyển #8')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
})
