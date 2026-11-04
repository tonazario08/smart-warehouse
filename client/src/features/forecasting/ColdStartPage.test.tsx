import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ColdStartPage } from './ColdStartPage'
import * as api from './coldStartApi'

const auth = vi.hoisted(() => ({ token: 'first', id: 1, role: 'warehouse' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: auth.token, user: { id: auth.id, role: auth.role } }) }))
vi.mock('./coldStartApi', () => ({ getColdStartStatus: vi.fn(), getColdStartRun: vi.fn(), coldStartError: () => 'Không thể tải báo cáo.' }))
vi.mock('./api', () => ({ getForecastStatus: vi.fn().mockResolvedValue({ state: 'unavailable', reason_code: null, latest: null }), listForecastRuns: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }), forecastError: () => 'Không thể tải dữ liệu.' }))
const metric = { samples: 2, predicted: 1, baseline_predicted: 1, actual: 2, compared: 1, excluded_prediction: 1, excluded_baseline: 1, excluded_actual: 0, excluded_comparison: 1, actual_sum: 0, category_count: 1, mae: 0, baseline_mae: 2, wape: null, baseline_wape: null }
const run = { run_id: 'csv1-test', stale: false, report: { schema_version: 'cold-start-public/1', fixture_label: 'Dữ liệu kiểm thử', operational_state: 'unavailable', target: 'gross_fulfilled_units', unit: 'cái', scope: 'single-warehouse-fixture', created_at: '2026-11-05T00:00:00Z', train_cutoff: '2026-01-12T00:00:00Z', validation_cutoff: '2026-01-24T00:00:00Z', holdout_end: '2026-02-05', data_versions: ['ddv1-test'], reference_population: 3, selected_k: 1, selection_reason: 'validation_common_horizon_7_mae', metrics: { '1': metric, '7': metric }, samples: [ { origin: '2026-01-25', horizon: 1, prediction: 0, baseline: null, reference_count: 3, confidence: 'cluster', reason: null }, { origin: '2026-01-25', horizon: 7, prediction: null, baseline: 0, reference_count: 0, confidence: 'unavailable', reason: 'insufficient_references' } ], limitations: ['FIXTURE_ONLY', 'REAL_EVALUATION_NOT_VERIFIED', 'OPERATIONAL_UNAVAILABLE'] } } as const
const ready = { state: 'ready', reason_code: null, latest_run_id: 'csv1-test', operational_state: 'unavailable' } as const
const page = () => <MemoryRouter><ColdStartPage /></MemoryRouter>
beforeEach(() => { auth.token = 'first'; auth.id = 1; auth.role = 'warehouse'; vi.resetAllMocks(); vi.mocked(api.getColdStartStatus).mockResolvedValue(ready); vi.mocked(api.getColdStartRun).mockResolvedValue(run) })

it('shows fixture, limits, horizons and distinguishes zero from missing values', async () => {
  render(page())
  expect(await screen.findByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  expect(screen.getByText(/Chưa sẵn sàng cho vận hành/)).toBeInTheDocument()
  expect(screen.getByText(/chưa được xác minh trên nguồn nhiều sản phẩm/)).toBeInTheDocument()
  expect(screen.getByText(/Đơn vị xuất hàng/)).toHaveTextContent('cái')
  expect(screen.getByRole('columnheader', { name: 'Mẫu so sánh' })).toBeInTheDocument()
  expect(screen.getAllByText('1 ngày').length).toBeGreaterThan(0)
  expect(screen.getAllByText('7 ngày').length).toBeGreaterThan(0)
  expect(screen.getAllByText('0').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Không đủ dữ liệu').length).toBeGreaterThan(0)
})

it.each([['unavailable', '^Chưa có báo cáo$'], ['failed', 'không thành công'], ['stale', 'quá hạn']] as const)('shows %s without fetching a run', async (state, text) => {
  vi.mocked(api.getColdStartStatus).mockResolvedValue({ state, reason_code: 'TEST', latest_run_id: null, operational_state: 'unavailable' })
  render(page())
  expect(await screen.findByText(new RegExp(text, 'i'))).toBeInTheDocument()
  expect(api.getColdStartRun).not.toHaveBeenCalled()
})

it('does not present a run that turns stale between requests', async () => {
  vi.mocked(api.getColdStartRun).mockResolvedValue({ ...run, stale: true })
  render(page())
  expect(await screen.findByText(/quá hạn/i)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('rejects obsolete status before starting a run request', async () => {
  let resolve!: (status: typeof ready) => void
  vi.mocked(api.getColdStartStatus).mockImplementation(token => token === 'first' ? new Promise(done => { resolve = done }) : Promise.resolve({ ...ready, state: 'unavailable', latest_run_id: null }))
  const view = render(page())
  auth.token = 'second'; auth.id = 2; view.rerender(page())
  await screen.findByRole('heading', { name: 'Chưa có báo cáo' })
  await act(async () => { resolve(ready) })
  expect(api.getColdStartRun).not.toHaveBeenCalled()
})

it('discards an obsolete run after identity changes', async () => {
  let resolve!: (value: typeof run) => void
  vi.mocked(api.getColdStartRun).mockImplementation(() => new Promise(done => { resolve = done }))
  const view = render(page())
  await vi.waitFor(() => expect(api.getColdStartRun).toHaveBeenCalled())
  auth.token = 'second'; auth.id = 2
  vi.mocked(api.getColdStartStatus).mockResolvedValue({ ...ready, state: 'unavailable', latest_run_id: null })
  view.rerender(page()); await screen.findByRole('heading', { name: 'Chưa có báo cáo' })
  await act(async () => { resolve(run) })
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('offers retry and blocks the client role', async () => {
  vi.mocked(api.getColdStartStatus).mockRejectedValueOnce(new Error('offline'))
  const view = render(page())
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải báo cáo.')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  auth.role = 'client'; view.rerender(page())
  expect(screen.queryByText('Dữ liệu kiểm thử')).not.toBeInTheDocument()
  expect(screen.getByText(/không có quyền/)).toBeInTheDocument()
})

it('shows the selected cluster count and names the comparison in Vietnamese', async () => {
  render(page())
  expect(await screen.findByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  expect(screen.getByText('Số cụm đã chọn').parentElement).toHaveTextContent('1')
  expect(screen.getAllByText(/mốc so sánh/i).length).toBeGreaterThan(0)
  expect(screen.queryByText(/baseline/i)).not.toBeInTheDocument()
})

it('shows the Vietnamese breadcrumb with a trailing slash', async () => {
  const { Breadcrumbs } = await import('../../shared/layout/Breadcrumbs')
  render(<MemoryRouter initialEntries={['/forecasting/cold-start/']}><Breadcrumbs /></MemoryRouter>)
  expect(screen.getByRole('navigation', { name: 'Điều hướng vị trí' })).toHaveTextContent('Sản phẩm mới')
})

it('offers a link from forecasting to the new product report', async () => {
  const { ForecastingPage } = await import('./ForecastingPage')
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Xem dự báo cho sản phẩm mới' })).toHaveAttribute('href', '/forecasting/cold-start')
})
