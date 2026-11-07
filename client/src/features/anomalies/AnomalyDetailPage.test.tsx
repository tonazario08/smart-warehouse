import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { AnomalyDetailPage } from './AnomalyDetailPage'
import * as api from './api'
import type { Detail, ReviewResult } from './types'
const auth = vi.hoisted(() => ({ token: 'token', id: 1, role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: auth.token, user: { id: auth.id, role: auth.role } }) }))
vi.mock('./api')
const detail: Detail = { alert_id: 'alert', run_id: 'run', source_record_key: 'source', occurred_at: '2026-01-10T12:00:00Z', score: .7, threshold: .6, review_status: 'new', version: 1, features: [1,2,3,4,5,6], feature_order: ['log_quantity', 'hour_fraction', 'weekday_fraction', 'log_prior_quantity_mean_7d', 'log_prior_event_count_7d', 'log_quantity_to_prior_mean'], explanation: { state: 'available', reason: null, base_value: .6, contributions: [.1,0,0,0,0,0], residual: 0 }, run: { input_version: 'input', feature_version: 'feature', model_version: 'model', created_at: '2026-01-10T12:00:00Z', partitions: [], score_definition: '-IsolationForest.score_samples', dataset_class: 'fixture', real_precision_recall: 'NOT VERIFIED' } }
const result: ReviewResult = { alert_id: 'alert', status: 'confirmed', version: 2, review_id: 'review', replayed: false }
const view = () => <MemoryRouter initialEntries={['/anomalies/alert']}><Routes><Route path="/anomalies/:alertId" element={<AnomalyDetailPage />} /></Routes></MemoryRouter>
beforeEach(() => { vi.resetAllMocks(); auth.token = 'token'; auth.id = 1; auth.role = 'admin'; vi.mocked(api.getAlert).mockResolvedValue(detail); vi.mocked(api.getReviews).mockResolvedValue({ items: [] }) })
it('shows a recoverable error if the alert cannot be loaded', async () => {
  vi.mocked(api.getAlert).mockRejectedValue(new Error())
  render(view())
  expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
})
it('shows signed attribution and explicit fixture limitation', async () => {
  render(view())
  expect(await screen.findByText(/Số lượng xuất \(log\): \+0,1/)).toBeInTheDocument()
  expect(screen.getByText(/không chứng minh quan hệ nhân quả/)).toBeInTheDocument()
})
it('retries the same payload with the same key and changes key for edited payload', async () => {
  vi.mocked(api.submitReview).mockRejectedValue(new Error('network'))
  render(view()); await screen.findByText('Thông tin cảnh báo')
  await userEvent.type(screen.getByLabelText('Ghi chú'), 'Kiểm tra')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
  await screen.findByText(/Chưa thể lưu đánh giá/)
  await userEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
  await waitFor(() => expect(api.submitReview).toHaveBeenCalledTimes(2))
  const calls = vi.mocked(api.submitReview).mock.calls
  expect(calls[0][2]).toBe(calls[1][2]); expect(calls[0][3]).toEqual(calls[1][3])
  await userEvent.type(screen.getByLabelText('Ghi chú'), ' thêm')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
  await waitFor(() => expect(api.submitReview).toHaveBeenCalledTimes(3))
  expect(vi.mocked(api.submitReview).mock.calls[2][2]).not.toBe(calls[0][2])
})
it('retains note on version conflict and refreshes when asked', async () => {
  vi.mocked(api.submitReview).mockRejectedValue(new ApiError('conflict', 409))
  render(view()); await screen.findByText('Thông tin cảnh báo')
  await userEvent.type(screen.getByLabelText('Ghi chú'), 'Cần kiểm tra')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
  await screen.findByText(/Trạng thái đã thay đổi/)
  await userEvent.click(screen.getByRole('button', { name: 'Tải lại trạng thái' }))
  await screen.findByText('Thông tin cảnh báo')
  expect(screen.getByLabelText('Ghi chú')).toHaveValue('Cần kiểm tra')
})
it('ignores a pending review response after identity changes', async () => {
  let finish!: (value: ReviewResult) => void
  vi.mocked(api.submitReview).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const mounted = render(view()); await screen.findByText('Thông tin cảnh báo')
  await userEvent.type(screen.getByLabelText('Ghi chú'), 'Cần kiểm tra')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
  expect(screen.getByRole('button', { name: 'Đang xử lý...' })).toBeDisabled()
  auth.token = 'new'; auth.id = 2; mounted.rerender(view())
  await screen.findByText('Thông tin cảnh báo')
  await act(async () => finish(result))
  expect(screen.queryByText('Đã lưu đánh giá.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Ghi chú')).toHaveValue('')
})

it('discards a delayed history response after identity changes', async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.getReviews>>) => void
  vi.mocked(api.getReviews).mockReturnValueOnce(new Promise(resolve => { finish = resolve })).mockResolvedValueOnce({ items: [] })
  const mounted = render(view())
  await waitFor(() => expect(api.getReviews).toHaveBeenCalledTimes(1))
  auth.role = 'warehouse'; mounted.rerender(view())
  await screen.findByText('Thông tin cảnh báo')
  await act(async () => finish({ items: [{ review_id: 'old', actor_user_id: 4, decision: 'confirmed', note: 'ghi chú phiên cũ', created_at: '2026-01-10T12:00:00Z', version: 2 }] }))
  expect(screen.queryByText(/ghi chú phiên cũ/)).not.toBeInTheDocument()
})
it('shows unavailable explanation without fabricated contributions', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, explanation: { state: 'unavailable', reason: 'EXPLAINER_ERROR', base_value: null, contributions: null, residual: null } })
  render(view())
  expect(await screen.findByText(/Không thể tính giải thích/)).toBeInTheDocument()
  expect(screen.queryByText(/Số lượng xuất \(log\):/)).not.toBeInTheDocument()
})
