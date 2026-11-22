import type { ForecastRun } from './types'

export function forecastSourceLabel(run: ForecastRun) {
  if (run.manifest.dataset_class === 'fixture' || run.fixture_label) return 'Mô phỏng kiểm thử'
  if (run.manifest.dataset_class === 'research' || run.applicability === 'retrospective') return 'Nghiên cứu hồi cứu'
  return 'Vận hành'
}
