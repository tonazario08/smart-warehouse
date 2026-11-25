import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { readScoreComparison } from './alertReadability'
import { AnomalyDetailPage } from './AnomalyDetailPage'
import * as api from './api'
import type { Detail, ReviewResult } from './types'
const auth = vi.hoisted(() => ({ token: 'token', id: 1, role: 'admin' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: auth.token, user: { id: auth.id, role: auth.role } }) }))
vi.mock('./api')
const detail: Detail = { alert_id: 'alert', run_id: 'run', source_record_key: 'source', occurred_at: '2026-01-16T23:00:00Z', score: .7, threshold: .6, review_status: 'new', version: 1, features: [Math.log1p(12), 1, 4 / 6, Math.log1p(3), Math.log1p(2), Math.log1p(3)], feature_order: ['log_quantity', 'hour_fraction', 'weekday_fraction', 'log_prior_quantity_mean_7d', 'log_prior_event_count_7d', 'log_quantity_to_prior_mean'], explanation: { state: 'available', reason: null, base_value: .6, contributions: [.1,0,0,0,0,0], residual: 0 }, run: { input_version: 'input', feature_version: 'anomaly-features/1', model_version: 'isolation-forest/1', created_at: '2026-01-10T12:00:00Z', partitions: [], score_definition: '-IsolationForest.score_samples', dataset_class: 'fixture', real_precision_recall: 'NOT VERIFIED' } }
const result: ReviewResult = { alert_id: 'alert', status: 'confirmed', version: 2, review_id: 'review', replayed: false }
const view = () => <MemoryRouter initialEntries={['/anomalies/alert']}><Routes><Route path="/anomalies/:alertId" element={<AnomalyDetailPage />} /></Routes></MemoryRouter>
beforeEach(() => { vi.resetAllMocks(); auth.token = 'token'; auth.id = 1; auth.role = 'admin'; vi.mocked(api.getAlert).mockResolvedValue(detail); vi.mocked(api.getAlertOutbound).mockRejectedValue(new ApiError('unlinked', 404)); vi.mocked(api.getReviews).mockResolvedValue({ items: [] }) })
async function openTechnical() {
  const summary = await screen.findByText('Thông tin kỹ thuật')
  const technical = summary.closest('details')!
  expect(technical).not.toHaveAttribute('open')
  await userEvent.click(summary)
  expect(technical).toHaveAttribute('open')
  return technical
}
it('shows a recoverable error if the alert cannot be loaded', async () => {
  vi.mocked(api.getAlert).mockRejectedValue(new Error())
  render(view())
  expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
})
it('shows signed attribution and explicit fixture limitation', async () => {
  render(view())
  const technical = await openTechnical()
  const chart = within(technical).getByRole('list', { name: 'Mức đóng góp SHAP' })
  expect(within(chart).getAllByRole('listitem')[0]).toHaveTextContent(/Lượng ghi trong dữ liệu mẫu.*\+0,1/)
  expect(within(chart).getAllByRole('listitem')[0]).toHaveTextContent('12')
  expect(within(technical).getByText(/Giá trị nền: 0,6/)).toBeVisible()
  expect(screen.getByText(/không chứng minh quan hệ nhân quả/)).toBeInTheDocument()
})
it('uses equal scale for signed bars and keeps zero and small contributions readable', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({
    ...detail,
    explanation: { ...detail.explanation, base_value: .6500000001, contributions: [0.1, -0.1, 0, 0.05, -1e-10, 0] },
  })
  render(view())
  const chart = within(await openTechnical()).getByRole('list', { name: 'Mức đóng góp SHAP' })
  const [positive, negative, zero, half, small] = within(chart).getAllByRole('listitem')
  expect(positive.querySelector('[data-direction="increase"]')).toHaveStyle({ width: '50%' })
  expect(negative.querySelector('[data-direction="decrease"]')).toHaveStyle({ width: '50%' })
  expect(half.querySelector('[data-direction="increase"]')).toHaveStyle({ width: '25%' })
  expect(zero.querySelector('[data-direction]')).toBeNull()
  expect(within(zero).getByText('0', { exact: true })).toBeInTheDocument()
  expect(within(negative).getByText('-0,1', { exact: true })).toBeInTheDocument()
  expect(within(small).getByText('-1E-10', { exact: true })).toBeInTheDocument()
})
it.each([
  { name: 'missing entries', contributions: [0.1] },
  { name: 'nonfinite entries', contributions: [0.1, Infinity, 0, 0, 0, 0] },
])('omits a chart with $name', async ({ contributions }) => {
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, explanation: { ...detail.explanation, contributions } })
  render(view())
  await openTechnical()
  expect(await screen.findByText('Dữ liệu SHAP không đầy đủ hoặc không hợp lệ.')).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Mức đóng góp SHAP' })).not.toBeInTheDocument()
})
it.each(['__proto__', 'hour_fraction', ''])('rejects an invalid feature key %j without losing the alert', async (name) => {
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, feature_order: [name, ...detail.feature_order.slice(1)] })
  render(view())
  await openTechnical()
  expect(await screen.findByText('Dữ liệu SHAP không đầy đủ hoặc không hợp lệ.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Thông tin cảnh báo' })).toBeVisible()
})
it('uses a readable fallback for an unknown explanation reason', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({
    ...detail,
    explanation: { state: 'unavailable', reason: '__proto__', base_value: null, residual: null, contributions: null },
  })
  render(view())
  await openTechnical()
  expect(await screen.findByText('Chưa có giải thích. Không thể tính giải thích.')).toBeInTheDocument()
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
  await openTechnical()
  expect(await screen.findByText(/Không thể tính giải thích/)).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Mức đóng góp SHAP' })).not.toBeInTheDocument()
  expect(screen.queryByText(/Số lượng xuất \(log\):/)).not.toBeInTheDocument()
})

it('explains the model and distinguishes Vietnam time from seven full UTC days', async () => {
  render(view())
  expect(await screen.findByRole('heading', { name: 'Vì sao có cảnh báo?' })).toBeVisible()
  expect(screen.getByText(/không phải xác suất giao dịch sai/)).toBeVisible()
  expect(screen.getByText(/Giờ Việt Nam \(UTC\+07:00\)/)).toBeVisible()
  expect(screen.getByText(/bảy ngày UTC trọn vẹn/i)).toBeVisible()
  expect(screen.getByText(/06:00.*17\/01\/2026.*Giờ Việt Nam/)).toBeVisible()
  expect(screen.getByText(/23:00–23:59 UTC, Thứ Sáu/)).toBeVisible()
  expect(screen.getByText('09/01/2026 đến 15/01/2026 (UTC)')).toBeVisible()
  const facts = screen.getByRole('heading', { name: 'Số liệu để đối chiếu' }).closest('section')!
  expect(within(facts).getByText('12', { exact: true })).toBeVisible()
  expect(within(facts).getByText('3', { exact: true })).toBeVisible()
  expect(within(facts).getByText('2', { exact: true })).toBeVisible()
  expect(screen.getByText(/Đối chiếu số lượng ghi nhận với chứng từ xuất/)).toBeVisible()
})

it('does not claim that a point equal to threshold exceeds it', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, score: detail.threshold })
  render(view())
  expect(await screen.findByText(/Dữ liệu điểm và ngưỡng không nhất quán/)).toBeVisible()
  expect(screen.getByText('Điểm bằng ngưỡng')).toBeVisible()
  await openTechnical()
  expect(screen.queryByRole('list', { name: 'Mức đóng góp SHAP' })).not.toBeInTheDocument()
})


it('preserves strict comparison even when displayed scores round to the same value', async () => {
  const threshold = .5923
  const score = threshold + 1e-10
  vi.mocked(api.getAlert).mockResolvedValue({
    ...detail, threshold, score,
    explanation: { ...detail.explanation, base_value: threshold, contributions: [score - threshold, 0, 0, 0, 0, 0] },
  })
  render(view())
  expect(await screen.findByText(/Điểm vượt ngưỡng.*E-10/)).toBeVisible()
  expect(screen.getByText('0,5923000001', { exact: true })).toBeVisible()
  expect(screen.getByText('0,5923', { exact: true })).toBeVisible()
})

it('reports a below-threshold fixture display without validating it as a real warning', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, score: 0.591999999, threshold: 0.592 })
  render(view())
  expect(await screen.findByText('Điểm thấp hơn ngưỡng')).toBeVisible()
  expect(screen.getByText('0,591999999', { exact: true })).toBeVisible()
  expect(screen.getByText(/Không thể xác nhận cảnh báo vượt ngưỡng/)).toBeVisible()
})
it('separates adjacent tiny values and fails closed on nonfinite or absent inputs', () => {
  const threshold = 1e-100
  const score = threshold * (1 + Number.EPSILON)
  const comparison = readScoreComparison(score, threshold)
  expect(comparison).toMatchObject({ relation: 'above' })
  expect(comparison?.scoreText).not.toBe(comparison?.thresholdText)
  expect(readScoreComparison(Infinity, threshold)).toBeNull()
  expect(readScoreComparison(null, threshold)).toBeNull()
})
it('does not misread zero history as missing data', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({
    ...detail, features: [Math.log1p(12), 1, 4/6, 0, 0, Math.log1p(12)],
  })
  render(view())
  const facts = (await screen.findByRole('heading', { name: 'Số liệu để đối chiếu' })).closest('section')!
  expect(within(facts).getAllByText('0', { exact: true })).toHaveLength(2)
  expect(within(facts).queryByText('Không đủ dữ liệu lịch sử')).not.toBeInTheDocument()
})

it.each([
  (data: Detail) => ({ ...data, features: [data.features[0]] }),
  (data: Detail) => ({ ...data, features: data.features.map((v, i) => i === 3 ? Infinity : v) }),
  (data: Detail) => ({ ...data, run: { ...data.run, feature_version: 'future' } }),
])('reports unavailable history rather than making up zero', async (change) => {
  vi.mocked(api.getAlert).mockResolvedValue(change(detail))
  render(view())
  expect(await screen.findByText('Không đủ dữ liệu lịch sử')).toBeVisible()
  expect(screen.queryByRole('list', { name: 'Mức đóng góp SHAP' })).not.toBeInTheDocument()
})

it.each([
  (data: Detail) => ({ ...data, explanation: { ...data.explanation, residual: 1e-3 } }),
  (data: Detail) => ({ ...data, run: { ...data.run, model_version: 'other-model/1' } }),
  (data: Detail) => ({ ...data, features: data.features.map((v, i) => i === 1 ? 0 : v) }),
])('does not invent a driver when score/explanation/time metadata is inconsistent', async (change) => {
  vi.mocked(api.getAlert).mockResolvedValue(change(detail))
  render(view())
  expect(await screen.findByText('Chưa có giải thích đáng tin để nêu yếu tố làm tăng điểm.')).toBeVisible()
  expect(screen.queryByRole('list', { name: 'Mức đóng góp SHAP' })).not.toBeInTheDocument()
})

it('keeps full IDs copyable and reports completion or rejection accurately', async () => {
  const user = userEvent.setup()
  const id = 'alv1-' + '5'.repeat(64)
  const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('denied'))
  vi.mocked(api.getAlert).mockResolvedValue({ ...detail, alert_id: id })
  render(view())
  const disclosure = (await screen.findByText('Thông tin kỹ thuật')).closest('details')!
  expect(disclosure).not.toHaveAttribute('open')
  const summary = within(disclosure).getByText('Thông tin kỹ thuật')
  summary.focus()
  expect(summary).toHaveFocus()
  // JSDOM supports native disclosure clicks, but not its keyboard default action.
  await user.click(summary)
  expect(disclosure).toHaveAttribute('open')
  const copy = within(disclosure).getByRole('button', { name: 'Sao chép mã cảnh báo' })
  expect(within(disclosure).queryByText(id)).not.toBeInTheDocument()
  expect(within(disclosure).getByText(/alv1-5555555…55555555/)).toBeVisible()
  await user.click(copy)
  expect(write).toHaveBeenLastCalledWith(id)
  expect(await within(disclosure).findByText('Đã sao chép mã đầy đủ.')).toBeVisible()
  await user.click(copy)
  expect(await within(disclosure).findByText('Không sao chép được mã.')).toBeVisible()
  expect(within(disclosure).queryByText('Đã sao chép mã đầy đủ.')).not.toBeInTheDocument()
})

it('preserves who evaluated, when, and their reason for a warehouse user', async () => {
  auth.role = 'warehouse'
  vi.mocked(api.getReviews).mockResolvedValue({ items: [{
    review_id: 'review', actor_user_id: 17, decision: 'confirmed', note: 'Đối chiếu chứng từ',
    created_at: '2026-01-16T23:00:00Z', version: 2,
  }] })
  render(view())
  expect(await screen.findByText(/bởi người dùng 17 lúc.*06:00.*Lý do: Đối chiếu chứng từ/)).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Đánh giá cảnh báo' })).toBeVisible()
})

it('does not reveal alert and review controls to a denied client', async () => {
  auth.role = 'client'
  vi.mocked(api.getAlert).mockRejectedValue(new ApiError('forbidden', 403))
  vi.mocked(api.getReviews).mockRejectedValue(new ApiError('forbidden', 403))
  render(view())
  expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Đánh giá cảnh báo' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Thông tin cảnh báo' })).not.toBeInTheDocument()
})

it('keeps the general check guidance when valid SHAP has no positive driver', async () => {
  vi.mocked(api.getAlert).mockResolvedValue({
    ...detail,
    explanation: { ...detail.explanation, base_value: .8, contributions: [-.1, 0, 0, 0, 0, 0] },
  })
  render(view())
  expect(await screen.findByText('Không có yếu tố làm tăng điểm trong phần giải thích.')).toBeVisible()
  expect(screen.queryByText(/Yếu tố làm tăng điểm nhiều nhất theo mô hình/)).not.toBeInTheDocument()
  expect(screen.getByText(/Đối chiếu thông tin giao dịch với chứng từ xuất/)).toBeVisible()
  expect(within(await openTechnical()).getByRole('list', { name: 'Mức đóng góp SHAP' })).toBeVisible()
})

it('shows the verified outbound link by alert ID, not the numeric voucher ID', async () => {
  const getAlertOutbound = vi.mocked(api.getAlertOutbound).mockResolvedValue({
    outbound_id: 451, product_name: 'Sản phẩm mẫu', product_sku: 'SKU-A',
    warehouse_code: 'KHO-A', warehouse_name: 'Kho A',
    quantity: 10000, unit: 'each', occurred_at: '2026-01-16T23:00:00Z', performed_by_id: 17,
  })
  render(view())
  const linked = await screen.findByRole('link', { name: 'Mở phiếu xuất #451' })
  expect(linked).toHaveAttribute('href', '/anomalies/alert/outbound')
  const technical = screen.getByText('Thông tin kỹ thuật')
  expect(linked.compareDocumentPosition(technical) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(technical.closest('details')).not.toHaveAttribute('open')
  expect(getAlertOutbound).toHaveBeenCalledWith('token', 'alert')
})

it('shows no voucher link when the existing fixture is generic', async () => {
  render(view())
  expect(await screen.findByText('Chưa liên kết được phiếu xuất đối chiếu.')).toBeVisible()
  expect(screen.queryByRole('link', { name: /Mở phiếu xuất/ })).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Thông tin cảnh báo' })).toBeVisible()
})
