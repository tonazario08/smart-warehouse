import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildInventoryRows, filterInventoryRows, getStockScale } from '../src/shared/lib/inventory'
import { buildDashboardOverview } from '../src/shared/lib/dashboard'

const products = [
  { id: 1, sku: 'SP-1', name: 'Máy quét', description: null, category_id: 10, supplier_id: null, unit: 'cái', reorder_level: 5, is_active: true },
  { id: 2, sku: 'SP-2', name: 'Thùng carton', description: null, category_id: 20, supplier_id: null, unit: 'thùng', reorder_level: 0, is_active: true },
]
const warehouses = [
  { id: 1, code: 'WH-1', name: 'Kho chung', address: 'Hà Nội', latitude: null, longitude: null },
  { id: 2, code: 'WH-2', name: 'Kho chung', address: 'Đà Nẵng', latitude: null, longitude: null },
]
const stocks = [
  { id: 1, warehouse_id: 1, product_id: 1, quantity: 0 },
  { id: 2, warehouse_id: 1, product_id: 2, quantity: 0 },
  { id: 3, warehouse_id: 2, product_id: 1, quantity: 5 },
  { id: 4, warehouse_id: 2, product_id: 2, quantity: 15 },
]

test('zero stock is distinct from low stock, including a zero reorder threshold', () => {
  const rows = buildInventoryRows({ products, warehouses, stocks })
  assert.deepEqual(rows.map(row => row.status), ['out', 'out', 'low', 'healthy'])
})

test('inventory combines status, warehouse, category and search filters', () => {
  const rows = buildInventoryRows({ products, warehouses, stocks })
  assert.deepEqual(filterInventoryRows(rows, { search: 'máy', warehouseId: 1, status: 'out' }).map(row => row.id), [1])
  assert.deepEqual(filterInventoryRows(rows, { search: '', warehouseId: null, categoryProductIds: new Set([2]), status: 'healthy' }).map(row => row.id), [4])
  assert.deepEqual(filterInventoryRows(rows, { search: '', warehouseId: null, categoryProductIds: new Set() }).map(row => row.id), [])
})

test('dashboard warehouse totals are joined by IDs even when names are identical', () => {
  const overview = buildDashboardOverview({ products, warehouses, stock: stocks, transactions: [], stats: { product_count: 2, total_stock: 20, low_stock_count: 3 } })
  assert.deepEqual(overview.warehouseRows.map(row => row.totalStock), [0, 20])
  assert.equal(overview.lowStockRows.length, 3)
  assert.equal(overview.lowStockRows[0].status, 'out')
})

test('stock scale exposes an independent minimum marker without invented capacity', () => {
  assert.deepEqual(getStockScale(0, 50), { maximum: 100, currentPercent: 0, minimumPercent: 50 })
  assert.deepEqual(getStockScale(50, 50), { maximum: 100, currentPercent: 50, minimumPercent: 50 })
  assert.deepEqual(getStockScale(0, 0), { maximum: 1, currentPercent: 0, minimumPercent: 0 })
  const scale = getStockScale(324, 50)
  assert.equal(scale.maximum, 405)
  assert.equal(scale.currentPercent, 80)
  assert.ok(scale.minimumPercent > 12 && scale.minimumPercent < 13)
})

test('recent inbound and outbound panels do not lose a type behind the global transaction limit', () => {
  const transactions = [
    { id: 1, transaction_type: 'inbound', warehouse_id: 1, product_id: 1, quantity: 3 },
    ...Array.from({ length: 6 }, (_, index) => ({ id: index + 2, transaction_type: 'outbound', warehouse_id: 2, product_id: 2, quantity: 1 })),
  ]
  const overview = buildDashboardOverview({ products, warehouses, stock: stocks, transactions, stats: { product_count: 2, total_stock: 20, low_stock_count: 3 } })
  assert.deepEqual(overview.recentInbound?.map(row => row.id), [1])
  assert.deepEqual(overview.recentOutbound?.map(row => row.id), [7, 6])
  assert.deepEqual(overview.recentTransactions.map(row => row.id), [7, 6, 5, 4, 3])
})
