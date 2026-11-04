import { ApiError, request } from '../../api'
import type { Page } from '../../types'
import type { Algorithm, Policy, ReplenishmentMode, ReplenishmentRun, ReplenishmentStatus, SimulationDay } from './types'

export const getReplenishmentStatus = (token: string, mode: ReplenishmentMode) => request<ReplenishmentStatus>('/replenishment/status?' + new URLSearchParams({ mode }), {}, token)
export const listReplenishmentRuns = (token: string, mode: ReplenishmentMode, page: number) => request<Page<ReplenishmentRun>>('/replenishment/runs?' + new URLSearchParams({ mode, page: String(page), page_size: '20' }), {}, token)
export const getReplenishmentRun = (token: string, id: string) => request<ReplenishmentRun>('/replenishment/runs/' + encodeURIComponent(id), {}, token)
export const getReplenishmentDays = (token: string, id: string, algorithm: Algorithm, leadTime: number, service: string, policy: Policy, page: number) => request<Page<SimulationDay>>('/replenishment/runs/' + encodeURIComponent(id) + '/days?' + new URLSearchParams({ algorithm, lead_time: String(leadTime), service, policy, page: String(page), page_size: '20' }), {}, token)
export function replenishmentReason(code: string | null): string {
  const messages: Record<string, string> = {
    NO_REVIEWED_POLICY_INPUTS: 'Chưa có dữ liệu được duyệt để tính chính sách bổ sung hàng.',
    NO_RUNS: 'Chưa có kết quả trong phạm vi này.',
    BINDING_UNAVAILABLE: 'Sản phẩm hoặc kho không còn phù hợp với kết quả này.',
    FORECAST_STALE: 'Dự báo không bao phủ khoảng thời gian được yêu cầu.',
    CALENDAR_UNAVAILABLE: 'Dữ liệu bị thiếu ngày trong khoảng thời gian cần đánh giá.',
    NO_EVALUATION_WINDOWS: 'Không có cửa sổ đánh giá hợp lệ.',
    UNSUPPORTED_INVENTORY_STATE: 'Thông tin tồn và hàng đang đến chưa đủ để tính.',
    INSUFFICIENT_CALIBRATION: 'Không đủ dữ liệu để hiệu chỉnh độ bất định.',
    ORDERING_COST_MISSING: 'Chưa có chi phí đặt hàng.', ORDERING_COST_ZERO: 'Chi phí đặt hàng bằng 0 không hỗ trợ EOQ.',
    HOLDING_COST_MISSING: 'Chưa có chi phí lưu kho.', HOLDING_COST_ZERO: 'Chi phí lưu kho bằng 0 không hỗ trợ EOQ.',
  }
  return code && messages[code] ? messages[code] : 'Kết quả chưa khả dụng. Vui lòng thử lại sau.'
}
export function replenishmentError(cause: unknown): string {
  const code = typeof cause === 'object' && cause !== null && 'code' in cause ? String(cause.code) : ''
  const messages: Record<string, string> = { REPLENISHMENT_FORBIDDEN: 'Bạn không có quyền xem kết quả này.', REPLENISHMENT_NOT_FOUND: 'Không tìm thấy kết quả bổ sung hàng.', REPLENISHMENT_BINDING_UNAVAILABLE: 'Sản phẩm hoặc kho không còn phù hợp với kết quả này.', REPLENISHMENT_SCHEMA_UNSUPPORTED: 'Kết quả có định dạng không tương thích.', REPLENISHMENT_ARTIFACT_INVALID: 'Kết quả không hợp lệ hoặc không còn khả dụng.', REPLENISHMENT_CATALOG_UNAVAILABLE: 'Danh mục bổ sung hàng hiện không khả dụng.' }
  if (messages[code]) return messages[code]
  if (cause instanceof ApiError && cause.status === 403) return 'Bạn không có quyền xem kết quả này.'
  if (cause instanceof ApiError && cause.status === 404) return 'Không tìm thấy kết quả bổ sung hàng.'
  return 'Không thể tải dữ liệu bổ sung hàng. Vui lòng thử lại.'
}
