import type { StockPageData } from '../inventory/types'
import type { Product } from '../products/types'
import type { Warehouse } from '../warehouses/types'
import type { ReplenishmentRun, SimulationDay } from './types'

export type ReplenishmentAlertSources = {
  stock: StockPageData
  product: Product
  warehouse: Warehouse
}

export type ReplenishmentAlert =
  | { status: 'research' }
  | { status: 'missing'; reason: string }
  | { status: 'reorder' | 'above'; day: string; onHand: number; rop: number; unit: string; sku: string; warehouseCode: string; eoq: number | null }

function isFixtureWarehouseRun(run: ReplenishmentRun): boolean {
  const { manifest } = run
  return manifest.mode === 'operational'
    && manifest.dataset_class === 'fixture'
    && manifest.reporting_scope === 'warehouse'
    && run.applicability === 'fixture_scenario'
}

export function getFixtureWarehouseBinding(run: ReplenishmentRun) {
  const { entity, manifest: { binding } } = run
  if (!isFixtureWarehouseRun(run) || !entity || !binding
    || !Number.isSafeInteger(binding.product_id) || binding.product_id <= 0
    || !Number.isSafeInteger(binding.warehouse_id) || binding.warehouse_id <= 0
    || entity.product_id !== binding.product_id || entity.warehouse_id !== binding.warehouse_id) {
    return null
  }
  return binding
}

// The inventory endpoint has no unit column; its quantity is interpreted using
// the verified catalogue product unit. Never infer or convert units.
export function evaluateReplenishmentAlert(
  run: ReplenishmentRun,
  days: SimulationDay[] | null,
  sources: ReplenishmentAlertSources | null,
): ReplenishmentAlert {
  if (run.manifest.mode === 'research' || run.applicability === 'research_scenario') {
    return { status: 'research' }
  }
  if (!isFixtureWarehouseRun(run)) {
    return { status: 'missing', reason: 'Kịch bản không phải fixture theo một kho cụ thể.' }
  }
  const { entity, manifest } = run
  const binding = getFixtureWarehouseBinding(run)
  if (!entity || !binding) {
    return { status: 'missing', reason: 'Chưa có liên kết sản phẩm và kho đáng tin cậy.' }
  }
  if (!sources) return { status: 'missing', reason: 'Chưa có dữ liệu tồn kho và danh mục để xác minh.' }
  const { stock, product, warehouse } = sources
  if (product.id !== binding.product_id || !product.sku || product.sku !== entity.sku) {
    return { status: 'missing', reason: 'SKU của danh mục không khớp kết quả mô phỏng.' }
  }
  if (warehouse.id !== binding.warehouse_id || !warehouse.code || warehouse.code !== entity.warehouse_code) {
    return { status: 'missing', reason: 'Kho của danh mục không khớp kết quả mô phỏng.' }
  }
  if (!product.unit || product.unit !== binding.unit || product.unit !== manifest.unit) {
    return { status: 'missing', reason: 'Đơn vị tính của dữ liệu không khớp.' }
  }
  // The API filters by both IDs, but verify the response as well. Multiple or
  // absent rows are ambiguous, not zero inventory.
  if (stock.total !== 1 || stock.items.length !== 1) {
    return { status: 'missing', reason: 'Không xác định được đúng một bản ghi tồn kho.' }
  }
  const row = stock.items[0]
  if (row.product_id !== binding.product_id || row.warehouse_id !== binding.warehouse_id) {
    return { status: 'missing', reason: 'SKU hoặc kho của bản ghi tồn không khớp.' }
  }
  if (!Number.isSafeInteger(row.quantity) || row.quantity < 0) {
    return { status: 'missing', reason: 'Số lượng tồn kho không hợp lệ.' }
  }
  // Use the first scored day on the CURRENT trace page; never use rop_min/max.
  const reference = days?.find(day => !day.warmup)
  if (!reference || !/^\d{4}-\d{2}-\d{2}$/.test(reference.day)
    || !Number.isSafeInteger(reference.reorder_point) || reference.reorder_point < 0) {
    return { status: 'missing', reason: 'Không có ROP hợp lệ cho ngày đánh giá trên trang hiện tại.' }
  }
  const eoq = run.calibration?.eoq
  const validEoq = eoq?.state === 'ready' && eoq.reason_code === null
    && Number.isSafeInteger(eoq.quantity) && (eoq.quantity ?? 0) > 0
    && eoq.raw !== null && eoq.raw !== undefined && eoq.raw.trim() !== ''
    && Number.isFinite(Number(eoq.raw)) && Number(eoq.raw) > 0
    ? eoq.quantity : null
  return {
    status: row.quantity <= reference.reorder_point ? 'reorder' : 'above',
    day: reference.day,
    onHand: row.quantity,
    rop: reference.reorder_point,
    unit: product.unit,
    sku: product.sku,
    warehouseCode: warehouse.code,
    eoq: validEoq ?? null,
  }
}
