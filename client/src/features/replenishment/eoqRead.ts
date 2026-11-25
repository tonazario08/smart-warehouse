import type { ReplenishmentRun } from './types'

function positiveDecimal(value: unknown): boolean {
  if (typeof value !== 'string' || !/^\+?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())) return false
  const number = Number(value)
  return Number.isFinite(number) && number > 0
}

// Display-only gate for values already calculated by the admitted scenario.
export function validatedEoq(run: ReplenishmentRun): number | null {
  const costs = run.manifest.config?.costs
  const eoq = run.calibration?.eoq
  return costs?.currency === 'VND' && costs.holding_period === 'year'
    && positiveDecimal(costs.ordering_cost) && positiveDecimal(costs.holding_cost)
    && eoq?.state === 'ready' && eoq.reason_code === null && positiveDecimal(eoq.raw)
    && typeof eoq.quantity === 'number' && Number.isSafeInteger(eoq.quantity) && eoq.quantity > 0
    ? eoq.quantity : null
}
