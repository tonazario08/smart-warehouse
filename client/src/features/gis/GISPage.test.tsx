import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { RouteGuard } from '../../app/RouteGuard'
import { GISPage } from './GISPage'
import * as api from './api'
import type { Heatmap, RouteRead, SnapshotMetadata, WarehouseOptions } from './types'

const auth = vi.hoisted(() => ({ token: 'fake-session-one' as string | null, role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({
  useAuth: () => ({ token: auth.token, user: auth.token ? { id: 1, role: auth.role } : null }),
}))
vi.mock('./api', async importOriginal => ({
  ...await importOriginal<typeof import('./api')>(),
  getGisStatus: vi.fn(),
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
  expect(screen.getByText('Đường công cộng OpenStreetMap')).toBeInTheDocument()
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
