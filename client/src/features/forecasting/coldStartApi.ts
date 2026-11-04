import { ApiError, request } from '../../api'

export type ColdStartStatus = {
  state: 'ready' | 'unavailable' | 'failed' | 'stale'
  reason_code: string | null
  latest_run_id: string | null
  operational_state: 'unavailable'
}
export type ColdStartMetric = {
  samples: number; predicted: number; baseline_predicted: number; actual: number; compared: number
  excluded_prediction: number; excluded_baseline: number; excluded_actual: number; excluded_comparison: number
  actual_sum: number; category_count: number; mae: number | null; baseline_mae: number | null
  wape: number | null; baseline_wape: number | null
}
export type ColdStartSample = {
  origin: string; horizon: 1 | 7; prediction: number | null; baseline: number | null
  reference_count: number; confidence: 'cluster' | 'category' | 'all_train' | 'unavailable'
  reason: 'insufficient_metadata' | 'insufficient_references' | null
}
export type ColdStartRun = {
  run_id: string; stale: boolean
  report: {
    schema_version: 'cold-start-public/1'; fixture_label: 'Dữ liệu kiểm thử'; operational_state: 'unavailable'
    target: 'gross_fulfilled_units'; unit: string; scope: 'single-warehouse-fixture'
    created_at: string; train_cutoff: string; validation_cutoff: string; holdout_end: string
    data_versions: readonly string[]; reference_population: number; selected_k: number
    selection_reason: 'validation_common_horizon_7_mae' | 'no_common_validation_samples'
    metrics: Record<'1' | '7', ColdStartMetric>; samples: readonly ColdStartSample[]; limitations: readonly string[]
  }
}
export const getColdStartStatus = (token: string) => request<ColdStartStatus>('/forecasts/cold-start/status', {}, token)
export const getColdStartRun = (token: string, id: string) => request<ColdStartRun>('/forecasts/cold-start/runs/' + encodeURIComponent(id), {}, token)
export function coldStartError(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 403) return 'Bạn không có quyền xem báo cáo này.'
  if (cause instanceof ApiError && cause.status === 404) return 'Không tìm thấy báo cáo. Vui lòng tải lại.'
  if (cause instanceof ApiError && cause.status === 409) return 'Báo cáo không hợp lệ. Vui lòng thử lại sau.'
  return 'Không thể tải báo cáo. Vui lòng thử lại.'
}
