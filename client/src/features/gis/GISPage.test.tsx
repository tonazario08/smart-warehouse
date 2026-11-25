import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { RouteGuard } from '../../app/RouteGuard'
import { GISPage } from './GISPage'
import * as api from './api'
import type { Heatmap, RouteRead, SnapshotMetadata, StreetLayer, WarehouseOptions } from './types'

const auth = vi.hoisted(() => ({ token: 'fake-session-one' as string | null, role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({
  useAuth: () => ({ token: auth.token, user: auth.token ? { id: 1, role: auth.role } : null }),
}))
vi.mock('./publicLandmarks', () => ({
  publicLandmarks: [
    { id: 'mock-place', name: 'Địa danh thử', aliases: ['Tên thường gọi'], latitude: 10.77, longitude: 106.7,
      sourceUrl: 'https://example.invalid/mock', sourceLabel: 'Nguồn mô phỏng chỉ dùng khi kiểm thử' },
    { id: 'mock-outside', name: 'Địa danh ngoài vùng', aliases: [], latitude: 40, longitude: 100,
      sourceUrl: 'https://example.invalid/mock', sourceLabel: 'Nguồn mô phỏng chỉ dùng khi kiểm thử' },
  ],
}))
vi.mock('./api', async importOriginal => ({
  ...await importOriginal<typeof import('./api')>(),
  getGisStatus: vi.fn(),
  getGisStreetLayer: vi.fn(),
  getGisChoices: vi.fn(),
  getWarehouseOptions: vi.fn(),
  getGisRoute: vi.fn(),
  getGisHeatmap: vi.fn(),
  getGisPolicy: vi.fn(),
}))

const warehouse = { warehouse_id: 5, code: 'M10-A', name: 'Kho M10', latitude: 10.75, longitude: 106.65 }
const product = { product_id: 3, sku: 'M10-SKU', name: 'Sản phẩm M10', unit: 'hộp' }
const fixture = { stock_data_class: 'synthetic_fixture', stock_fixture_label: 'Kho và tồn kiểm thử' } as const
const snapshot: SnapshotMetadata = {
  snapshot_id: 'gsv1-' + 'a'.repeat(64), dataset_class: 'public_osm',
  source_url: 'https://download.geofabrik.de/asia/vietnam-261105.osm.pbf',
  snapshot_at: '2026-11-05T21:23:02Z', bounds: [106.64, 10.72, 106.76, 10.82],
  crs: 'EPSG:4326', weight_unit: 'mm', license: 'ODbL 1.0',
  attribution: '© OpenStreetMap contributors', license_url: 'https://www.openstreetmap.org/copyright',
}
const publicLayer: StreetLayer = {
  state: 'available', snapshot_id: snapshot.snapshot_id, bounds: snapshot.bounds,
  segments: [[[106.65, 10.75], [106.66, 10.76]]],
  attribution: snapshot.attribution, license_url: snapshot.license_url,
}
const coordinate = { latitude: 10.76, longitude: 106.66 }
const destination = { kind: 'coordinate', coordinate, warehouse: null, request_id: null } as const
const origin = { kind: 'warehouse', coordinate: { latitude: 10.75, longitude: 106.65 }, warehouse, request_id: null } as const
const options: WarehouseOptions = {
  ...fixture, stock_as_of: '2026-11-07T00:00:00Z', product, quantity: 2,
  snapshot_state: 'available', snapshot, ranking_state: 'available', destination,
  ranked: [{ warehouse, available_quantity: 2, distance_mm: 1547215, snapshot_id: snapshot.snapshot_id }],
  geographic_only: [], excluded: [],
}
const route: RouteRead = {
  ...fixture, snapshot_state: 'available', snapshot, origin, destination,
  geometry: { type: 'LineString', coordinates: [[106.65, 10.75], [106.66, 10.76]] },
  origin_snap: null, destination_snap: null, reason: null, distance_mm: 1547215, transfer: null,
}
const zero = { quantity: 0, transaction_count: 0 }
const heatmap: Heatmap = {
  ...fixture, product, start_date: '2026-11-02', end_date: '2026-11-03',
  start_utc: '2026-11-01T17:00:00Z', end_utc: '2026-11-02T17:00:00Z',
  timezone: 'Asia/Ho_Chi_Minh', queried_at: '2026-11-07T00:00:00Z',
  points: [{ warehouse, fulfilled_quantity: 9, transaction_count: 1 }],
  unlocated: [{ warehouse: { ...warehouse, warehouse_id: 6, name: 'Kho chưa có điểm', latitude: null, longitude: null }, fulfilled_quantity: 0, transaction_count: 0 }],
  excluded: { transfer_in: zero, transfer_out: { quantity: 2, transaction_count: 1 }, standard_outbound: zero, unclassified_outbound: zero },
}

beforeEach(() => {
  auth.token = 'fake-session-one'
  auth.role = 'admin'
  vi.resetAllMocks()
  vi.mocked(api.getGisStatus).mockResolvedValue({ ...fixture, state: 'available', snapshot })
  vi.mocked(api.getGisStreetLayer).mockResolvedValue({ state: 'unavailable', snapshot_id: null, bounds: null, segments: [], attribution: null, license_url: null })
  vi.mocked(api.getGisChoices).mockResolvedValue({
    products: [{ ...product, id: product.product_id, is_active: true, category_id: 1, description: null, supplier_id: null, reorder_level: 0 }],
    warehouses: [{ ...warehouse, id: warehouse.warehouse_id, address: 'Fixture' }],
  })
  vi.mocked(api.getWarehouseOptions).mockResolvedValue(options)
  vi.mocked(api.getGisRoute).mockResolvedValue(route)
  vi.mocked(api.getGisHeatmap).mockResolvedValue(heatmap)
})

function page() {
  return <MemoryRouter><GISPage /></MemoryRouter>
}

async function fillProduct() {
  await screen.findByRole('option', { name: 'M10-SKU · Sản phẩm M10' })
  await userEvent.selectOptions(screen.getByLabelText('Sản phẩm (SKU)'), '3')
}

async function fillCoordinates() {
  await fillProduct()
  await userEvent.clear(screen.getByLabelText('Số lượng cần'))
  await userEvent.type(screen.getByLabelText('Số lượng cần'), '2')
  await userEvent.click(screen.getByText('Nhập tọa độ thủ công'))
  await userEvent.type(screen.getByLabelText('Vĩ độ'), '10.76')
  await userEvent.type(screen.getByLabelText('Kinh độ'), '106.66')
}

it('redirects the client role through the existing direct route guard without loading GIS', async () => {
  auth.role = 'client'
  render(<MemoryRouter initialEntries={['/gis']}><Routes>
    <Route element={<RouteGuard permission="gis:read" />}>
      <Route path="/gis" element={<GISPage />} />
    </Route>
    <Route path="/products" element={<p>Sản phẩm được phép</p>} />
  </Routes></MemoryRouter>)
  expect(await screen.findByText('Sản phẩm được phép')).toBeInTheDocument()
  expect(api.getGisStatus).not.toHaveBeenCalled()
})

it('loads options from explicit coordinates and shows the selected route by keyboard', async () => {
  render(page())
  expect(screen.getByRole('heading', { name: 'Bản đồ kho' })).toBeInTheDocument()
  expect(await screen.findByText('Kho và tồn kiểm thử')).toBeInTheDocument()
  expect(screen.getByText(/Đường công cộng OpenStreetMap ·/)).toBeInTheDocument()
  expect(screen.getByText('106.64, 10.72 đến 106.76, 10.82')).toBeInTheDocument()
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][1]).toEqual({
    product_id: 3, quantity: 2, destination: { kind: 'coordinate', ...coordinate },
  })
  const show = await screen.findByRole('button', { name: 'Xem tuyến từ Kho M10' })
  show.focus()
  await userEvent.keyboard('{Enter}')
  expect(await screen.findByRole('img', { name: 'Sơ đồ tuyến đường' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: snapshot.attribution })).toHaveAttribute('href', snapshot.license_url)
  const routeDetails = screen.getByRole('region', { name: 'Tuyến đường' })
  expect(within(routeDetails).getByText('1,547 km')).toBeInTheDocument()
  expect(within(routeDetails).getByText('Tuyến ô tô tham khảo')).toBeInTheDocument()
  expect(within(routeDetails).getByText('Nét liền là đường đi')).toBeInTheDocument()
  const mapsLink = within(routeDetails).getByRole<HTMLAnchorElement>('link', { name: 'Mở chỉ đường trong Google Maps' })
  screen.getByRole('link', { name: snapshot.attribution }).focus()
  await userEvent.tab()
  expect(mapsLink).toHaveFocus()
  const url = new URL(mapsLink.href)
  expect(url.origin + url.pathname).toBe('https://www.google.com/maps/dir/')
  expect(Object.fromEntries(url.searchParams)).toEqual({
    api: '1', origin: '10.75,106.65', destination: '10.76,106.66', travelmode: 'driving', dir_action: 'navigate',
  })
  expect(mapsLink).toHaveAttribute('referrerpolicy', 'no-referrer')
})

it('sends selected warehouses and authorized purchase IDs as distinct destinations', async () => {
  render(page())
  await fillProduct()
  await userEvent.selectOptions(screen.getByLabelText('Loại điểm đến'), 'warehouse')
  await userEvent.selectOptions(screen.getByLabelText('Kho đích'), '5')
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][1].destination).toEqual({
    kind: 'warehouse', warehouse_id: 5,
  })
  await userEvent.selectOptions(screen.getByLabelText('Loại điểm đến'), 'purchase_request')
  await userEvent.type(screen.getByLabelText('ID yêu cầu mua hàng'), '12')
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[1][1].destination).toEqual({
    kind: 'purchase_request', request_id: 12,
  })
})

it('distinguishes a geographic fallback from a route and displays unavailable snapshot reasons', async () => {
  vi.mocked(api.getGisStatus).mockResolvedValue({ ...fixture, state: 'invalid', snapshot: null })
  vi.mocked(api.getWarehouseOptions).mockResolvedValue({
    ...options, snapshot_state: 'invalid', snapshot: null, ranking_state: 'unavailable',
    ranked: [],
    geographic_only: [{ warehouse, available_quantity: 2, distance_mm: 120000, reason: 'snapshot_invalid' }],
  })
  render(page())
  expect(await screen.findByText('Bản chụp đường không hợp lệ.')).toBeInTheDocument()
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(await screen.findByRole('heading', { name: 'Khoảng cách địa lý' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Xem tuyến từ/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('img', { name: 'Sơ đồ tuyến đường' })).not.toBeInTheDocument()
})

it('ignores a late warehouse response when a filter changes', async () => {
  let finish!: (value: WarehouseOptions) => void
  vi.mocked(api.getWarehouseOptions).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(screen.getByText('Đang tìm kho đủ tồn…')).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('Số lượng cần'), '1')
  await act(async () => finish(options))
  expect(screen.queryByRole('button', { name: 'Xem tuyến từ Kho M10' })).not.toBeInTheDocument()
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][2].aborted).toBe(true)
})

it('ignores an in-flight result after a session changes', async () => {
  let finish!: (value: WarehouseOptions) => void
  vi.mocked(api.getWarehouseOptions).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  const view = render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  auth.token = 'fake-session-two'
  view.rerender(page())
  await act(async () => finish(options))
  expect(screen.queryByRole('button', { name: 'Xem tuyến từ Kho M10' })).not.toBeInTheDocument()
})

it('shows request errors and retries, but does not retry a forbidden status', async () => {
  vi.mocked(api.getGisStatus)
    .mockRejectedValueOnce(new Error('network failure'))
    .mockRejectedValueOnce(new ApiError('Bạn không có quyền thực hiện thao tác này.', 403))
  render(page())
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại dữ liệu đường' }))
  expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Thử lại dữ liệu đường' })).not.toBeInTheDocument()
})

it('shows transfer context and a no-route reason without drawing a line', async () => {
  vi.mocked(api.getGisRoute).mockResolvedValue({
    ...route, geometry: null, distance_mm: null, reason: 'no_route',
    transfer: { transfer_id: 9, mode: 'immediate' },
  })
  render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Tra phiếu chuyển kho' }))
  await userEvent.type(screen.getByLabelText('ID phiếu chuyển kho'), '9')
  await userEvent.click(screen.getByRole('button', { name: 'Xem tuyến chuyển kho' }))
  expect(vi.mocked(api.getGisRoute).mock.calls[0][1]).toEqual({ kind: 'transfer', transfer_id: 9 })
  expect(await screen.findByText(/Chuyển kho tức thời/)).toBeInTheDocument()
  expect(screen.getByText('Không tìm thấy đường đi trong mạng đường đã chọn.')).toBeInTheDocument()
})

it.each(['origin', 'destination'] as const)('omits the Google Maps link when the %s coordinate is missing', async endpoint => {
  vi.mocked(api.getGisRoute).mockResolvedValue({
    ...route, [endpoint]: { ...route[endpoint], coordinate: null },
    geometry: null, distance_mm: null, reason: 'no_route', transfer: { transfer_id: 9, mode: 'immediate' },
  })
  render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Tra phiếu chuyển kho' }))
  await userEvent.type(screen.getByLabelText('ID phiếu chuyển kho'), '9')
  await userEvent.click(screen.getByRole('button', { name: 'Xem tuyến chuyển kho' }))
  expect(await screen.findByText(/Chuyển kho tức thời/)).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Mở chỉ đường trong Google Maps' })).not.toBeInTheDocument()
})

it('keeps heatmap totals, units, missing coordinates and exclusions available in a keyboard table', async () => {
  render(page())
  await fillProduct()
  await userEvent.click(screen.getByRole('button', { name: 'Xem lượng xuất' }))
  const table = await screen.findByRole('table', { name: 'Lượng xuất theo kho' })
  expect(within(table).getByText('9 hộp')).toBeInTheDocument()
  expect(within(table).getByText('Kho chưa có điểm', { exact: false })).toBeInTheDocument()
  expect(within(table).getByText('Chưa có vị trí')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cuộn bảng lượng xuất theo kho' })).toHaveAttribute('tabindex', '0')
  expect(screen.getByRole('img', { name: 'Bản đồ lượng xuất theo kho' })).toBeInTheDocument()
  expect(screen.getByText('Asia/Ho_Chi_Minh', { exact: false })).toBeInTheDocument()
  expect(screen.getByText('Chân xuất chuyển kho', { exact: false })).toBeInTheDocument()
})



it('shows verified policy provenance for the selected SKU and warehouse', async () => {
  const runId = 'rrv1-' + 'a'.repeat(64)
  vi.mocked(api.getGisPolicy).mockResolvedValue({
    state: 'applicable',
    run: {
      run_id: runId, data_version: 'ddv1-fixture', created_at: '2026-11-05T12:00:00Z',
      fixture_label: 'Kịch bản kiểm thử', href: '/replenishment/runs/' + runId,
    },
  })
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Xem tuyến từ Kho M10' }))
  await userEvent.click(screen.getByText('Tham khảo bổ sung hàng'))
  await userEvent.type(screen.getByLabelText('Mã kết quả bổ sung hàng'), runId)
  await userEvent.click(screen.getByRole('button', { name: 'Kiểm tra phạm vi áp dụng' }))
  expect(vi.mocked(api.getGisPolicy).mock.calls[0][1]).toEqual({
    product_id: 3, warehouse_id: 5, run_id: runId,
  })
  expect(await screen.findByText('Kịch bản kiểm thử')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Xem kết quả bổ sung hàng' }))
    .toHaveAttribute('href', '/replenishment/runs/' + runId)
})

it('keeps filters disabled during catalogue loading and explains an empty catalogue', async () => {
  let finish!: (data: Awaited<ReturnType<typeof api.getGisChoices>>) => void
  vi.mocked(api.getGisChoices).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  render(page())
  expect(screen.getByText('Đang tải sản phẩm và kho…')).toBeInTheDocument()
  expect(screen.getByLabelText('Sản phẩm (SKU)')).toBeDisabled()
  await act(async () => finish({ products: [], warehouses: [] }))
  expect(screen.getByText('Chưa có sản phẩm đang hoạt động.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tìm kho đủ tồn' })).toBeDisabled()
})

function pointAt(map: HTMLElement, x: number, y: number) {
  vi.spyOn(map, 'getBoundingClientRect').mockReturnValue({
    x: 16, y: 20, left: 16, top: 20, right: 336, bottom: 340, width: 320, height: 320, toJSON: () => ({}),
  })
  fireEvent.click(map, { clientX: 16 + x, clientY: 20 + y })
}

it('picks an in-bounds destination without sending it and overlays only a matching public route', async () => {
  vi.mocked(api.getGisStreetLayer).mockResolvedValue(publicLayer)
  render(page())
  await fillProduct()
  const picker = await screen.findByRole('img', { name: 'Chọn điểm đến trên nền đường OpenStreetMap' })
  expect(picker.querySelector('.gis-map__streets')).toBeInTheDocument()
  const pickerFigure = picker.closest('figure')!
  expect(within(pickerFigure).getByRole('link', { name: snapshot.attribution })).toHaveAttribute('href', snapshot.license_url)

  pointAt(picker, 160, 60)
  expect(screen.getByLabelText('Vĩ độ')).toHaveValue(null)
  pointAt(picker, 160, 160)
  expect(screen.getByLabelText('Vĩ độ')).toHaveValue(10.77)
  expect(screen.getByLabelText('Kinh độ')).toHaveValue(106.7)
  expect(picker.querySelector('.gis-map__destination')).toBeInTheDocument()
  expect(api.getWarehouseOptions).not.toHaveBeenCalled()
  expect(api.getGisRoute).not.toHaveBeenCalled()

  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][1].destination).toEqual({ kind: 'coordinate', latitude: 10.77, longitude: 106.7 })
  await userEvent.click(await screen.findByRole('button', { name: 'Xem tuyến từ Kho M10' }))
  const result = await screen.findByRole('img', { name: 'Tuyến trên nền đường OpenStreetMap' })
  expect(result.querySelector('.gis-map__streets')).toBeInTheDocument()
  expect(result.querySelector('.gis-map__road')).toBeInTheDocument()

  await userEvent.click(screen.getByText('Nhập tọa độ thủ công'))
  const latitudeField = screen.getByLabelText('Vĩ độ')
  latitudeField.focus()
  await userEvent.keyboard('{Control>}a{/Control}55')
  expect(latitudeField).toHaveValue(55)
  expect(screen.queryByRole('img', { name: 'Tuyến trên nền đường OpenStreetMap' })).not.toBeInTheDocument()
  expect(picker.querySelector('.gis-map__destination')).not.toBeInTheDocument()
  expect(screen.getByText(/Điểm nhập nằm ngoài vùng hiển thị/)).toBeInTheDocument()
})

it('drops an old route response after changing the destination on the map', async () => {
  let finish!: (route: RouteRead) => void
  vi.mocked(api.getGisRoute).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Xem tuyến từ Kho M10' }))
  const picker = screen.getByRole('img', { name: 'Chọn điểm đến trên sơ đồ tọa độ' })
  pointAt(picker, 160, 160)
  expect(vi.mocked(api.getGisRoute).mock.calls[0][2].aborted).toBe(true)
  await act(async () => finish(route))
  expect(screen.queryByRole('img', { name: 'Sơ đồ tuyến đường' })).not.toBeInTheDocument()
  expect(api.getWarehouseOptions).toHaveBeenCalledTimes(1)
})

it('never paints the public backdrop if IDs mismatch or the snapshot is synthetic', async () => {
  vi.mocked(api.getGisStreetLayer).mockResolvedValue({ ...publicLayer, snapshot_id: 'not-current' })
  const view = render(page())
  const picker = await screen.findByRole('img', { name: 'Chọn điểm đến trên sơ đồ tọa độ' })
  expect(picker.querySelector('.gis-map__streets')).not.toBeInTheDocument()
  expect(screen.getByText('Sơ đồ tọa độ, không có nền đường phố.')).toBeInTheDocument()
  view.unmount()
  vi.mocked(api.getGisStreetLayer).mockClear()
  vi.mocked(api.getGisStatus).mockResolvedValue({
    ...fixture, state: 'available', snapshot: { ...snapshot, dataset_class: 'synthetic_fixture' },
  })
  render(page())
  expect(await screen.findByText('Sơ đồ tọa độ mô phỏng, không có nền đường phố.')).toBeInTheDocument()
  expect(api.getGisStreetLayer).not.toHaveBeenCalled()
})

it('keeps manual coordinate controls when status is stale without loading a public layer', async () => {
  vi.mocked(api.getGisStatus).mockResolvedValue({ ...fixture, state: 'stale', snapshot })
  render(page())
  expect(await screen.findByText('Bản chụp đường đã quá hạn.')).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: /Chọn điểm đến trên/ })).not.toBeInTheDocument()
  expect(api.getGisStreetLayer).not.toHaveBeenCalled()
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(api.getWarehouseOptions).toHaveBeenCalled()
})

it('shows a map legend and clears the selected destination without a request', async () => {
  render(page())
  await fillCoordinates()
  expect(screen.getByRole('list', { name: 'Chú giải bản đồ kho' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Xóa điểm đến' }))
  expect(screen.getByLabelText('Vĩ độ')).toHaveValue(null)
  expect(screen.getByLabelText('Kinh độ')).toHaveValue(null)
  expect(api.getWarehouseOptions).not.toHaveBeenCalled()
})

it('uses real stock buckets and links each approved ranked warehouse to the same resolved destination', async () => {
  const other = { ...warehouse, warehouse_id: 9, name: 'Kho khác', longitude: 106.68 }
  const straight = { ...warehouse, warehouse_id: 10, name: 'Kho không nối đường', longitude: 106.69 }
  const shortage = { ...warehouse, warehouse_id: 11, name: 'Kho thiếu', longitude: 106.7 }
  const unknown = { ...warehouse, warehouse_id: 12, name: 'Kho chưa biết', longitude: 106.71 }
  const unlocated = { ...warehouse, warehouse_id: 13, name: 'Kho không tọa độ', longitude: null }
  vi.mocked(api.getWarehouseOptions).mockResolvedValue({
    ...options,
    ranked: [...options.ranked, { ...options.ranked[0], warehouse: other }, { ...options.ranked[0], warehouse: unlocated }],
    geographic_only: [{ warehouse: straight, available_quantity: 6, reason: 'no_route', distance_mm: 1230000 }],
    excluded: [
      { warehouse: shortage, available_quantity: 1, reason: 'insufficient_stock' },
      { warehouse: unknown, available_quantity: null, reason: 'missing_stock' },
    ],
  })
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  const map = screen.getByRole('img', { name: 'Chọn điểm đến trên sơ đồ tọa độ' })
  const links = await screen.findAllByRole('link', { name: /^Google Maps từ/ })
  expect(links).toHaveLength(2)
  const urls = links.map(link => new URL(link.getAttribute('href')!))
  expect(urls.map(url => url.searchParams.get('origin'))).toEqual(['10.75,106.65', '10.75,106.68'])
  expect(urls.map(url => url.searchParams.get('destination'))).toEqual(['10.76,106.66', '10.76,106.66'])
  expect(links.every(link => link.getAttribute('referrerpolicy') === 'no-referrer')).toBe(true)
  expect(api.getGisRoute).not.toHaveBeenCalled()
  expect(map.querySelectorAll('.gis-map__stock-enough')).toHaveLength(3)
  expect(map.querySelectorAll('.gis-map__stock-short')).toHaveLength(1)
  expect(map.querySelector('.gis-map__stock-short title')).toHaveTextContent('Kho thiếu')
  expect(map).not.toHaveTextContent('Kho chưa biết')
  expect(map).not.toHaveTextContent('Kho không tọa độ')
  expect(screen.getByRole('region', { name: 'Khoảng cách địa lý' })).toHaveTextContent('Đủ tồn')
})

it('reframes the selected server route without new network calls or moving the destination', async () => {
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Xem tuyến từ Kho M10' }))
  const map = screen.getByRole('img', { name: 'Chọn điểm đến trên sơ đồ tọa độ' })
  const original = map.querySelector('.gis-map__road')?.getAttribute('points')
  expect(original).toBeTruthy()
  await userEvent.click(await screen.findByRole('button', { name: 'Xem gần tuyến' }))
  expect(map).toHaveAttribute('data-map-frame', 'route')
  expect(map.querySelector('.gis-map__road')).not.toHaveAttribute('points', original)
  await userEvent.click(screen.getByRole('button', { name: 'Về khung vùng' }))
  expect(map).toHaveAttribute('data-map-frame', 'coverage')
  expect(map.querySelector('.gis-map__road')).toHaveAttribute('points', original)
  expect(screen.getByLabelText('Vĩ độ')).toHaveValue(10.76)
  expect(api.getWarehouseOptions).toHaveBeenCalledTimes(1)
  expect(api.getGisRoute).toHaveBeenCalledTimes(1)
})

it('clears a pending lookup and discards a late successful response', async () => {
  let finish!: (options: WarehouseOptions) => void
  vi.mocked(api.getWarehouseOptions).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  render(page())
  await fillCoordinates()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  await userEvent.click(screen.getByRole('button', { name: 'Xóa điểm đến' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][2].aborted).toBe(true)
  await act(async () => finish(options))
  expect(screen.getByLabelText('Kinh độ')).toHaveValue(null)
  expect(screen.queryByRole('button', { name: 'Xem tuyến từ Kho M10' })).not.toBeInTheDocument()
})

it('keeps long snapshot metadata in a collapsed disclosure', async () => {
  render(page())
  expect(await screen.findByText(/Đường công cộng OpenStreetMap · 2026-11-05 UTC/)).toBeVisible()
  expect(screen.getByText(snapshot.snapshot_id)).not.toBeVisible()
  await userEvent.click(screen.getByText('Chi tiết bản chụp đường'))
  expect(screen.getByText(snapshot.snapshot_id)).toBeVisible()
})

it('does not offer Google Maps or draw an invented path when transfer has no server route', async () => {
  vi.mocked(api.getGisRoute).mockResolvedValue({
    ...route, reason: 'no_route', geometry: null, distance_mm: null, transfer: { transfer_id: 7, mode: 'immediate' },
  })
  render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Tra phiếu chuyển kho' }))
  await userEvent.type(screen.getByLabelText('ID phiếu chuyển kho'), '7')
  await userEvent.click(screen.getByRole('button', { name: 'Xem tuyến chuyển kho' }))
  const map = await screen.findByRole('img', { name: 'Sơ đồ tuyến đường' })
  expect(map.querySelector('.gis-map__road')).toBeNull()
  expect(screen.queryByRole('link', { name: /Google Maps/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Xóa điểm đến' })).not.toBeInTheDocument()
})

it('keeps manual coordinates behind a separate initially-collapsed control', async () => {
  render(page())
  const manual = await screen.findByText('Nhập tọa độ thủ công')
  expect(manual.parentElement).not.toHaveAttribute('open')
  await userEvent.click(manual)
  expect(screen.getByLabelText('Vĩ độ')).toBeVisible()
})

async function findMockLandmark() {
  const search = await screen.findByRole('searchbox', { name: 'Tìm địa danh' })
  await userEvent.type(search, 'ten thuong goi')
  expect(screen.queryByRole('button', { name: 'Địa danh ngoài vùng' })).not.toBeInTheDocument()
  await userEvent.keyboard('{Enter}{Tab}')
  const suggestion = screen.getByRole('button', { name: 'Địa danh thử' })
  expect(suggestion).toHaveFocus()
  await userEvent.keyboard('{Enter}')
  return search
}

it('selects an accent-insensitive alias by keyboard without contacting warehouse lookup until explicitly submitted', async () => {
  vi.mocked(api.getGisStreetLayer).mockResolvedValue(publicLayer)
  render(page())
  await fillProduct()
  const search = await findMockLandmark()
  expect(search).toHaveValue('Địa danh thử')
  expect(screen.getByText('Điểm đến: Địa danh thử')).toBeVisible()
  const map = screen.getByRole('img', { name: 'Chọn điểm đến trên nền đường OpenStreetMap' })
  expect(map.querySelector('.gis-map-target-label')).toHaveTextContent('Địa danh thử')
  expect(map.querySelector('.gis-map-warehouse-label title')).toHaveTextContent('M10-A · Kho M10')
  expect(api.getWarehouseOptions).not.toHaveBeenCalled()
  expect(api.getGisRoute).not.toHaveBeenCalled()

  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][1].destination)
    .toEqual({ kind: 'coordinate', latitude: 10.77, longitude: 106.7 })
})

it('drops a pending named lookup on map placement, and manual edits and clear do not retain its name', async () => {
  vi.mocked(api.getGisStreetLayer).mockResolvedValue(publicLayer)
  let finish!: (options: WarehouseOptions) => void
  vi.mocked(api.getWarehouseOptions).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  render(page())
  await fillProduct()
  const search = await findMockLandmark()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  const map = screen.getByRole('img', { name: 'Chọn điểm đến trên nền đường OpenStreetMap' })
  pointAt(map, 125, 140)
  expect(vi.mocked(api.getWarehouseOptions).mock.calls[0][2].aborted).toBe(true)
  expect(search).toHaveValue('')
  expect(map.querySelector('.gis-map-target-label')).toBeNull()
  await act(async () => finish(options))
  expect(screen.queryByRole('button', { name: 'Xem tuyến từ Kho M10' })).not.toBeInTheDocument()
  await findMockLandmark()
  await userEvent.click(screen.getByText('Nhập tọa độ thủ công'))
  await userEvent.clear(screen.getByLabelText('Vĩ độ'))
  await userEvent.type(screen.getByLabelText('Vĩ độ'), '10.75')
  expect(screen.queryByText('Điểm đến: Địa danh thử')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Xóa điểm đến' }))
  expect(map.querySelector('.gis-map__destination')).toBeNull()
})

it('does not turn an unmatched text search into a destination, even if a previous point existed', async () => {
  vi.mocked(api.getGisStreetLayer).mockResolvedValue(publicLayer)
  render(page())
  await fillProduct()
  const search = await findMockLandmark()
  await userEvent.clear(search)
  await userEvent.type(search, 'không tồn tại')
  expect(screen.getByText(/Không tìm thấy địa danh/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Tìm kho đủ tồn' }))
  expect(api.getWarehouseOptions).not.toHaveBeenCalled()
  expect(screen.getByRole('img', { name: 'Chọn điểm đến trên nền đường OpenStreetMap' }).querySelector('.gis-map__destination')).toBeNull()
})

it('routes a private B2B delivery by request ID only and never builds a Google Maps link', async () => {
  vi.mocked(api.getGisRoute).mockResolvedValue({
    ...route,
    destination: { kind: 'purchase_request_delivery', coordinate, warehouse: null, request_id: 42 },
  })
  render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Địa chỉ giao của đơn B2B' }))
  await userEvent.type(screen.getByLabelText('ID đơn B2B'), '42')
  expect(api.getGisRoute).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Xem tuyến giao B2B' }))
  expect(vi.mocked(api.getGisRoute).mock.calls[0][1]).toEqual({ kind: 'purchase_request_delivery', request_id: 42 })
  expect(await screen.findByText(/Tuyến nội bộ từ kho được gán trên đơn/)).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Google Maps/ })).not.toBeInTheDocument()
  expect(api.getWarehouseOptions).not.toHaveBeenCalled()
})

it('does not put a Google link into a delivery view even for an unexpected legacy route result', async () => {
  render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Địa chỉ giao của đơn B2B' }))
  await userEvent.type(screen.getByLabelText('ID đơn B2B'), '42')
  await userEvent.click(screen.getByRole('button', { name: 'Xem tuyến giao B2B' }))
  expect(await screen.findByText('Không xác minh được tuyến cho điểm giao của đơn B2B này.')).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: 'Sơ đồ tuyến đường' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Google Maps/ })).not.toBeInTheDocument()
})
