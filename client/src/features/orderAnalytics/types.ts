export type AnalyticsState = 'computing' | 'available' | 'insufficient_data' | 'failed'
export type AnalyticsTarget = { warehouse_id: number; product_id: number }
export type AnalyticsStatus = { state: AnalyticsState; reason_code: string | null; computed_at: string | null }
export type OpenDemand = AnalyticsTarget & AnalyticsStatus & {
  sku: string
  unit: string
  forecast_run_id: string | null
  forecast_dataset_class: string | null
  forecast_stale: boolean | null
  pending_quantity: number | null
  approved_quantity: number | null
  open_quantity: number | null
  order_count: number | null
}
export type ReplenishmentPosition = AnalyticsTarget & AnalyticsStatus & {
  sku: string
  unit: string
  on_hand: number | null
  open_quantity: number | null
  projected_quantity: number | null
  rop: number | null
  rop_date: string | null
  eoq: number | null
  recommendation: boolean
  dataset_class: string | null
  run_id: string | null
}
export type OrderCheck = AnalyticsTarget & AnalyticsStatus & {
  purchase_request_id: number
  flagged: boolean | null
  rule_id: string | null
  rule_version: number | null
  sample_count: number | null
  median: number | null
  mad: number | null
  score: number | null
  label: string | null
}
export type SimulationSelection = {
  algorithm: string
  lead_time: number
  service: string
  policy: string
  reference_date?: string
  run_id?: string
}

export function analyticsTarget(value: Record<string, unknown> | null | undefined): AnalyticsTarget | null {
  const product_id = value?.product_id, warehouse_id = value?.warehouse_id
  return typeof product_id === 'number' && Number.isSafeInteger(product_id) && product_id > 0
    && typeof warehouse_id === 'number' && Number.isSafeInteger(warehouse_id) && warehouse_id > 0
    ? { product_id, warehouse_id } : null
}
