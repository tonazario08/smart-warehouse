import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ForecastRunPage } from './ForecastRunPage'
import * as api from './api'

const auth = vi.hoisted(() => ({ role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: auth.role } }) }))
vi.mock('./api', () => ({ getForecastRun: vi.fn(), getForecastPredictions: vi.fn(), forecastError: () => 'Không thể tải dữ liệu.' }))
it('rejects malformed run IDs without requesting data', async () => {
  render(<MemoryRouter initialEntries={['/forecasting/runs/not-valid']}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã kết quả dự báo không hợp lệ.')
  expect(api.getForecastRun).not.toHaveBeenCalled()
})

it('shows null actual distinctly from zero and renders WAPE as a percentage', async () => {
  const id = 'frv1-' + 'a'.repeat(64)
  vi.mocked(api.getForecastRun).mockResolvedValue({ manifest: { run_id: id, mode: 'research', kind: 'evaluation', dataset_class: 'fixture', data_version: 'ddv2-test', target: 'reported_daily_unit_sales', reporting_scope: 'company_aggregate', unit: 'unit', knowledge_time_mode: 'retrospective_final_vintage', trained_through: '2021-12-31', training_information_cutoff: null, admission_cutoff: null, knowledge_bound: null, origin_start: '2022-01-01', origin_end: '2022-01-01', horizons: [1, 7], generated_at: '2022-01-01T00:00:00Z', limitations: [] }, metrics: { 'persistence:1': { count: 2, origin_count: 2, mae: 1, wape: 0.25, origin_total_mae: 1, reason: null, wape_reason: null } }, binding: null, entity: null, applicability: 'retrospective', stale: null, fixture_label: 'Dữ liệu kiểm thử' })
  vi.mocked(api.getForecastPredictions).mockResolvedValue({ items: [{ series_key: 's', origin: '2022-01-01', target_date: '2022-01-02', lead: 1, horizon: 1, algorithm: 'persistence', prediction: 0, actual: null, unit: 'unit' }, { series_key: 's', origin: '2022-01-02', target_date: '2022-01-03', lead: 1, horizon: 1, algorithm: 'persistence', prediction: 0, actual: 0, unit: 'unit' }], total: 21, page: 1, page_size: 20 })
  render(<MemoryRouter initialEntries={['/forecasting/runs/' + id]}><Routes><Route path="/forecasting/runs/:runId" element={<ForecastRunPage />} /></Routes></MemoryRouter>)
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
