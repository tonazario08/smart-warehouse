import { ApiError, request } from '../../api'
import type { Page } from '../../types'
import type { Algorithm, ForecastMode, ForecastRun, ForecastStatus, Prediction } from './types'

export const getForecastStatus = (token: string, mode: ForecastMode) => request<ForecastStatus>('/forecasts/status?' + new URLSearchParams({ mode }), {}, token)
export const listForecastRuns = (token: string, mode: ForecastMode, page: number) => request<Page<ForecastRun>>('/forecasts/runs?' + new URLSearchParams({ mode, page: String(page), page_size: '20' }), {}, token)
export const getForecastRun = (token: string, id: string) => request<ForecastRun>('/forecasts/runs/' + encodeURIComponent(id), {}, token)
export const getForecastPredictions = (token: string, id: string, horizon: number, algorithm: Algorithm, page: number) => request<Page<Prediction>>('/forecasts/runs/' + encodeURIComponent(id) + '/predictions?' + new URLSearchParams({ horizon: String(horizon), algorithm, page: String(page), page_size: '20' }), {}, token)
export function forecastError(cause: unknown): string {
  const code = typeof cause === 'object' && cause !== null && 'code' in cause ? String(cause.code) : ''
  const messages: Record<string, string> = { FORECAST_FORBIDDEN: 'Bạn không có quyền xem kết quả này.', FORECAST_NOT_FOUND: 'Không tìm thấy kết quả dự báo.', FORECAST_SCHEMA_UNSUPPORTED: 'Kết quả có định dạng không tương thích.', FORECAST_ARTIFACT_INVALID: 'Kết quả dự báo không hợp lệ hoặc không còn khả dụng.', FORECAST_CATALOG_UNAVAILABLE: 'Danh mục dự báo hiện không khả dụng.' }
  if (messages[code]) return messages[code]
  if (cause instanceof ApiError && cause.status === 403) return 'Bạn không có quyền xem kết quả này.'
  if (cause instanceof ApiError && cause.status === 404) return 'Không tìm thấy kết quả dự báo.'
  return 'Không thể tải dữ liệu dự báo. Vui lòng thử lại.'
}
