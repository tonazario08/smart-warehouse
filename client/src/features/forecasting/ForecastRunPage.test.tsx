import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ForecastRunPage } from './ForecastRunPage'
import * as api from './api'
import type { ForecastChartResult, ForecastRun, Prediction } from './types'

const auth = vi.hoisted(() => ({ role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: auth.role } }) }))
vi.mock('./api', () => ({ getForecastRun: vi.fn(), getForecastPredictions: vi.fn(), getForecastChart: vi.fn(), forecastError: () => 'Không thể tải dữ liệu.' }))
beforeEach(() => { vi.mocked(api.getForecastChart).mockReset().mockResolvedValue({ items: [], series_key: null }) })
it('rejects malformed run IDs without requesting data', async () => {
  render(<MemoryRouter initialEntries={['/forecasting/runs/not-valid']}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã kết quả dự báo không hợp lệ.')
  expect(api.getForecastRun).not.toHaveBeenCalled()
})

it('shows null actual distinctly from zero and renders WAPE as a percentage', async () => {
  const id = 'frv1-' + 'a'.repeat(64)
  vi.mocked(api.getForecastRun).mockResolvedValue({ manifest: { run_id: id, mode: 'research', kind: 'evaluation', dataset_class: 'fixture', data_version: 'ddv2-test', target: 'reported_daily_unit_sales', reporting_scope: 'company_aggregate', unit: 'unit', knowledge_time_mode: 'retrospective_final_vintage', trained_through: '2021-12-31', training_information_cutoff: null, admission_cutoff: null, knowledge_bound: null, origin_start: '2022-01-01', origin_end: '2022-01-01', horizons: [1, 7], generated_at: '2022-01-01T00:00:00Z', limitations: [] }, metrics: { 'persistence:1': { count: 2, origin_count: 2, mae: 1, wape: 0.25, origin_total_mae: 1, reason: null, wape_reason: null } }, binding: null, entity: null, applicability: 'retrospective', stale: null, fixture_label: 'Dữ liệu kiểm thử' })
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: [{ series_key: 's', origin: '2022-01-01', target_date: '2022-01-02', lead: 1, horizon: 1, algorithm: 'persistence', prediction: 0, actual: null, unit: 'unit' }, { series_key: 's', origin: '2022-01-02', target_date: '2022-01-03', lead: 1, horizon: 1, algorithm: 'persistence', prediction: 0, actual: 0, unit: 'unit' }], total: 21, page: 1, page_size: 20 })
  const tableData = await api.getForecastPredictions('token', id, 1, 'persistence', 1)
  vi.mocked(api.getForecastChart).mockResolvedValueOnce({ items: tableData.items, series_key: 's' })
  render(<MemoryRouter initialEntries={['/forecasting/runs/' + id]}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).toBeInTheDocument()
  expect(await screen.findByText('Chưa có')).toBeInTheDocument()
  expect(screen.getByText('25%')).toBeInTheDocument()
  expect(screen.getAllByText('0 đơn vị')).toHaveLength(3)
  expect(screen.getByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(api.getForecastPredictions).toHaveBeenLastCalledWith('token', id, 1, 'persistence', 2)
  await userEvent.selectOptions(await screen.findByLabelText('Khoảng dự báo'), '7')
  expect(api.getForecastPredictions).toHaveBeenLastCalledWith('token', id, 7, 'persistence', 1)
  await userEvent.selectOptions(await screen.findByLabelText('Phương pháp'), 'xgboost')
  expect(api.getForecastPredictions).toHaveBeenLastCalledWith('token', id, 7, 'xgboost', 1)
})

it('clears research content immediately when the role changes and access is denied', async () => {
  const id = 'frv1-' + 'a'.repeat(64)
  auth.role = 'admin'
  const element = () => <MemoryRouter initialEntries={['/forecasting/runs/' + id]}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>
  const { rerender } = render(element())
  expect(await screen.findByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  vi.mocked(api.getForecastRun).mockRejectedValue(new Error('denied'))
  auth.role = 'warehouse'
  rerender(element())
  expect(screen.queryByText('Dữ liệu kiểm thử')).not.toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu.')
  auth.role = 'admin'
})

const pilotId = 'frv1-96f99dca2c706b19e144b975e591724c777b096001c537e3288b06320d73c472'
const pilotVersion = 'ddv1-2357daebb159601338bd97e41362bb21dfe93c3abd72252998e51e87144f8348'
function caseRecord(id = pilotId, dataVersion = pilotVersion): ForecastRun {
  return {
    manifest: { run_id: id, mode: 'operational', kind: 'evaluation', dataset_class: 'fixture', data_version: dataVersion,
      target: 'gross_fulfilled_units', reporting_scope: 'warehouse', unit: 'unit', knowledge_time_mode: 'historical',
      trained_through: '2021-12-31', training_information_cutoff: null, admission_cutoff: null, knowledge_bound: null,
      origin_start: '2022-01-01', origin_end: '2022-01-10', horizons: [1, 7], generated_at: '2022-01-01T00:00:00Z',
      limitations: ['NOT_LATENT_DEMAND', 'AVAILABILITY_UNKNOWN'],
    },
    metrics: { 'persistence:1': { count: 365, origin_count: 365, mae: 0, wape: 0, origin_total_mae: 0, reason: null, wape_reason: null },
      'xgboost:1': { count: 365, origin_count: 365, mae: 0, wape: 0, origin_total_mae: 0, reason: null, wape_reason: null } },
    binding: null, entity: { product_name: 'M7-E2E-SYNTHETIC', sku: ' M7-E2E-SYNTHETIC ',
      warehouse_name: 'Kho mẫu', warehouse_code: 'M7-E2E-SYNTHETIC' },
    applicability: 'operational', stale: null, fixture_label: 'Dữ liệu kiểm thử',
  }
}

function detail(id = pilotId) {
  return <MemoryRouter initialEntries={['/forecasting/runs/' + id]}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>
}

it('keeps one metadata block, distinct entities, full copied IDs and accessible collapsed limits', async () => {
  const user = userEvent.setup()
  const copy = vi.spyOn(navigator.clipboard, 'writeText')
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  render(detail())
  expect(await screen.findByRole('heading', { name: 'Thông tin kết quả' })).toBeInTheDocument()
  expect(screen.getAllByRole('heading', { name: /^Thông tin kết quả$/ })).toHaveLength(1)
  expect(screen.getByText('Sản phẩm').nextElementSibling).toHaveTextContent(/^M7-E2E-SYNTHETIC$/)
  expect(screen.getByText('Kho', { exact: true }).nextElementSibling).toHaveTextContent(/^Kho mẫu \(M7-E2E-SYNTHETIC\)$/)
  expect(screen.getByTitle(pilotId)).toHaveTextContent(pilotId.slice(0, 14) + '…')
  expect(screen.getByTitle(pilotVersion)).toHaveTextContent(pilotVersion.slice(0, 14) + '…')
  await user.click(screen.getByRole('button', { name: 'Sao chép mã kết quả' }))
  expect(copy).toHaveBeenCalledWith(pilotId)
  expect(screen.getByRole('status')).toHaveTextContent('Đã sao chép')
  const summary = screen.getByText('Lưu ý phạm vi mô hình (2)')
  expect(summary.parentElement).not.toHaveAttribute('open')
  summary.focus()
  expect(summary).toHaveFocus()
  // Native keyboard activation is checked in a real browser; jsdom does not activate summary on Enter.
  await user.click(summary)
  expect(summary.parentElement).toHaveAttribute('open')
  expect(screen.getByText('Không đo nhu cầu tiềm ẩn.')).toBeVisible()
})

it('only explains a constant sequence for the exact immutable Persistence fixture, not another method or data version', async () => {
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const first = render(detail())
  expect(await screen.findByText(/WAPE = 0% do chuỗi hằng 2 đơn vị/)).toBeInTheDocument()
  expect(screen.getByText(/không phải tỷ lệ dự báo đúng/)).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Phương pháp'), 'xgboost')
  expect(await screen.findByText(/WAPE = 0% trên tập đánh giá này không chứng minh/)).toBeInTheDocument()
  expect(screen.queryByText(/chuỗi hằng 2 đơn vị/)).not.toBeInTheDocument()
  first.unmount()
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord(pilotId, 'ddv1-other'))
  render(detail())
  expect(await screen.findByText(/WAPE = 0% trên tập đánh giá này không chứng minh/)).toBeInTheDocument()
  expect(screen.queryByText(/chuỗi hằng 2 đơn vị/)).not.toBeInTheDocument()
})

it('plots one exact lead and series independently from all table rows, leaves a real gap, and preserves the full table', async () => {
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  const make = (origin: string, target: string, value: number | null, lead = 7, series = 'warehouse-test'): Prediction => ({
    series_key: series, origin, target_date: target, lead, horizon: 7, algorithm: 'persistence', prediction: 2, actual: value, unit: 'unit',
  })
  const requests = vi.mocked(api.getForecastPredictions)
  requests.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const data = [
    make('2022-01-01', '2022-01-08', 2),
    make('2022-01-02', '2022-01-09', null),
    make('2022-01-03', '2022-01-10', 0),
    make('2022-01-07', '2022-01-08', 5, 1),
    make('2022-01-01', '2022-01-08', 9, 7, 'other'),
  ]
  requests.mockImplementation(async (_token, _id, horizon) => ({ items: horizon === 7 ? data : [], total: horizon === 7 ? 60 : 0, page: 1, page_size: 20 }))
  vi.mocked(api.getForecastChart).mockImplementation(async (_token, _id, horizon, _algorithm, lead) =>
    horizon === 7 && lead === 7 ? { items: data.slice(0, 3), series_key: 'warehouse-test' } : { items: [], series_key: null })
  render(detail())
  await userEvent.selectOptions(await screen.findByLabelText('Khoảng dự báo'), '7')
  await userEvent.selectOptions(await screen.findByLabelText('Bước dự báo của biểu đồ'), '7')
  const graph = await screen.findByRole('img', { name: 'Biểu đồ dự báo và thực tế' })
  expect(graph).toHaveAccessibleDescription(/ngày thứ 7.*2022-01-08 đến 2022-01-10; 3 điểm dự báo, 2 có thực tế/)
  const actual = graph.querySelector('.forecast-chart__actual')?.getAttribute('d') ?? ''
  expect(actual.match(/M/g)).toHaveLength(2)
  expect(actual).not.toContain('L')
  expect(graph.querySelector('circle[data-actual="0"]')).toBeInTheDocument()
  expect(graph.querySelectorAll('.forecast-chart__prediction-point')).toHaveLength(3)
  expect(within(screen.getByRole('table', { name: 'Các giá trị dự báo' })).getAllByRole('row')).toHaveLength(6)
})


function forecastPoints(count: number, horizon = 1, lead = 1, algorithm: Prediction['algorithm'] = 'persistence'): Prediction[] {
  const toDate = (day: number) => new Date(Date.UTC(2022, 0, day)).toISOString().slice(0, 10)
  return Array.from({ length: count }, (_, index) => ({
    series_key: 's', origin: toDate(index + 1), target_date: toDate(index + 1 + lead), lead, horizon, algorithm,
    prediction: 2, actual: index === 6 ? null : index === 7 ? 0 : 2, unit: 'unit',
  }))
}

it('retains the exact 30-point chart on table page changes, keeps table size and does not query chart again', async () => {
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  const chartData = forecastPoints(30)
  vi.mocked(api.getForecastChart).mockResolvedValueOnce({ items: chartData, series_key: 's' })
  vi.mocked(api.getForecastPredictions).mockResolvedValueOnce({ items: chartData.slice(0, 20), total: 30, page: 1, page_size: 20 })
  render(detail())
  const graph = await screen.findByRole('img', { name: 'Biểu đồ dự báo và thực tế' })
  expect(screen.getByRole('heading', { name: /30 ngày đích gần nhất có dữ liệu/ })).toBeInTheDocument()
  expect(graph).toHaveAccessibleDescription(/Từ 2022-01-02 đến 2022-01-31; 30 điểm dự báo, 29 có thực tế/)
  expect(graph.querySelectorAll('.forecast-chart__prediction-point')).toHaveLength(30)
  expect(within(await screen.findByRole('table', { name: 'Các giá trị dự báo' })).getAllByRole('row')).toHaveLength(21)
  let finish!: (value: Awaited<ReturnType<typeof api.getForecastPredictions>>) => void
  vi.mocked(api.getForecastPredictions).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(screen.getByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).toBe(graph)
  expect(screen.getByText('Đang tải bảng chi tiết dự báo…')).toBeVisible()
  await act(async () => finish({ items: chartData.slice(20), total: 30, page: 2, page_size: 20 }))
  expect(screen.getByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).toBe(graph)
  expect(vi.mocked(api.getForecastChart)).toHaveBeenCalledTimes(1)
  expect(vi.mocked(api.getForecastPredictions)).toHaveBeenLastCalledWith('token', pilotId, 1, 'persistence', 2)
})

it('defaults to lead 1, lets the 7-day chart switch to lead 6 alone, and drops a stale response on horizon 1', async () => {
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 })
  let finish!: (result: ForecastChartResult) => void
  vi.mocked(api.getForecastChart).mockImplementation((_token, _id, horizon, _algorithm, lead) =>
    horizon === 7 && lead === 6 ? new Promise(resolve => { finish = resolve })
      : Promise.resolve({ items: forecastPoints(2, horizon, lead), series_key: 's' }))
  render(detail())
  expect(await screen.findByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).toHaveAccessibleDescription(/Bước ngày thứ 1/)
  await userEvent.selectOptions(screen.getByLabelText('Khoảng dự báo'), '7')
  const selector = await screen.findByLabelText('Bước dự báo của biểu đồ')
  expect(selector).toHaveValue('1')
  const tableCallCount = vi.mocked(api.getForecastPredictions).mock.calls.length
  await userEvent.selectOptions(selector, '6')
  expect(vi.mocked(api.getForecastChart)).toHaveBeenLastCalledWith('token', pilotId, 7, 'persistence', 6, expect.any(AbortSignal))
  expect(vi.mocked(api.getForecastPredictions)).toHaveBeenCalledTimes(tableCallCount)
  const oldSignal = vi.mocked(api.getForecastChart).mock.lastCall?.[5]
  await userEvent.selectOptions(screen.getByLabelText('Khoảng dự báo'), '1')
  expect(oldSignal?.aborted).toBe(true)
  expect(screen.queryByLabelText('Bước dự báo của biểu đồ')).not.toBeInTheDocument()
  await act(async () => finish({ items: forecastPoints(2, 7, 6), series_key: 's' }))
  expect(await screen.findByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).toHaveAccessibleDescription(/Kỳ dự báo 1 ngày · Bước ngày thứ 1/)
  expect(vi.mocked(api.getForecastChart)).toHaveBeenLastCalledWith('token', pilotId, 1, 'persistence', 1, expect.any(AbortSignal))
  await userEvent.selectOptions(screen.getByLabelText('Khoảng dự báo'), '7')
  expect(await screen.findByLabelText('Bước dự báo của biểu đồ')).toHaveValue('1')
})

it.each(['failure', 'mixed series', 'over cap', 'empty'] as const)('keeps the independent table available with chart %s', async scenario => {
  vi.mocked(api.getForecastRun).mockResolvedValue(caseRecord())
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: forecastPoints(1), page: 1, page_size: 20, total: 1 })
  const chart = vi.mocked(api.getForecastChart)
  if (scenario === 'failure') chart.mockRejectedValueOnce(new Error('unavailable'))
  if (scenario === 'mixed series') chart.mockResolvedValueOnce({ items: [{ ...forecastPoints(1)[0], series_key: 'other' }], series_key: 's' })
  if (scenario === 'over cap') chart.mockResolvedValueOnce({ items: forecastPoints(31), series_key: 's' })
  render(detail())
  expect(await screen.findByRole('table', { name: 'Các giá trị dự báo' })).toBeInTheDocument()
  if (scenario === 'empty') expect(await screen.findByText(/Chưa có điểm cho bước này/)).toBeVisible()
  else expect(await screen.findByText(/Không tải được biểu đồ/)).toBeVisible()
  expect(screen.queryByRole('img', { name: 'Biểu đồ dự báo và thực tế' })).not.toBeInTheDocument()
})
