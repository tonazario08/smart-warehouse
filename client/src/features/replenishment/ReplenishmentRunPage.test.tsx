import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ReplenishmentRunPage } from './ReplenishmentRunPage'
import * as api from './api'

vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: 'admin' } }) }))
vi.mock('./api', () => ({ getReplenishmentRun: vi.fn(), getReplenishmentDays: vi.fn(), replenishmentError: () => 'Không thể tải dữ liệu.' }))
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
