import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { ReplenishmentRunPage } from './ReplenishmentRunPage'
import * as api from './api'

vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: 'admin' } }) }))
vi.mock('./api', () => ({ getReplenishmentRun: vi.fn(), getReplenishmentDays: vi.fn(), getReplenishmentAlertSources: vi.fn(), replenishmentError: () => 'Không thể tải dữ liệu.' }))
it('rejects invalid IDs before requests', async () => {
  render(<MemoryRouter initialEntries={['/replenishment/runs/invalid']}><Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã kết quả bổ sung hàng không hợp lệ')
  expect(api.getReplenishmentRun).not.toHaveBeenCalled()
})

it('keeps filter focus and metadata while loading a new trace without refetching detail', async () => {
  const id = 'rrv1-' + 'a'.repeat(64)
  vi.mocked(api.getReplenishmentRun).mockResolvedValue({
    manifest: { run_id: id, mode: 'research', dataset_class: 'research', data_version: 'ddv2-test', forecast_run_id: 'frv1-test', target: 'reported_daily_unit_sales', reporting_scope: 'company_aggregate', unit: 'unit', created_at: '2026-10-30T00:00:00Z', admission_cutoff: '2026-10-26T16:41:38Z', knowledge_bound: '2026-10-26T16:41:38Z', training_information_cutoff: '2026-10-26T16:41:38Z', source_business_timezone: null, scenario_clock_timezone: 'UTC', scenario_clock_convention: 'ANALYTICAL_SCENARIO_CLOCK_UTC', config: { calibration_start: '2022-01-01', calibration_end: '2022-07-01', evaluation_start: '2022-07-01', evaluation_end: '2023-01-01', warmup_days: 7, initial_on_hand: 10000, initial_pipeline: [], reservations: 0, backlog: 0, costs: { currency: 'VND', holding_period: 'year', ordering_cost: '100000', holding_cost: '20000' } } },
    calibration: { calibration: { annual_demand: '730', annual_demand_dates: [], entries: [] }, eoq: { quantity: 0, raw: '0', reason_code: 'ZERO_DEMAND' }, interval_metrics: [] },
    summaries: [], applicability: 'research_scenario', fixture_label: null, stale: null, reason_codes: [], entity: null,
  })
  vi.mocked(api.getReplenishmentDays).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  render(<MemoryRouter initialEntries={['/replenishment/runs/' + id]}><Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes></MemoryRouter>)
  const control = await screen.findByLabelText('Thời gian cung ứng')
  control.focus()
  await userEvent.selectOptions(control, '7')
  expect(control).toHaveFocus()
  expect(screen.getByText('2022-01-01 đến trước 2022-07-01')).toBeInTheDocument()
  expect(screen.getByText('2022-07-01 đến trước 2023-01-01')).toBeInTheDocument()
  expect(screen.getByText('Đơn vị bán được báo cáo')).toBeInTheDocument()
  expect(screen.getByText('Tổng hợp toàn công ty')).toBeInTheDocument()
  expect(screen.getByText('Không có')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cuộn bảng so sánh chính sách' })).toHaveAttribute('tabindex', '0')
  expect(api.getReplenishmentRun).toHaveBeenCalledOnce()
  expect(api.getReplenishmentDays).toHaveBeenLastCalledWith('token', id, 'persistence', 7, '0.90', 'proposed', 1)
})

it('distinguishes zero from undefined rates and pages the trace', async () => {
  const id = 'rrv1-' + 'b'.repeat(64)
  const summary = { scored_days: 171, demand: 0, fulfilled: 0, lost: 0, fill_rate: null, fill_reason: 'ZERO_DEMAND', day_service: null, day_service_reason: 'NO_POSITIVE_DEMAND_DAYS', stockout_days: 0, average_on_hand: '0', order_count: 0, receipt_count: 0, ordering_cost: '0', holding_cost: '0', partial_cost: '0.6', terminal_pipeline: 0 }
  vi.mocked(api.getReplenishmentRun).mockResolvedValue({
    manifest: { run_id: id, mode: 'operational', dataset_class: 'fixture', data_version: 'ddv1-fixture', forecast_run_id: 'frv1-test', target: 'gross_fulfilled_units', reporting_scope: 'warehouse', unit: 'unit', created_at: '2026-11-01T00:00:00Z', admission_cutoff: null, knowledge_bound: null, training_information_cutoff: '2021-12-31T00:00:00Z', source_business_timezone: 'UTC', scenario_clock_timezone: 'UTC', scenario_clock_convention: 'OPERATIONAL_BUSINESS_TIMEZONE', config: { calibration_start: '2022-01-01', calibration_end: '2022-07-01', evaluation_start: '2022-07-01', evaluation_end: '2023-01-01', warmup_days: 7, initial_on_hand: 0, initial_pipeline: [], reservations: 0, backlog: 0, costs: { currency: 'VND', holding_period: 'year', ordering_cost: '100', holding_cost: '365' } } },
    calibration: { calibration: { annual_demand: '0', annual_demand_dates: [], entries: [{ algorithm: 'persistence', horizon: 1, windows: [{}], quantiles: { '0.90': '0' } }] }, eoq: { quantity: 0, raw: '0', reason_code: 'ZERO_DEMAND' }, interval_metrics: [{ algorithm: 'persistence', horizon: 1, subset: 'all', count: 1, reason_code: null, coverage: '0', mean_width: '0', mean_interval_score: '0', pinball: {} }] },
    summaries: [{ case: { algorithm: 'persistence', horizon: 1, service: '0.90', policy: 'proposed' }, initial_on_hand: 0, rop_min: 0, rop_max: 0, summary }],
    applicability: 'fixture_scenario', fixture_label: 'Dữ liệu kiểm thử', stale: null, reason_codes: [], entity: null,
  })
  vi.mocked(api.getReplenishmentDays).mockResolvedValue({ items: [{ day: '2022-07-01', origin: '2022-06-30', warmup: true, opening_on_hand: 0, received: 0, position: 0, forecast_mean: '0', residual_quantile: '0', safety_stock: '0', reorder_point: 0, order_quantity: 0, ordered: 0, due_date: null, demand: 0, fulfilled: 0, lost: 0, on_hand_end: 0, pipeline_end: 0, ordering_cost: '0', holding_cost: '0' }], total: 21, page: 1, page_size: 20 })
  render(<MemoryRouter initialEntries={['/replenishment/runs/' + id]}><Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('Không xác định: nhu cầu bằng 0')).toBeInTheDocument()
  expect(screen.getByText('0%')).toBeInTheDocument()
  const comparison = screen.getByRole('table', { name: 'So sánh chính sách bổ sung hàng' })
  expect(within(within(comparison).getAllByRole('row')[1]).getAllByRole('cell').at(-1)).toHaveTextContent(/^1$/)
  expect(await screen.findByRole('region', { name: 'Cuộn bảng diễn biến theo ngày' })).toHaveAttribute('tabindex', '0')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(api.getReplenishmentDays).toHaveBeenLastCalledWith('token', id, 'persistence', 1, '0.90', 'proposed', 2)
})

const demoId = 'rrv1-' + 'c'.repeat(64)
const anotherId = 'rrv1-' + 'd'.repeat(64)

function mockDemoRun(productId = 10, warehouseId = 20) {
  vi.mocked(api.getReplenishmentRun).mockResolvedValue({
    manifest: {
      run_id: demoId, mode: 'operational', dataset_class: 'fixture', binding: { product_id: productId, warehouse_id: warehouseId, unit: 'unit' },
      data_version: 'ddv1-demo', forecast_run_id: 'frv1-demo', target: 'gross_fulfilled_units', reporting_scope: 'warehouse', unit: 'unit', created_at: '2026-11-01T00:00:00Z',
      admission_cutoff: null, knowledge_bound: null, training_information_cutoff: null,
      source_business_timezone: 'UTC', scenario_clock_timezone: 'UTC', scenario_clock_convention: 'OPERATIONAL_BUSINESS_TIMEZONE',
      config: { calibration_start: '2022-01-01', calibration_end: '2022-07-01', evaluation_start: '2022-07-01', evaluation_end: '2023-01-01', warmup_days: 0, initial_on_hand: 5, initial_pipeline: [], reservations: 0, backlog: 0, costs: { currency: 'VND', holding_period: 'year', ordering_cost: '100', holding_cost: '365' } },
    },
    calibration: { calibration: { annual_demand: '100', annual_demand_dates: [], entries: [] }, eoq: { state: 'ready', quantity: 10, raw: '9.5', reason_code: null }, interval_metrics: [] },
    summaries: [], applicability: 'fixture_scenario', fixture_label: 'Dữ liệu kiểm thử', stale: null, reason_codes: [],
    entity: { product_id: productId, warehouse_id: warehouseId, sku: 'SKU-DEMO', product_name: 'Demo', warehouse_code: 'WH-DEMO', warehouse_name: 'Warehouse' },
  })
  vi.mocked(api.getReplenishmentAlertSources).mockResolvedValue(demoSources(5))
  vi.mocked(api.getReplenishmentDays).mockImplementation(async (_token, _id, _algorithm, leadTime) => ({
    items: [{ day: leadTime === 1 ? '2026-01-02' : '2026-01-09', origin: '2026-01-01', warmup: false, reorder_point: leadTime === 1 ? 5 : 4,
      opening_on_hand: 5, received: 0, position: 5, forecast_mean: '5', residual_quantile: '0', safety_stock: '0', order_quantity: 10,
      ordered: 0, due_date: null, demand: 0, fulfilled: 0, lost: 0, on_hand_end: 5, pipeline_end: 0, ordering_cost: '0', holding_cost: '0' }],
    total: 1, page: 1, page_size: 20,
  }))
}

function demoSources(quantity: number) {
  return {
    stock: { items: [{ id: 1, product_id: 10, warehouse_id: 20, quantity, created_at: '2026-01-01' }], total: 1, page: 1, page_size: 2 },
    product: { id: 10, sku: 'SKU-DEMO', unit: 'unit' },
    warehouse: { id: 20, code: 'WH-DEMO' },
  } as Awaited<ReturnType<typeof api.getReplenishmentAlertSources>>
}

function renderDemo() {
  render(<MemoryRouter initialEntries={['/replenishment/runs/' + demoId]}>
    <Link to={'/replenishment/runs/' + demoId}>Quay lại bản mô phỏng</Link>
    <Link to={'/replenishment/runs/' + anotherId}>Mở bản mô phỏng khác</Link>
    <Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes>
  </MemoryRouter>)
}

it.each([
  { productId: 10, warehouseId: 20, valid: true },
  { productId: 0, warehouseId: 20, valid: false },
  { productId: -1, warehouseId: 20, valid: false },
  { productId: 10, warehouseId: 0, valid: false },
  { productId: 10, warehouseId: -1, valid: false },
])('handles demo stock lookup for product $productId and warehouse $warehouseId', async ({ productId, warehouseId, valid }) => {
  vi.clearAllMocks()
  mockDemoRun(productId, warehouseId)
  renderDemo()
  if (!valid) {
    expect(await screen.findByText(/Thiếu dữ liệu để đối chiếu/)).toBeInTheDocument()
    expect(screen.queryByText(/Đang kiểm tra tồn kho, danh mục và ROP/)).not.toBeInTheDocument()
    expect(api.getReplenishmentAlertSources).not.toHaveBeenCalled()
    return
  }
  expect(await screen.findByText(/Đề xuất xem xét bổ sung/)).toBeInTheDocument()
  expect(screen.getByText(/Lượng đặt tham khảo theo EOQ/)).toHaveTextContent('10')
  expect(api.getReplenishmentAlertSources).toHaveBeenCalledWith('token', 10, 20)
  vi.mocked(api.getReplenishmentAlertSources).mockResolvedValue(demoSources(20))
  await userEvent.selectOptions(screen.getByLabelText('Thời gian cung ứng'), '7')
  expect(await screen.findByText(/Tồn kho trên ngưỡng ROP tham chiếu/)).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cảnh báo bổ sung hàng demo' })).toHaveTextContent(/tồn: 20/)
  expect(screen.queryByText(/Đề xuất xem xét bổ sung/)).not.toBeInTheDocument()
  expect(screen.getByText(/lead time 7 ngày là giả định/)).toBeInTheDocument()
})

it('reports a missing binding returned by the detail API', async () => {
  vi.clearAllMocks()
  mockDemoRun()
  vi.mocked(api.getReplenishmentRun).mockRejectedValueOnce(new ApiError('Conflict', 409, 'REPLENISHMENT_BINDING_UNAVAILABLE'))
  renderDemo()
  expect(await screen.findByText(/Thiếu dữ liệu để đối chiếu/)).toBeInTheDocument()
  expect(api.getReplenishmentAlertSources).not.toHaveBeenCalled()
})

it('reports denied stock after a case change even while the new trace is pending', async () => {
  vi.clearAllMocks()
  mockDemoRun()
  renderDemo()
  expect(await screen.findByText(/Đề xuất xem xét bổ sung/)).toBeInTheDocument()
  vi.mocked(api.getReplenishmentAlertSources).mockRejectedValueOnce(new ApiError('Forbidden', 403))
  vi.mocked(api.getReplenishmentDays).mockReturnValueOnce(new Promise(() => {}))
  await userEvent.selectOptions(screen.getByLabelText('Thời gian cung ứng'), '7')
  expect(await screen.findByText(/Thiếu dữ liệu để đối chiếu/)).toBeInTheDocument()
  expect(screen.queryByText(/Đề xuất xem xét bổ sung/)).not.toBeInTheDocument()
})

it('does not display the previous advisory while revisiting a run', async () => {
  vi.clearAllMocks()
  mockDemoRun()
  renderDemo()
  expect(await screen.findByText(/Đề xuất xem xét bổ sung/)).toBeInTheDocument()
  vi.mocked(api.getReplenishmentRun).mockReturnValueOnce(new Promise(() => {}))
  await userEvent.click(screen.getByRole('link', { name: 'Mở bản mô phỏng khác' }))
  expect(await screen.findByText('Đang tải chi tiết bổ sung hàng...')).toBeInTheDocument()

  const advisoryAtReload = vi.fn()
  vi.mocked(api.getReplenishmentDays).mockImplementationOnce(() => {
    advisoryAtReload(Boolean(screen.queryByText(/Đề xuất xem xét bổ sung/)))
    return new Promise(() => {})
  })
  await userEvent.click(screen.getByRole('link', { name: 'Quay lại bản mô phỏng' }))
  expect(await screen.findByText(/Đang kiểm tra tồn kho, danh mục và ROP/)).toBeInTheDocument()
  expect(advisoryAtReload).toHaveBeenCalledWith(false)
})
