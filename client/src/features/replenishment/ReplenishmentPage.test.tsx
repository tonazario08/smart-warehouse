import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ReplenishmentPage } from './ReplenishmentPage'
import * as api from './api'

const auth = vi.hoisted(() => ({ role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: 'token', user: { id: 1, role: auth.role } }) }))
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), getReplenishmentStatus: vi.fn(), listReplenishmentRuns: vi.fn(), replenishmentError: () => 'Không thể tải dữ liệu.' }))
beforeEach(() => { auth.role = 'admin'; vi.resetAllMocks() })
it('shows unavailable binding before requesting the run list', async () => {
  vi.mocked(api.getReplenishmentStatus).mockResolvedValue({ state: 'unavailable', reason_code: 'BINDING_UNAVAILABLE', latest: null })
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  expect(await screen.findByText(/Sản phẩm hoặc kho không còn phù hợp/)).toBeInTheDocument()
  expect(api.listReplenishmentRuns).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Nghiên cứu' })).toBeInTheDocument()
})
it('shows stale reason and hides research for warehouse', async () => {
  auth.role = 'warehouse'
  vi.mocked(api.getReplenishmentStatus).mockResolvedValue({ state: 'failed', reason_code: 'FORECAST_STALE', latest: null })
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  expect(await screen.findByText(/Dự báo không bao phủ khoảng thời gian/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Nghiên cứu' })).not.toBeInTheDocument()
  expect(api.listReplenishmentRuns).not.toHaveBeenCalled()
})
it('switches scope and labels retrospective research', async () => {
  vi.mocked(api.getReplenishmentStatus).mockResolvedValue({ state: 'unavailable', reason_code: 'NO_RUNS', latest: null })
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  await userEvent.click(screen.getByRole('button', { name: 'Nghiên cứu' }))
  expect(await screen.findByText(/nghiên cứu hồi cứu/i)).toBeInTheDocument()
  expect(api.getReplenishmentStatus).toHaveBeenLastCalledWith('token', 'research')
})

it('does not request the old scope list after the user switches scope', async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.getReplenishmentStatus>>) => void
  vi.mocked(api.getReplenishmentStatus).mockImplementation((_token, mode) => mode === 'operational'
    ? new Promise(resolve => { finish = resolve })
    : Promise.resolve({ state: 'unavailable', reason_code: 'NO_RUNS', latest: null }))
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  await userEvent.click(screen.getByRole('button', { name: 'Nghiên cứu' }))
  expect(await screen.findByText('Chưa có kết quả trong phạm vi này.')).toBeInTheDocument()
  await act(async () => { finish({ state: 'ready', reason_code: null, latest: null }) })
  expect(api.listReplenishmentRuns).not.toHaveBeenCalled()
})

it('lists verified ready runs with source and fixture labels', async () => {
  const run = { manifest: { run_id: 'rrv1-' + 'a'.repeat(64), data_version: 'ddv1-fixture', created_at: '2026-11-01T00:00:00Z' }, applicability: 'fixture_scenario', fixture_label: 'Dữ liệu kiểm thử' } as import('./types').ReplenishmentRun
  vi.mocked(api.getReplenishmentStatus).mockResolvedValue({ state: 'ready', reason_code: null, latest: run })
  vi.mocked(api.listReplenishmentRuns).mockResolvedValue({ items: [run], total: 1, page: 1, page_size: 20 })
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  expect(await screen.findByRole('link', { name: run.manifest.run_id })).toBeInTheDocument()
  expect(screen.getByText('Dữ liệu kiểm thử')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cuộn danh sách kết quả bổ sung hàng' })).toHaveAttribute('tabindex', '0')
  expect(api.listReplenishmentRuns).toHaveBeenCalledWith('token', 'operational', 1)
})

it('retries failed status without changing the session', async () => {
  vi.mocked(api.getReplenishmentStatus).mockResolvedValueOnce({ state: 'failed', reason_code: 'FORECAST_STALE', latest: null }).mockResolvedValueOnce({ state: 'unavailable', reason_code: 'NO_REVIEWED_POLICY_INPUTS', latest: null })
  render(<MemoryRouter><ReplenishmentPage /></MemoryRouter>)
  expect(await screen.findByText(/Dự báo không bao phủ/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText(/Chưa có dữ liệu được duyệt/)).toBeInTheDocument()
  expect(api.getReplenishmentStatus).toHaveBeenLastCalledWith('token', 'operational')
})
