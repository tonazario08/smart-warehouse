import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { ReplenishmentRunPage } from './ReplenishmentRunPage'
import * as api from './api'
import { getReplenishmentPosition } from '../orderAnalytics/api'
import type { ReplenishmentPosition } from '../orderAnalytics/types'
import type { ForecastPilot, ForecastPilotResult } from './types'

vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: 'admin' } }) }))
vi.mock('../orderAnalytics/api', () => ({ getReplenishmentPosition: vi.fn() }))
vi.mock('./api', () => ({ getReplenishmentRun: vi.fn(), getForecastPilot: vi.fn(async () => ({ state: 'unavailable', reason_code: null, pilot: null })), getReplenishmentDays: vi.fn(), getReplenishmentAlertSources: vi.fn(), replenishmentError: () => 'Không thể tải dữ liệu.' }))
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
    summaries: [
      { case: { algorithm: 'persistence', horizon: 1, service: '0.90', policy: 'proposed' }, initial_on_hand: 0, rop_min: 0, rop_max: 0, summary },
      { case: { algorithm: 'persistence', horizon: 1, service: '0.80', policy: 'proposed' }, initial_on_hand: 0, rop_min: 2.001, rop_max: 2.002, summary },
    ],
    applicability: 'fixture_scenario', fixture_label: 'Dữ liệu kiểm thử', stale: null, reason_codes: [], entity: null,
  })
  vi.mocked(api.getReplenishmentDays).mockResolvedValue({ items: [{ day: '2022-07-01', origin: '2022-06-30', warmup: true, opening_on_hand: 0, received: 0, position: 0, forecast_mean: '0', residual_quantile: '0', safety_stock: '0', reorder_point: 0, order_quantity: 0, ordered: 0, due_date: null, demand: 0, fulfilled: 0, lost: 0, on_hand_end: 0, pipeline_end: 0, ordering_cost: '0', holding_cost: '0' }], total: 21, page: 1, page_size: 20 })
  render(<MemoryRouter initialEntries={['/replenishment/runs/' + id]}><Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes></MemoryRouter>)
  expect((await screen.findAllByText('Không xác định: nhu cầu bằng 0'))[0]).toBeInTheDocument()
  expect(screen.getByText('0%')).toBeInTheDocument()
  const comparison = screen.getByRole('table', { name: 'So sánh chính sách bổ sung hàng' })
  expect(within(within(comparison).getAllByRole('row')[1]).getAllByRole('cell').at(-1)).toHaveTextContent(/^1$/)
  expect(within(within(comparison).getAllByRole('row')[1]).getAllByRole('cell')[5]).toHaveTextContent(/^0$/)
  expect(within(comparison).getByText('Thấp nhất 2,001 / Cao nhất 2,002')).toBeInTheDocument()
  expect(await screen.findByRole('region', { name: 'Cuộn bảng diễn biến theo ngày' })).toHaveAttribute('tabindex', '0')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(api.getReplenishmentDays).toHaveBeenLastCalledWith('token', id, 'persistence', 1, '0.90', 'proposed', 2)
})

const demoId = 'rrv1-' + 'c'.repeat(64)
const anotherId = 'rrv1-' + 'd'.repeat(64)
const forecastId = 'frv1-' + 'e'.repeat(64)

function mockPosition(onHand: number | null = 5, open = 2, demoOverride: Partial<ReplenishmentPosition> = {}) {
  vi.mocked(getReplenishmentPosition).mockImplementation(async (_token, target, view, selection) => ({
    ...target, sku: 'SKU-DEMO', unit: 'unit', on_hand: onHand, open_quantity: open,
    projected_quantity: onHand === null ? null : onHand - open,
    state: onHand === null || view === 'operational' ? 'insufficient_data' : 'available',
    reason_code: onHand === null ? 'STOCK_ROW_MISSING' : view === 'operational' ? 'OPERATIONAL_ROP_NOT_FOUND' : null,
    computed_at: null, rop: view === 'demo' ? selection.lead_time === 1 ? 5 : 4 : null,
    rop_date: view === 'demo' ? selection.reference_date ?? null : null,
    run_id: view === 'demo' ? selection.run_id ?? null : null,
    dataset_class: view === 'demo' ? 'fixture' : null,
    eoq: null, recommendation: false,
    ...(view === 'demo' ? demoOverride : {}),
  }))
}

function mockDemoRun(productId = 10, warehouseId = 20) {
  mockPosition()
  vi.mocked(api.getReplenishmentRun).mockResolvedValue({
    manifest: {
      run_id: demoId, mode: 'operational', dataset_class: 'fixture', binding: { product_id: productId, warehouse_id: warehouseId, unit: 'unit' },
      data_version: 'ddv1-demo', forecast_run_id: forecastId, target: 'gross_fulfilled_units', reporting_scope: 'warehouse', unit: 'unit', created_at: '2026-11-01T00:00:00Z',
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
  expect(await screen.findByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).toBeInTheDocument()
  expect(screen.getByText(/Lượng đặt tham khảo theo EOQ/)).toHaveTextContent('10')
  expect(api.getReplenishmentAlertSources).toHaveBeenCalledWith('token', 10, 20)
  vi.mocked(api.getReplenishmentAlertSources).mockResolvedValue(demoSources(20))
  mockPosition(20)
  await userEvent.selectOptions(screen.getByLabelText('Thời gian cung ứng'), '7')
  expect(await screen.findByText(/Tồn kho trên ngưỡng ROP tham chiếu/)).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cảnh báo bổ sung hàng demo' })).toHaveTextContent(/Tồn hiện tại20 đơn vị/)
  expect(screen.queryByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).not.toBeInTheDocument()
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
  expect(await screen.findByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).toBeInTheDocument()
  vi.mocked(api.getReplenishmentAlertSources).mockRejectedValueOnce(new ApiError('Forbidden', 403))
  vi.mocked(api.getReplenishmentDays).mockReturnValueOnce(new Promise(() => {}))
  await userEvent.selectOptions(screen.getByLabelText('Thời gian cung ứng'), '7')
  expect(await screen.findByText(/Thiếu dữ liệu để đối chiếu/)).toBeInTheDocument()
  expect(screen.queryByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).not.toBeInTheDocument()
})

it('does not display the previous advisory while revisiting a run', async () => {
  vi.clearAllMocks()
  mockDemoRun()
  renderDemo()
  expect(await screen.findByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).toBeInTheDocument()
  vi.mocked(api.getReplenishmentRun).mockReturnValueOnce(new Promise(() => {}))
  await userEvent.click(screen.getByRole('link', { name: 'Mở bản mô phỏng khác' }))
  expect(await screen.findByText('Đang tải chi tiết bổ sung hàng...')).toBeInTheDocument()

  const advisoryAtReload = vi.fn()
  vi.mocked(api.getReplenishmentDays).mockImplementationOnce(() => {
    advisoryAtReload(Boolean(screen.queryByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)))
    return new Promise(() => {})
  })
  await userEvent.click(screen.getByRole('link', { name: 'Quay lại bản mô phỏng' }))
  await waitFor(() => expect(advisoryAtReload).toHaveBeenCalledWith(false))
  expect(screen.queryByText(/Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng/)).not.toBeInTheDocument()
})

it('offers a separate warehouse forecast pilot on the fixture run only', async () => {
  mockDemoRun()
  vi.mocked(api.getReplenishmentDays).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  render(<MemoryRouter initialEntries={['/replenishment/runs/' + demoId]}><Routes><Route path="/replenishment/runs/:runId" element={<ReplenishmentRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByRole('region', { name: 'Demo: Từ dự báo đến điểm đặt lại' })).toBeInTheDocument()
})

function pilotResult(position: number, extra: Partial<ForecastPilot> = {}): ForecastPilotResult {
  return { state: 'ready', reason_code: null, pilot: {
    forecast_run_id: forecastId, replenishment_run_id: demoId,
    warehouse_id: 20, product_id: 10, sku: 'SKU-DEMO', warehouse_code: 'WH-DEMO', unit: 'unit', data_version: 'ddv1-demo',
    algorithm: 'xgboost', lead_time: 7, service_level: '0.90', policy: 'proposed',
    training_cutoff: '2022-06-29T00:00:00Z', origin: '2022-06-30', scenario_day: '2022-07-01',
    forecast_during_lead_time: '14.5', safety_stock: '5.5', rop: 20, simulated_inventory_position: position,
    threshold: position > 20 ? 'above' : 'at_or_below',
    eoq: null, holdout_wape: '0.25', holdout_lead_time_mae: '3.5',
    ...extra,
  } }
}

it.each([
  [17, 'Dưới điểm đặt lại: xem xét bổ sung.'],
  [20, 'Bằng điểm đặt lại: xem xét bổ sung.'],
  [21, 'Trên điểm đặt lại: chưa chạm ngưỡng.'],
] as const)('displays only the exact demo relation %s, source, 7-day lead, known holdout, and missing EOQ', async (position, message) => {
  mockDemoRun()
  vi.mocked(api.getForecastPilot).mockResolvedValueOnce(pilotResult(position))
  renderDemo()
  const pilot = within(await screen.findByRole('region', { name: 'Demo: Từ dự báo đến điểm đặt lại' }))
  expect(await pilot.findByText(message)).toBeInTheDocument()
  expect(pilot.getByText(/thời gian cung ứng giả định 7 ngày/)).toBeInTheDocument()
  expect(pilot.getByText('2022-07-01')).toBeInTheDocument()
  expect(pilot.getByText('2022-06-29T00:00:00Z')).toBeInTheDocument()
  expect(pilot.getByText('14,5 đơn vị')).toBeInTheDocument()
  expect(pilot.getByText(/Sai lệch WAPE trên tập kiểm tra: 25%/)).toBeInTheDocument()
  expect(pilot.getByText(/trung bình của tổng 7 ngày trên tập kiểm tra: 3,5 đơn vị/)).toBeInTheDocument()
  expect(pilot.getByText(/Chưa đủ cơ sở hiển thị lượng đặt EOQ/)).toBeInTheDocument()
  expect(pilot.getByRole('link', { name: 'Mở đúng kết quả dự báo nguồn' })).toHaveAttribute('href', '/forecasting/runs/' + forecastId)
  expect(pilot.getByText(/không gồm đơn B2B đang chờ/)).toBeInTheDocument()
  expect(pilot.queryByRole('button')).not.toBeInTheDocument()
})

it.each([
  { forecast_run_id: 'frv1-' + 'a'.repeat(64) },
  { data_version: 'different' },
  { unit: 'kg' },
  { warehouse_id: 21 },
  { threshold: 'above' },
] satisfies Partial<ForecastPilot>[])('does not display a forecast/action for mixed pair %j', async override => {
  mockDemoRun()
  vi.mocked(api.getForecastPilot).mockResolvedValueOnce(pilotResult(20, override))
  renderDemo()
  const pilot = within(await screen.findByRole('region', { name: 'Demo: Từ dự báo đến điểm đặt lại' }))
  expect(await pilot.findByText(/Chưa có cặp dự báo và bổ sung hàng demo đã xác minh/)).toBeInTheDocument()
  expect(pilot.queryByRole('link')).not.toBeInTheDocument()
  expect(pilot.queryByText(/xem xét bổ sung/)).not.toBeInTheDocument()
})

it('does not show a late pilot after moving to a different replenishment run', async () => {
  mockDemoRun()
  let finish!: (result: ForecastPilotResult) => void
  vi.mocked(api.getForecastPilot).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  renderDemo()
  expect(await screen.findByText(/Đang đối chiếu cặp kết quả demo/)).toBeInTheDocument()
  const signal = vi.mocked(api.getForecastPilot).mock.lastCall?.[2]
  const initial = await api.getReplenishmentRun('token', demoId)
  vi.mocked(api.getReplenishmentRun).mockResolvedValueOnce({ ...initial, manifest: { ...initial.manifest, run_id: anotherId } })
  await userEvent.click(screen.getByRole('link', { name: 'Mở bản mô phỏng khác' }))
  expect(signal?.aborted).toBe(true)
  await act(async () => finish(pilotResult(17)))
  expect(screen.queryByRole('link', { name: 'Mở đúng kết quả dự báo nguồn' })).not.toBeInTheDocument()
})

it.each([true, false])('only shows a positive EOQ when valid cost assumptions are present: %s', async hasCosts => {
  mockDemoRun()
  const run = await api.getReplenishmentRun('token', demoId)
  if (!hasCosts) run.manifest.config.costs = { ...run.manifest.config.costs, holding_cost: null }
  run.calibration!.eoq = { state: 'ready', quantity: 18, raw: '17.5', reason_code: null }
  vi.mocked(api.getForecastPilot).mockResolvedValueOnce(pilotResult(17, { eoq: 18, holdout_wape: null, holdout_lead_time_mae: null }))
  renderDemo()
  const section = within(await screen.findByRole('region', { name: 'Demo: Từ dự báo đến điểm đặt lại' }))
  await section.findByText(/Dưới điểm đặt lại/)
  expect(section.queryByText('18 đơn vị') !== null).toBe(hasCosts)
  expect(section.queryByText(/WAPE/)).not.toBeInTheDocument()
})

it('preserves verified 9986 while illustrating 13, 14 and 15 without fetches', async () => {
  mockDemoRun()
  vi.mocked(api.getForecastPilot).mockResolvedValueOnce(pilotResult(9986, {
    rop: 14, forecast_during_lead_time: '14', safety_stock: '0',
  }))
  renderDemo()
  const pilot = within(await screen.findByRole('region', { name: 'Demo: Từ dự báo đến điểm đặt lại' }))
  expect(await pilot.findByText(/9\.986 đơn vị >.*14 đơn vị/)).toBeInTheDocument()
  const example = within(pilot.getByRole('region', { name: 'Ví dụ: So sánh với ngưỡng 14' }))
  const calls = vi.mocked(api.getForecastPilot).mock.calls.length
  for (const [amount, symbol, verdict] of [[13, '<', 'Cần xem xét đặt thêm'], [14, '=', 'Cần xem xét đặt thêm'], [15, '>', 'Chưa chạm ngưỡng đặt thêm']] as const) {
    await userEvent.click(example.getByRole('button', { name: 'Tồn ' + amount }))
    expect(example.getByRole('status')).toHaveTextContent(`${amount} ${symbol} 14`)
    expect(example.getByRole('status')).toHaveTextContent(verdict)
    expect(pilot.getByText(/9\.986 đơn vị >.*14 đơn vị/)).toBeInTheDocument()
  }
  expect(vi.mocked(api.getForecastPilot)).toHaveBeenCalledTimes(calls)
  const concepts = within(pilot.getByRole('region', { name: 'Phân biệt các số liệu kho' }))
  expect(concepts.getByText('Hàng từ nhà cung cấp đang về').nextElementSibling).toHaveTextContent('Chưa có số liệu vận hành đã xác minh')
  expect(concepts.getByText('Đơn khách B2B chờ giao').nextElementSibling).toHaveTextContent('không phải hàng nhập')
})

it('shows input facts once and keeps actual and projected demo conclusions separate', async () => {
  mockDemoRun()
  vi.mocked(api.getReplenishmentAlertSources).mockResolvedValue(demoSources(6))
  mockPosition(6)
  renderDemo()
  const panel = within(await screen.findByRole('region', { name: 'Cảnh báo bổ sung hàng demo' }))
  const facts = await panel.findByLabelText('Số liệu tồn dùng chung')
  expect(within(facts).getByText('6 đơn vị')).toBeInTheDocument()
  expect(within(facts).getByText('2 đơn vị')).toBeInTheDocument()
  expect(within(facts).getByText('4 đơn vị')).toBeInTheDocument()
  expect(panel.getAllByLabelText('Số liệu tồn dùng chung')).toHaveLength(1)
  expect(within(panel.getByRole('region', { name: 'Tồn hiện tại so với ROP' })).getByText(/Tồn kho trên ngưỡng/)).toBeInTheDocument()
  expect(await within(panel.getByRole('region', { name: 'Tồn dự kiến so với ROP' })).findByText(/Tồn dự kiến tại hoặc dưới/)).toBeInTheDocument()
})

it('shows one missing-stock notice and no stock verdict even with conflicting old source', async () => {
  mockDemoRun()
  mockPosition(null)
  renderDemo()
  const panel = within(await screen.findByRole('region', { name: 'Cảnh báo bổ sung hàng demo' }))
  expect(await panel.findAllByText(/Chưa có bản ghi tồn kho/)).toHaveLength(1)
  expect(panel.queryByRole('region', { name: 'Tồn hiện tại so với ROP' })).not.toBeInTheDocument()
  expect(panel.queryByRole('region', { name: 'Tồn dự kiến so với ROP' })).not.toBeInTheDocument()
  expect(panel.queryByLabelText('Số liệu tồn dùng chung')).not.toBeInTheDocument()
})

it('suppresses mismatched projected snapshot without hiding the independently verified actual verdict', async () => {
  mockDemoRun()
  mockPosition(5, 2, { projected_quantity: 99 })
  renderDemo()
  const panel = within(await screen.findByRole('region', { name: 'Cảnh báo bổ sung hàng demo' }))
  expect(await panel.findByText(/Tồn thực tại hoặc dưới/)).toBeInTheDocument()
  expect(await panel.findByText(/Số liệu hoặc tham chiếu tồn dự kiến không khớp/)).toBeInTheDocument()
  expect(panel.queryByText(/Tồn dự kiến trên ROP/)).not.toBeInTheDocument()
  expect(panel.queryByText('99 đơn vị')).not.toBeInTheDocument()
})

it('shortens exact run keys and de-duplicates each entity without merging product and warehouse', async () => {
  const user = userEvent.setup()
  const copy = vi.spyOn(navigator.clipboard, 'writeText')
  mockDemoRun()
  const run = await api.getReplenishmentRun('token', demoId)
  run.entity!.product_name = run.entity!.sku
  run.entity!.warehouse_name = ' Kho kho '
  renderDemo()
  const display = await screen.findByTitle(demoId)
  expect(display).toHaveTextContent(demoId.slice(0, 14) + '…')
  expect(screen.getByText('Sản phẩm', { exact: true }).nextElementSibling).toHaveTextContent(/^SKU-DEMO$/)
  expect(screen.getAllByText('Kho', { exact: true }).find(label => label.tagName === 'DT')?.nextElementSibling).toHaveTextContent('Kho kho (WH-DEMO)')
  await user.click(screen.getByRole('button', { name: 'Sao chép mã kết quả' }))
  expect(copy).toHaveBeenCalledWith(demoId)
})
