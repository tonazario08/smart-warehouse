import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { AnomaliesPage } from './AnomaliesPage'
import * as api from './api'
const auth = vi.hoisted(() => ({ token: 'token' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: auth.token, user: { id: 1, role: 'admin' } }) }))
vi.mock('./api')
beforeEach(() => { vi.resetAllMocks(); auth.token = 'token' })
it('shows unavailable fixture state', async () => {
  vi.mocked(api.getStatus).mockResolvedValue({ state: 'unavailable', dataset_class: null, real_precision_recall: 'NOT VERIFIED' })
  render(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  expect(await screen.findByText('Chưa có cảnh báo khả dụng')).toBeInTheDocument()
})
it('shows a recoverable loading error', async () => {
  vi.mocked(api.getStatus).mockRejectedValue(new Error())
  render(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
})

it('does not show the previous identity response while a new session loads', async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.getStatus>>) => void
  const first = new Promise<Awaited<ReturnType<typeof api.getStatus>>>(resolve => { finish = resolve })
  vi.mocked(api.getStatus).mockReturnValueOnce(first).mockResolvedValueOnce({ state: 'unavailable', dataset_class: null, real_precision_recall: 'NOT VERIFIED' })
  auth.token = 'old'
  const view = render(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  auth.token = 'new'; view.rerender(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  expect(await screen.findByText('Chưa có cảnh báo khả dụng')).toBeInTheDocument()
  await act(async () => { finish({ state: 'available', dataset_class: 'fixture', real_precision_recall: 'NOT VERIFIED' }) })
  expect(api.getAlerts).not.toHaveBeenCalled()
})


it('discards the prior list when identity changes after status resolves', async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.getAlerts>>) => void
  vi.mocked(api.getStatus).mockResolvedValue({ state: 'available', dataset_class: 'fixture', real_precision_recall: 'NOT VERIFIED' })
  vi.mocked(api.getAlerts).mockReturnValueOnce(new Promise(resolve => { finish = resolve })).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })
  auth.token = 'old'
  const view = render(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  await waitFor(() => expect(api.getAlerts).toHaveBeenCalledTimes(1))
  auth.token = 'new'; view.rerender(<MemoryRouter><AnomaliesPage /></MemoryRouter>)
  await screen.findByText('Không có cảnh báo')
  await act(async () => finish({ items: [{ alert_id: 'old-secret', run_id: 'run', source_record_key: 'key', occurred_at: '2026-01-01T00:00:00Z', score: .8, threshold: .7, review_status: 'new', version: 1 }], total: 1, page: 1, page_size: 20 }))
  expect(screen.queryByText('old-secret')).not.toBeInTheDocument()
})
