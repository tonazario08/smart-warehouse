import type { Detail } from './types'

const KEYS = [
  'log_quantity',
  'hour_fraction',
  'weekday_fraction',
  'log_prior_quantity_mean_7d',
  'log_prior_event_count_7d',
  'log_quantity_to_prior_mean',
] as const
type FeatureKey = typeof KEYS[number]
export const readableLabels: Record<FeatureKey, string> = {
  log_quantity: 'Lượng ghi trong dữ liệu mẫu',
  hour_fraction: 'Giờ trong ngày (UTC)',
  weekday_fraction: 'Thứ trong tuần (UTC)',
  log_prior_quantity_mean_7d: 'Lượng xuất trung bình mỗi ngày',
  log_prior_event_count_7d: 'Số giao dịch trong kỳ',
  log_quantity_to_prior_mean: 'Chỉ số so với lịch sử',
}
const vietnamTime = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})
const utcDay = new Intl.DateTimeFormat('vi-VN', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric' })
const utcWeekday = new Intl.DateTimeFormat('vi-VN', { timeZone: 'UTC', weekday: 'long' })
const decimal = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 8 })
const scientific = new Intl.NumberFormat('vi-VN', { notation: 'scientific', maximumSignificantDigits: 6 })
const DAY_MS = 86_400_000
const MAX_EVENT_QUANTITY = 2_147_483_647
const MAX_EVENTS = 10_000
const CLOSE_TOLERANCE = 1e-10

export function number(value: number) {
  return value !== 0 && Math.abs(value) < 1e-8 ? scientific.format(value) : decimal.format(value)
}
export function probability(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}
export function readScoreComparison(score: unknown, threshold: unknown) {
  if (!probability(score) || !probability(threshold)) return null
  const relation = score > threshold ? 'above' : score < threshold ? 'below' : 'equal'
  let scoreText = number(score)
  let thresholdText = number(threshold)
  if (relation !== 'equal' && scoreText === thresholdText) {
    for (let digits = 9; digits <= 20 && scoreText === thresholdText; digits++) {
      const precise = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: digits })
      scoreText = precise.format(score)
      thresholdText = precise.format(threshold)
    }
    if (scoreText === thresholdText) {
      // Round-trip representations cannot merge two distinct finite doubles.
      const roundTrip = (value: number) => value.toString().replace('.', ',').replace('e', 'E')
      scoreText = roundTrip(score)
      thresholdText = roundTrip(threshold)
    }
  }
  return {
    relation, scoreText, thresholdText,
    label: relation === 'above' ? 'Điểm cao hơn ngưỡng' : relation === 'below' ? 'Điểm thấp hơn ngưỡng' : 'Điểm bằng ngưỡng',
  } as const
}

function timestamp(value: unknown) {
  if (typeof value !== 'string' || !/T.*(?:Z|[+-]\d\d:\d\d)$/i.test(value)) return null
  const parsed = new Date(value)
  return Number.isFinite(parsed.getTime()) ? parsed : null
}
export function formatVietnamTime(value: string) {
  const date = timestamp(value)
  return date ? vietnamTime.format(date) : null
}
function decode(value: unknown, min: number, max: number, integer: boolean) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null
  const raw = Math.expm1(value)
  if (!Number.isFinite(raw)) return null
  // Allow only floating-point noise from expm1(log1p(x)), not a plausible adjacent amount.
  const tolerance = Math.max(1e-12, Math.abs(raw) * Number.EPSILON * 12)
  const recovered = integer ? Math.round(raw) : raw
  if (Math.abs(raw - recovered) > tolerance || recovered < min - tolerance || recovered > max + tolerance) return null
  return recovered
}

export function readFeatures(detail: Detail) {
  const date = timestamp(detail.occurred_at)
  const vector = detail.features
  const order = detail.feature_order
  const version = detail.run?.feature_version
  const publishedShape = version === 'anomaly-features/1'
    && Array.isArray(vector) && vector.length === KEYS.length
    && Array.isArray(order) && order.length === KEYS.length
    && KEYS.every((key, i) => order[i] === key)
  const value = (i: number) => publishedShape ? vector[i] : undefined
  const quantity = decode(value(0), 1, MAX_EVENT_QUANTITY, true)
  const mean = decode(value(3), 0, MAX_EVENT_QUANTITY * MAX_EVENTS / 7, false)
  const count = decode(value(4), 0, MAX_EVENTS, true)
  const ratio = decode(value(5), 0, MAX_EVENT_QUANTITY, false)
  const hourScale = value(1), weekdayScale = value(2)
  const hour = date && probability(hourScale) && Math.abs(hourScale - date.getUTCHours() / 23) <= CLOSE_TOLERANCE ? date.getUTCHours() : null
  const weekday = date && probability(weekdayScale) && Math.abs(weekdayScale - ((date.getUTCDay() + 6) % 7) / 6) <= CLOSE_TOLERANCE ? utcWeekday.format(date) : null
  const historyValid = mean !== null && count !== null && ((mean === 0) === (count === 0))
  const ratioExpected = quantity !== null && historyValid ? quantity / (1 + mean) : null
  const ratioValid = ratio !== null && ratioExpected !== null && Math.abs(ratio - ratioExpected) <= Math.max(1e-12, ratioExpected * CLOSE_TOLERANCE)
  const valid = quantity !== null && hour !== null && weekday !== null && historyValid && ratioValid
  return {
    valid, publishedShape, date, quantity, hour, weekday,
    history: date && historyValid ? { mean, count, dates: `${utcDay.format(date.getTime() - 7 * DAY_MS)} đến ${utcDay.format(date.getTime() - DAY_MS)} (UTC)` } : null,
    values: [
      quantity === null ? null : number(quantity),
      hour === null ? null : `${String(hour).padStart(2, '0')}:00–${String(hour).padStart(2, '0')}:59 UTC`,
      weekday,
      historyValid ? `${number(mean)} mỗi ngày` : null,
      historyValid ? `${number(count)} giao dịch` : null,
      ratioValid ? number(ratio) : null,
    ],
  }
}

export function attribution(detail: Detail, features: ReturnType<typeof readFeatures>) {
  const explanation = detail.explanation
  if (explanation?.state !== 'available' || explanation.reason !== null || !features.valid
      || detail.run?.model_version !== 'isolation-forest/1'
      || detail.run.score_definition !== '-IsolationForest.score_samples'
      || !probability(detail.score) || !probability(detail.threshold) || detail.score <= detail.threshold
      || !Array.isArray(explanation.contributions) || explanation.contributions.length !== KEYS.length
      || !explanation.contributions.every(Number.isFinite)
      || !Number.isFinite(explanation.base_value) || explanation.base_value === null
      || !Number.isFinite(explanation.residual) || explanation.residual === null || explanation.residual < 0) return null
  const residual = Math.abs(explanation.base_value + explanation.contributions.reduce((a, b) => a + b, 0) - detail.score)
  if (!Number.isFinite(residual) || residual > 1e-8 || Math.abs(residual - explanation.residual) > 1e-12) return null
  return KEYS.map((key, i) => ({ label: readableLabels[key], actual: features.values[i], amount: explanation.contributions![i], key }))
}
