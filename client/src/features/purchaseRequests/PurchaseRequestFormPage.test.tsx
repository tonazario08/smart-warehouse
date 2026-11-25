import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import * as L from 'leaflet'
import { deferredResponse, jsonResponse, purchase, purchaseHandler, purchaseNearest, purchaseProduct, renderPurchaseRequestRoute } from '../../test/renderPurchaseRequestRoute'

beforeEach(() => {
  // Leaflet uses SVG here; the browser test exercises installed Canvas and touch behavior.
  Object.defineProperty(L.Browser, 'svg', { configurable: true, value: true })
  const width = Object.getOwnPropertyDescriptor(Element.prototype, 'clientWidth')!.get!
  const height = Object.getOwnPropertyDescriptor(Element.prototype, 'clientHeight')!.get!
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockImplementation(function (this: Element) {
    return this.classList.contains('purchase-delivery-leaflet') ? 640 : width.call(this)
  })
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockImplementation(function (this: Element) {
    return this.classList.contains('purchase-delivery-leaflet') ? 360 : height.call(this)
  })
})
afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })
const syntheticLocation = { address: 'Địa chỉ mô phỏng', latitude: 10.5, longitude: 106.5 }
async function confirmManual(latitude = '10.5', longitude = '106.5') {
  fireEvent.change(screen.getByLabelText('Địa chỉ giao hàng'), { target: { value: '  ' + syntheticLocation.address + '  ' } })
  fireEvent.change(screen.getByLabelText('Vĩ độ điểm nhận'), { target: { value: latitude } })
  fireEvent.change(screen.getByLabelText('Kinh độ điểm nhận'), { target: { value: longitude } })
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận điểm giao' }))
}
async function fill() {
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), '3')
  await userEvent.type(screen.getByLabelText('Ghi chú'), '  Giao trong tuần  ')
  await confirmManual()
}
async function review() { await userEvent.click(screen.getByRole('button', { name: 'Xem lại yêu cầu' })); return screen.getByRole('dialog') }
it('shows only active products and readonly current actor; allocates no key until a valid confirmation', async () => {
  const uuid = vi.spyOn(crypto, 'randomUUID')
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: [purchaseProduct, { ...purchaseProduct, id: 4, sku: 'INACTIVE', is_active: false }], total: 2, page: 1, page_size: 100 }) : purchaseHandler(url))
  await fill()
  expect(screen.queryByRole('option', { name: /INACTIVE/ })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Tài khoản yêu cầu')).toHaveAttribute('readonly')
  expect(screen.getByText(/Gửi yêu cầu và duyệt không giữ chỗ/)).toBeInTheDocument()
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
  expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ warehouse_id: 1, product_id: 3, quantity: 3, note: 'Giao trong tuần', delivery_location: syntheticLocation })
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
const nearestPanel = () => within(screen.getByRole('heading', { name: 'Kho gần điểm nhận' }).parentElement as HTMLElement)
async function chooseProductAndPoint(quantity = '3', latitude = '10.5', longitude = '106.5') {
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), quantity)
  await confirmManual(latitude, longitude)
}
async function findNearest() {
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho gần có đủ tồn' }))
}
it.each(['1e2', '1.0', '2147483648'])('does not search for quantity %s rejected by submission', async quantity => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new')
  await chooseProductAndPoint()
  const quantityInput = screen.getByLabelText<HTMLInputElement>('Số lượng')
  fireEvent.change(quantityInput, { target: { value: quantity } })
  expect(quantityInput.value).toBe(quantity)
  await findNearest()
  expect(nearestPanel().getByText('Nhập số lượng hợp lệ trước khi tìm kho gần.')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/nearest-warehouses'))).toBe(false)
})

it('shows nearest warehouses in API order with distance, stock, Haversine and the exact private body', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new')
  await chooseProductAndPoint()
  await findNearest()
  const items = within(await nearestPanel().findByRole('list')).getAllByRole('listitem')
  expect(items).toHaveLength(2)
  expect(items[0]).toHaveTextContent('Kho khác (KHO-B)')
  expect(items[0]).toHaveTextContent('3,5 km')
  expect(items[0]).toHaveTextContent('còn 12 cái')
  expect(items[1]).toHaveTextContent('Kho yêu cầu (KHO-A)')
  expect(nearestPanel().getByText(/đường chim bay/)).toHaveTextContent(/haversine/)
  const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/nearest-warehouses'))
  expect(call).toBeDefined()
  expect(new URL(String(call![0])).search).toBe('')
  expect(call![1]?.method).toBe('POST')
  expect(JSON.parse(String(call![1]?.body))).toEqual({ product_id: 3, quantity: 3, latitude: 10.5, longitude: 106.5 })
  expect(new Headers(call![1]?.headers).get('Authorization')).toBe('Bearer client-purchase-token')
})
it('never reorders an empty result and keeps manual warehouse selection', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.includes('/nearest-warehouses') ? jsonResponse({ ...purchaseNearest, warehouses: [] }) : purchaseHandler(url))
  await chooseProductAndPoint()
  await findNearest()
  expect(await screen.findByText('Không có kho đang hoạt động nào đủ tồn cho số lượng này. Vui lòng chọn kho thủ công.')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  expect(screen.getByRole('combobox', { name: 'Kho hàng' })).toHaveValue('1')
})
it('fills the warehouse select from a suggestion and submits through the existing flow', async () => {
  const { fetchMock, active } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', (url, init) => init?.method === 'POST' && url.endsWith('/purchase-requests') ? jsonResponse(purchase, 201) : purchaseHandler(url))
  await chooseProductAndPoint()
  await findNearest()
  await nearestPanel().findByRole('list')
  await userEvent.click(nearestPanel().getByRole('button', { name: 'Chọn kho Kho khác' }))
  expect(screen.getByRole('combobox', { name: 'Kho hàng' })).toHaveValue('2')
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại yêu cầu' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Gửi yêu cầu mua hàng' }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/purchase-requests/8'))
  const post = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith('/purchase-requests') && init?.method === 'POST')
  expect(JSON.parse(String(post?.[1]?.body))).toEqual({ warehouse_id: 2, product_id: 3, quantity: 3, note: null, delivery_location: syntheticLocation })
})
it.each(['product', 'quantity', 'latitude'] as const)('clears stale suggestions when %s changes, dropping the auto-filled warehouse', async field => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => new URL(url).pathname.endsWith('/products') ? jsonResponse({ items: [purchaseProduct, { ...purchaseProduct, id: 4, sku: 'B2B-004' }], total: 2, page: 1, page_size: 100 }) : purchaseHandler(url))
  await chooseProductAndPoint()
  await findNearest()
  await nearestPanel().findByRole('list')
  await userEvent.click(nearestPanel().getByRole('button', { name: 'Chọn kho Kho khác' }))
  if (field === 'product') await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '4')
  if (field === 'quantity') fireEvent.change(screen.getByLabelText('Số lượng'), { target: { value: '4' } })
  if (field === 'latitude') await userEvent.type(screen.getByLabelText('Vĩ độ điểm nhận'), '1')
  expect(nearestPanel().queryByRole('list')).not.toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Kho hàng' })).toHaveValue('')
})
it('ignores a late suggestion response after inputs change', async () => {
  const first = deferredResponse(), second = deferredResponse()
  let calls = 0
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => {
    if (!url.includes('/nearest-warehouses')) return purchaseHandler(url)
    return ++calls === 1 ? first.promise : second.promise
  })
  await chooseProductAndPoint()
  await findNearest()
  fireEvent.change(screen.getByLabelText('Số lượng'), { target: { value: '4' } })
  await findNearest()
  await act(async () => second.resolve(jsonResponse({ ...purchaseNearest, warehouses: [{ warehouse_id: 2, code: 'KHO-MOI', name: 'Kho mới', available_quantity: 12, distance_km: 1 }] })))
  expect(await nearestPanel().findByText('Kho mới')).toBeInTheDocument()
  await act(async () => first.resolve(jsonResponse({ ...purchaseNearest, warehouses: [{ warehouse_id: 1, code: 'KHO-CU', name: 'Kho cũ', available_quantity: 12, distance_km: 9 }] })))
  expect(nearestPanel().queryByText('Kho cũ')).not.toBeInTheDocument()
  expect(nearestPanel().getByText('Kho mới')).toBeInTheDocument()
})
it('shows a Vietnamese error and keeps manual selection when the lookup fails', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.includes('/nearest-warehouses') ? jsonResponse({ detail: { code: 'PRODUCT_NOT_FOUND' } }, 404) : purchaseHandler(url))
  await chooseProductAndPoint()
  await findNearest()
  expect(await nearestPanel().findByText('Không tìm thấy sản phẩm.')).toBeInTheDocument()
  expect(nearestPanel().queryByRole('list')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/nearest-warehouses'))).toHaveLength(1)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  expect(screen.getByRole('combobox', { name: 'Kho hàng' })).toHaveValue('1')
})
it('keeps a manually chosen warehouse after a lookup and refuses an unknown suggestion', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.includes('/nearest-warehouses') ? jsonResponse({ ...purchaseNearest, warehouses: [{ warehouse_id: 999, code: 'GONE', name: 'Kho đã xóa', available_quantity: 5, distance_km: 1 }] }) : purchaseHandler(url))
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  await chooseProductAndPoint()
  await findNearest()
  expect(await nearestPanel().findByText('Kho đã xóa')).toBeInTheDocument()
  await userEvent.click(nearestPanel().getByRole('button', { name: 'Chọn kho Kho đã xóa' }))
  expect(nearestPanel().getByText('Kho gợi ý không còn trong danh sách kho. Vui lòng tải lại biểu mẫu hoặc chọn kho thủ công.')).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Kho hàng' })).toHaveValue('1')
})
it.each([['', '106.5'], ['10.5', ''], ['91', '106.5'], ['10.5', '181'], ['abc', '106.5']])('rejects receive coordinates %s / %s without calling the API', async (latitude, longitude) => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new')
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), '3')
  if (latitude) await userEvent.type(screen.getByLabelText('Vĩ độ điểm nhận'), latitude)
  if (longitude) await userEvent.type(screen.getByLabelText('Kinh độ điểm nhận'), longitude)
  await findNearest()
  expect(nearestPanel().getByText('Nhập vĩ độ (-90 đến 90) và kinh độ (-180 đến 180) hợp lệ.')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/nearest-warehouses'))).toBe(false)
})

it('renders independent explicit controls for device permission and point confirmation', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new')
  expect(await screen.findByRole('button', { name: 'Dùng vị trí hiện tại' })).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Xác nhận điểm giao' })).toBeEnabled()
})

const publicMatch = { label: '135 Nam Kỳ Khởi Nghĩa, TP. Hồ Chí Minh', latitude: 10.7770348, longitude: 106.695488, precision: 'house_number' }
const mapFixture = {
  state: 'available', bounds: { west: 106.64, south: 10.72, east: 106.76, north: 10.82 },
  roads: [{ name: 'Đường công cộng thử nghiệm', points: [[106.65, 10.75], [106.66, 10.76]] }],
  places: [{ name: 'Địa danh thử nghiệm', kind: 'landmark', point: [106.7, 10.77] }], areas: [],
  attribution: '© OpenStreetMap contributors', license_url: 'https://www.openstreetmap.org/copyright',
}

it('previews one verified match without confirming or using staff GIS; exact address is posted only on demand', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => {
    if (url.endsWith('/geocode-delivery-address')) return jsonResponse({ status: 'matches', candidates: [publicMatch] })
    if (url.endsWith('/delivery-map')) return jsonResponse(mapFixture)
    return purchaseHandler(url)
  })
  await screen.findByRole('option', { name: /B2B-003/ })
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '1')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '3')
  await userEvent.type(screen.getByLabelText('Số lượng'), '3')
  const address = screen.getByLabelText('Địa chỉ giao hàng')
  fireEvent.change(address, { target: { value: '135 nam ky khoi nghia' } })
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/geocode-delivery-address'))).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'Tìm địa chỉ' }))
  expect(await screen.findByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent('10.7770348, 106.695488')
  const map = await screen.findByRole('application', { name: 'Bản đồ chọn ghim giao hàng' })
  expect(map).toHaveAttribute('data-delivery-map-renderer', 'leaflet')
  expect(map.querySelector('.leaflet-overlay-pane path')).toBeInTheDocument()
  expect(address).toHaveValue('135 nam ky khoi nghia')
  const search = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/geocode-delivery-address'))!
  expect(new URL(String(search[0])).search).toBe('')
  expect(search[1]).toMatchObject({ method: 'POST', cache: 'no-store' })
  expect(JSON.parse(String(search[1]?.body))).toEqual({ address: '135 nam ky khoi nghia' })
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/gis/'))).toBe(false)
  await findNearest()
  expect(screen.getByText('Xác nhận điểm giao trước khi tìm kho gần.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Xem lại yêu cầu' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận điểm giao' }))
  expect(await review()).toHaveTextContent('135 nam ky khoi nghia')
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  expect(localStorage.length).toBe(1)
})

it('requests device location only by button, ignores a late callback and previews accuracy before confirmation', async () => {
  let callback!: PositionCallback
  const locate = vi.fn((next: PositionCallback) => { callback = next })
  const geolocation = Object.getOwnPropertyDescriptor(navigator, 'geolocation')
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: locate } })
  try {
    renderPurchaseRequestRoute('/purchase-requests/new')
    const button = await screen.findByRole('button', { name: 'Dùng vị trí hiện tại' })
    expect(locate).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Địa chỉ giao hàng'), { target: { value: 'Địa chỉ không có trong mẫu' } })
    await userEvent.click(button)
    expect(locate).toHaveBeenCalledTimes(1)
    expect(locate.mock.calls[0]).toHaveLength(3)
    await userEvent.click(screen.getByRole('button', { name: 'Xóa điểm giao' }))
    const position = { coords: { latitude: 10.77, longitude: 106.7, accuracy: 16.2 }, timestamp: 0 } as GeolocationPosition
    await act(async () => callback(position))
    expect(screen.queryByLabelText('Ghim điểm giao đang chọn')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Địa chỉ giao hàng'), { target: { value: 'Địa chỉ mới' } })
    await userEvent.click(button)
    await act(async () => callback(position))
    expect(screen.getByText(/Độ chính xác ước tính: ±17 m/)).toBeInTheDocument()
    expect(screen.queryByText(/Đã xác nhận điểm giao:/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Xác nhận điểm giao' }))
    expect(screen.getByText('Đã xác nhận điểm giao: Địa chỉ mới')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Địa chỉ giao hàng'), { target: { value: 'Địa chỉ sửa' } })
    expect(screen.queryByLabelText('Ghim điểm giao đang chọn')).not.toBeInTheDocument()
    expect(screen.queryByText(/Đã xác nhận điểm giao:/)).not.toBeInTheDocument()
  } finally {
    if (geolocation) Object.defineProperty(navigator, 'geolocation', geolocation)
    else Reflect.deleteProperty(navigator, 'geolocation')
  }
})

it('keeps manual fallback when device position permission is denied', async () => {
  const geolocation = Object.getOwnPropertyDescriptor(navigator, 'geolocation')
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
    getCurrentPosition: vi.fn((_success: PositionCallback, failure: PositionErrorCallback) => failure({ code: 1 } as GeolocationPositionError)),
  } })
  try {
    renderPurchaseRequestRoute('/purchase-requests/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Dùng vị trí hiện tại' }))
    expect(screen.getByText(/Bạn chưa cho phép dùng vị trí/)).toBeInTheDocument()
    await confirmManual()
    expect(screen.getByText('Đã xác nhận điểm giao: Địa chỉ mô phỏng')).toBeInTheDocument()
  } finally {
    if (geolocation) Object.defineProperty(navigator, 'geolocation', geolocation)
    else Reflect.deleteProperty(navigator, 'geolocation')
  }
})

it('offers an explicit internal address lookup without sending a request on typing', async () => {
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new')
  const address = await screen.findByLabelText('Địa chỉ giao hàng')
  fireEvent.change(address, { target: { value: 'địa chỉ kiểm thử' } })
  expect(screen.getByRole('button', { name: 'Tìm địa chỉ' })).toBeEnabled()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/geocode-delivery-address'))).toBe(false)
})

it('requires a choice for ambiguous matches and marks approximate pins without replacing the typed address', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/geocode-delivery-address')
    ? jsonResponse({ status: 'matches', candidates: [publicMatch, { ...publicMatch, label: 'Đường công cộng mẫu', precision: 'approximate', latitude: 10.775 }] })
    : purchaseHandler(url))
  const address = await screen.findByLabelText('Địa chỉ giao hàng')
  await userEvent.type(address, 'đường mơ hồ')
  await userEvent.keyboard('{Enter}')
  const list = await screen.findByRole('list', { name: 'Địa chỉ gợi ý' })
  expect(screen.queryByLabelText('Ghim điểm giao đang chọn')).not.toBeInTheDocument()
  const approximate = within(list).getByRole('button', { name: /Đường công cộng mẫu · Xấp xỉ/ })
  approximate.focus()
  await userEvent.keyboard('{Enter}')
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent('10.775, 106.695488')
  expect(address).toHaveValue('đường mơ hồ')
  expect(approximate).toHaveAttribute('aria-pressed', 'true')
  const confirm = screen.getByRole('button', { name: 'Xác nhận điểm giao' })
  expect(confirm).toBeDisabled()
  const acknowledgment = screen.getByRole('checkbox', { name: /chỉ là điểm tham khảo trên đường/ })
  await userEvent.click(acknowledgment)
  expect(confirm).toBeEnabled()
  await userEvent.click(within(list).getByRole('button', { name: /135 Nam Kỳ/ }))
  await userEvent.click(approximate)
  expect(screen.getByRole('checkbox', { name: /chỉ là điểm tham khảo trên đường/ })).not.toBeChecked()
  expect(confirm).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox', { name: /chỉ là điểm tham khảo trên đường/ }))
  await userEvent.click(confirm)
  expect(screen.getByText('Đã xác nhận điểm giao: đường mơ hồ')).toBeInTheDocument()
})

it('ignores a late geocode response after a later manual coordinate paste', async () => {
  const pending = deferredResponse()
  const { fetchMock } = renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/geocode-delivery-address')
    ? pending.promise : purchaseHandler(url))
  const address = await screen.findByLabelText('Địa chỉ giao hàng')
  fireEvent.change(address, { target: { value: 'Địa chỉ do khách nhập' } })
  await userEvent.click(screen.getByRole('button', { name: 'Tìm địa chỉ' }))
  await userEvent.type(screen.getByLabelText('Dán tọa độ (vĩ độ, kinh độ)'), '10.78, 106.7')
  await userEvent.click(screen.getByRole('button', { name: 'Dùng tọa độ đã dán' }))
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent('10.78, 106.7')
  expect(fetchMock.mock.calls.find(([url]) => String(url).endsWith('/geocode-delivery-address'))?.[1]?.signal?.aborted).toBe(true)
  await act(async () => pending.resolve(jsonResponse({ status: 'matches', candidates: [publicMatch] })))
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent('10.78, 106.7')
  expect(address).toHaveValue('Địa chỉ do khách nhập')
  expect(screen.queryByText(/Đã xác nhận điểm giao/)).not.toBeInTheDocument()
})

it.each(['no_match', 'unavailable'])('does not manufacture a pin on %s and lets keyboard adjust the local map', async status => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/geocode-delivery-address')
    ? jsonResponse({ status, candidates: [] }) : url.endsWith('/delivery-map') ? jsonResponse(mapFixture) : purchaseHandler(url))
  const map = await screen.findByRole('application', { name: 'Bản đồ chọn ghim giao hàng' })
  const address = screen.getByLabelText('Địa chỉ giao hàng')
  fireEvent.change(address, { target: { value: 'Không có địa chỉ' } })
  await userEvent.click(screen.getByRole('button', { name: 'Tìm địa chỉ' }))
  expect(await screen.findByText(status === 'no_match' ? /Không tìm thấy địa chỉ/ : /Chưa có dữ liệu tra địa chỉ/)).toBeInTheDocument()
  expect(map.querySelector('.purchase-delivery-leaflet-pin')).toBeNull()
  map.focus()
  await userEvent.keyboard('{ArrowUp}')
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent(/Ghim 10\.77/)
  expect(address).toHaveValue('Không có địa chỉ')
})

it('changes the viewport by zoom or keyboard pan without changing a confirmed address or pin', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/delivery-map') ? jsonResponse(mapFixture) : purchaseHandler(url))
  const map = await screen.findByRole('application', { name: 'Bản đồ chọn ghim giao hàng' })
  await confirmManual('10.77', '106.7')
  const address = screen.getByLabelText('Địa chỉ giao hàng')
  expect(map.querySelector('.purchase-delivery-leaflet-pin')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Về ghim' }))
  await userEvent.click(screen.getByRole('button', { name: 'Phóng to' }))
  map.focus()
  await userEvent.keyboard('{Shift>}{ArrowRight}{/Shift}')
  await userEvent.click(screen.getByRole('button', { name: 'Về vùng phủ' }))
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).toHaveTextContent('10.77, 106.7')
  expect(screen.getByText('Đã xác nhận điểm giao: Địa chỉ mô phỏng')).toBeInTheDocument()
  map.focus()
  await userEvent.keyboard('{ArrowUp}')
  expect(screen.getByLabelText('Ghim điểm giao đang chọn')).not.toHaveTextContent('10.77, 106.7')
  expect(address).toHaveValue('  Địa chỉ mô phỏng  ')
  expect(screen.queryByText(/Đã xác nhận điểm giao/)).not.toBeInTheDocument()
})

it('blocks a single approximate preview until acknowledged or deliberately relocated', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/geocode-delivery-address')
    ? jsonResponse({ status: 'matches', candidates: [{ ...publicMatch, precision: 'approximate' }] }) : purchaseHandler(url))
  const address = await screen.findByLabelText('Địa chỉ giao hàng')
  fireEvent.change(address, { target: { value: 'Đường mẫu' } })
  await userEvent.click(screen.getByRole('button', { name: 'Tìm địa chỉ' }))
  await screen.findByLabelText('Ghim điểm giao đang chọn')
  const confirm = screen.getByRole('button', { name: 'Xác nhận điểm giao' })
  expect(confirm).toBeDisabled()
  const paste = screen.getByLabelText('Dán tọa độ (vĩ độ, kinh độ)')
  fireEvent.change(paste, { target: { value: '10.7770348, 106.695488' } })
  await userEvent.click(screen.getByRole('button', { name: 'Dùng tọa độ đã dán' }))
  expect(confirm).toBeDisabled()
  fireEvent.change(paste, { target: { value: '10.78, 106.7' } })
  await userEvent.click(screen.getByRole('button', { name: 'Dùng tọa độ đã dán' }))
  expect(confirm).toBeEnabled()
  expect(screen.queryByRole('checkbox', { name: /chỉ là điểm tham khảo trên đường/ })).not.toBeInTheDocument()
  expect(address).toHaveValue('Đường mẫu')
})

it('does not present the old unlabeled sparse response as a public Leaflet map', async () => {
  renderPurchaseRequestRoute('/purchase-requests/new', 'client', url => url.endsWith('/delivery-map') ? jsonResponse({
    state: 'available', bounds: [106.64, 10.72, 106.76, 10.82], segments: [[[106.65, 10.75], [106.66, 10.76]]],
    attribution: mapFixture.attribution, license_url: mapFixture.license_url,
  }) : purchaseHandler(url))
  expect(await screen.findByText(/Chưa có bản đồ nền OSM có nhãn/)).toBeVisible()
  expect(screen.queryByRole('application', { name: 'Bản đồ chọn ghim giao hàng' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Dán tọa độ (vĩ độ, kinh độ)')).toBeEnabled()
})
