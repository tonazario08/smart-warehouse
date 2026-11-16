import { describe, expect, it } from 'vitest'
import { evaluateReplenishmentAlert } from './alert'
import type { ReplenishmentAlertSources } from './alert'
import type { ReplenishmentRun, SimulationDay } from './types'

const makeRun = (): ReplenishmentRun => ({
  manifest: {
    run_id: 'rrv1-' + 'a'.repeat(64), mode: 'operational', dataset_class: 'fixture',
    reporting_scope: 'warehouse', binding: { product_id: 10, warehouse_id: 20, unit: 'unit' },
    unit: 'unit',
  },
  applicability: 'fixture_scenario',
  entity: { product_id: 10, warehouse_id: 20, sku: 'SKU-DEMO', product_name: 'Demo', warehouse_name: 'Warehouse', warehouse_code: 'WH-DEMO' },
  calibration: { eoq: { state: 'ready', quantity: 8, raw: '7.2', reason_code: null } },
} as ReplenishmentRun)

const makeSources = (quantity: number): ReplenishmentAlertSources => ({
  stock: { total: 1, page: 1, page_size: 2, items: [{ id: 5, product_id: 10, warehouse_id: 20, quantity, created_at: '2026-01-01T00:00:00Z' }] },
  product: { id: 10, sku: 'SKU-DEMO', unit: 'unit' },
  warehouse: { id: 20, code: 'WH-DEMO' },
} as ReplenishmentAlertSources)

const days = (rop: number): SimulationDay[] => [
  { day: '2026-01-01', warmup: true, reorder_point: 10000 },
  { day: '2026-01-02', warmup: false, reorder_point: rop },
] as SimulationDay[]

describe('fixture replenishment alert (read-only)', () => {
  it('suggests a review when stock touches ROP, using only the scored day', () => {
    expect(evaluateReplenishmentAlert(makeRun(), days(5), makeSources(5))).toMatchObject({
      status: 'reorder', day: '2026-01-02', onHand: 5, rop: 5, eoq: 8,
    })
  })
  it('suggests a review below ROP', () => {
    expect(evaluateReplenishmentAlert(makeRun(), days(5), makeSources(4)).status).toBe('reorder')
  })
  it('does not suggest replenishment above ROP', () => {
    expect(evaluateReplenishmentAlert(makeRun(), days(5), makeSources(6)).status).toBe('above')
  })
  it('does not treat an absent stock row as zero', () => {
    const input = makeSources(0)
    input.stock.items = []
    input.stock.total = 0
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
  })
  it('rejects missing and warmup-only ROP', () => {
    expect(evaluateReplenishmentAlert(makeRun(), null, makeSources(0)).status).toBe('missing')
    expect(evaluateReplenishmentAlert(makeRun(), [days(5)[0]], makeSources(0)).status).toBe('missing')
  })
  it('rejects invalid stock and ROP values', () => {
    expect(evaluateReplenishmentAlert(makeRun(), days(5), makeSources(Number.NaN)).status).toBe('missing')
    expect(evaluateReplenishmentAlert(makeRun(), days(-1), makeSources(0)).status).toBe('missing')
  })
  it('rejects mismatched SKU even when IDs match', () => {
    const input = makeSources(0)
    input.product.sku = 'OTHER-SKU'
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
  })
  it('rejects mismatched warehouse ID or code', () => {
    const input = makeSources(0)
    input.stock.items[0].warehouse_id = 21
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
    input.stock.items[0].warehouse_id = 20
    input.warehouse.code = 'OTHER-WH'
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
  })
  it('rejects mismatched stock product ID even when API was filtered', () => {
    const input = makeSources(0)
    input.stock.items[0].product_id = 11
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
  })
  it('rejects unit mismatch and incomplete fixture binding', () => {
    const input = makeSources(0)
    input.product.unit = 'kg'
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
    const run = makeRun()
    run.manifest.binding = null
    expect(evaluateReplenishmentAlert(run, days(5), makeSources(0)).status).toBe('missing')
  })
  it('rejects ambiguous multiple stock snapshots', () => {
    const input = makeSources(0)
    input.stock.total = 2
    expect(evaluateReplenishmentAlert(makeRun(), days(5), input).status).toBe('missing')
  })
  it('never compares research results to a warehouse snapshot', () => {
    const run = makeRun()
    run.manifest.mode = 'research'
    expect(evaluateReplenishmentAlert(run, days(5), makeSources(0)).status).toBe('research')
  })
  it('hides order quantity unless EOQ is strictly valid', () => {
    const run = makeRun()
    for (const eoq of [
      { state: 'ready' as const, quantity: 0, raw: '0', reason_code: 'ZERO_DEMAND' },
      { state: 'unavailable' as const, quantity: null, raw: null, reason_code: 'ORDERING_COST_MISSING' },
      { state: 'ready' as const, quantity: 2.5, raw: '2.1', reason_code: null },
      { state: 'ready' as const, quantity: 8, raw: 'NaN', reason_code: null },
    ]) {
      run.calibration!.eoq = eoq
      expect(evaluateReplenishmentAlert(run, days(5), makeSources(1))).toMatchObject({ status: 'reorder', eoq: null })
    }
  })
  it('uses the selected trace page rather than a previous page ROP', () => {
    const run = makeRun()
    const stock = makeSources(6)
    expect(evaluateReplenishmentAlert(run, days(5), stock).status).toBe('above')
    expect(evaluateReplenishmentAlert(run, days(7), stock).status).toBe('reorder')
  })
})
