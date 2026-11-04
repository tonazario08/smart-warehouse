import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ForecastingPage } from './ForecastingPage'
import * as api from './api'
import type { ForecastRun } from './types'
import { formatDateTime } from '../../shared/lib/formatters'

const auth = vi.hoisted(() => ({ role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: auth.role } }) }))
vi.mock('./api', () => ({ getForecastStatus: vi.fn(), listForecastRuns: vi.fn(), forecastError: () => 'Không thể tải dữ liệu.' }))
beforeEach(() => { auth.role = 'admin'; vi.resetAllMocks(); vi.mocked(api.getForecastStatus).mockResolvedValue({ state: 'unavailable', reason_code: 'NO_ADMITTED_OPERATIONAL_SERIES', latest: null }); vi.mocked(api.listForecastRuns).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }) })
it('shows honest operational absence and administrator research tab', async () => {
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  expect(await screen.findByText('Chưa có dữ liệu vận hành đủ điều kiện để dự báo.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Vận hành' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Vận hành' })).toHaveClass('ui-button', 'ui-button--primary')
  expect(screen.getByRole('button', { name: 'Nghiên cứu' })).toHaveClass('ui-button', 'ui-button--secondary')
  await userEvent.click(screen.getByRole('button', { name: 'Nghiên cứu' }))
  expect(screen.getByRole('button', { name: 'Nghiên cứu' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Nghiên cứu' })).toHaveClass('ui-button--primary')
  expect(await screen.findByText('Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.')).toBeInTheDocument()
  expect(api.getForecastStatus).toHaveBeenLastCalledWith('token', 'research')
})

it('discards a late operational response after switching to research', async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.getForecastStatus>>) => void
  vi.mocked(api.getForecastStatus).mockImplementation((_token, mode) => mode === 'operational' ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ state: 'unavailable', reason_code: 'NO_RUNS', latest: null }))
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  await userEvent.click(screen.getByRole('button', { name: 'Nghiên cứu' }))
  expect(await screen.findByText('Chưa có kết quả dự báo trong phạm vi này.')).toBeInTheDocument()
  finish({ state: 'unavailable', reason_code: 'NO_ADMITTED_OPERATIONAL_SERIES', latest: null })
  expect(screen.queryByText('Chưa có dữ liệu vận hành đủ điều kiện để dự báo.')).not.toBeInTheDocument()
})

it('removes research access immediately after a role change', async () => {
  const page = () => <MemoryRouter><ForecastingPage /></MemoryRouter>
  const { rerender } = render(page())
  await userEvent.click(screen.getByRole('button', { name: 'Nghiên cứu' }))
  expect(await screen.findByText('Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.')).toBeInTheDocument()
  auth.role = 'warehouse'
  rerender(page())
  expect(screen.queryByRole('button', { name: 'Nghiên cứu' })).not.toBeInTheDocument()
  expect(screen.queryByText('Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.')).not.toBeInTheDocument()
})

it.each([
  ['failed', 'FIT_FAILED', 'Lần tạo kết quả gần nhất không thành công'],
  ['unavailable', 'CATALOG_UNAVAILABLE', 'Danh mục dự báo hiện không khả dụng'],
] as const)('distinguishes %s status', async (state, reason, text) => {
  vi.mocked(api.getForecastStatus).mockResolvedValue({ state, reason_code: reason, latest: null })
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
})

it('offers retry after a request fails and keeps the session', async () => {
  vi.mocked(api.getForecastStatus).mockRejectedValueOnce(new Error('network'))
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải dữ liệu.')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText('Chưa có dữ liệu vận hành đủ điều kiện để dự báo.')).toBeInTheDocument()
})

it('shows each listed run’s information cutoff and actual horizons, including an unknown cutoff', async () => {
  const makeRun = (id: string, cutoff: string | null, horizons: number[]): ForecastRun => ({
    manifest: { run_id: id, mode: 'research', kind: 'evaluation', dataset_class: 'fixture', data_version: 'ddv2-test', target: 'reported_daily_unit_sales', reporting_scope: 'company_aggregate', unit: 'unit', knowledge_time_mode: 'retrospective_final_vintage', trained_through: '2021-12-31', training_information_cutoff: cutoff, admission_cutoff: null, knowledge_bound: null, origin_start: '2022-01-01', origin_end: '2022-12-01', horizons, generated_at: '2026-01-01T00:00:00Z', limitations: [] },
    metrics: null, binding: null, entity: null, applicability: 'retrospective', stale: null, fixture_label: 'Dữ liệu kiểm thử',
  })
  const first = makeRun('frv1-' + 'a'.repeat(64), '2024-06-15T00:00:00Z', [1, 7])
  const second = makeRun('frv1-' + 'b'.repeat(64), null, [7])
  vi.mocked(api.listForecastRuns).mockResolvedValue({ items: [first, second], total: 2, page: 1, page_size: 20 })
  render(<MemoryRouter><ForecastingPage /></MemoryRouter>)
  const row1 = (await screen.findByRole('link', { name: first.manifest.run_id })).closest('tr')!
  const row2 = screen.getByRole('link', { name: second.manifest.run_id }).closest('tr')!
  expect(screen.getByRole('columnheader', { name: 'Giới hạn thông tin' })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: 'Khoảng dự báo' })).toBeInTheDocument()
  expect(within(row1).getByText(formatDateTime(first.manifest.training_information_cutoff))).toBeInTheDocument()
  expect(within(row1).getByText('1 ngày, 7 ngày')).toBeInTheDocument()
  expect(within(row2).getByText('Không xác định')).toBeInTheDocument()
  expect(within(row2).getByText('7 ngày')).toBeInTheDocument()
})
