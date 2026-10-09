import assert from 'node:assert/strict'
import { buildDashboardOverview } from '../src/shared/lib/dashboard'

const overview = buildDashboardOverview({
  products: [
    { id: 1, sku: 'SP-001', name: 'Máy quét mã vạch', unit: 'cái', reorder_level: 10 },
    { id: 2, sku: 'SP-002', name: 'Thùng carton', unit: 'thùng', reorder_level: 20 },
  ],
  stats: { product_count: 2, total_stock: 22, low_stock_count: 1 },
  stock: [
    { id: 1, warehouse_id: 1, product_id: 1, quantity: 12 },
    { id: 2, warehouse_id: 1, product_id: 2, quantity: 10 },
  ],
  transactions: [
    { id: 4, transaction_type: 'inbound', warehouse_id: 1, product_id: 1, quantity: 3 },
    { id: 5, transaction_type: 'outbound', warehouse_id: 1, product_id: 2, quantity: 2 },
  ],
  warehouses: [{ id: 1, code: 'HCM-01', name: 'Kho Hồ Chí Minh' }],
})

assert.equal(overview.stats.productCount, 2)
assert.equal(overview.stats.totalStock, 22)
assert.equal(overview.stats.warehouseCount, 1)
assert.equal(overview.lowStockRows.length, 1)
assert.deepEqual(overview.lowStockRows[0], {
  id: 2,
  productName: 'Thùng carton',
  sku: 'SP-002',
  warehouseName: 'Kho Hồ Chí Minh',
  quantity: 10,
  unit: 'thùng',
  reorderLevel: 20,
  status: 'low',
})
assert.equal(overview.warehouseRows[0].totalStock, 22)
assert.equal(overview.warehouseRows[0].productCount, 2)
assert.equal(overview.recentTransactions[0].id, 5)
assert.equal(overview.recentTransactions[0].kind, 'outbound')
assert.equal(overview.recentTransactions[0].productName, 'Thùng carton')

const emptyOverview = buildDashboardOverview({
  products: [],
  stats: { product_count: 0, total_stock: 0, low_stock_count: 0 },
  stock: [],
  transactions: [],
  warehouses: [],
})

assert.deepEqual(emptyOverview.stockRows, [])
assert.deepEqual(emptyOverview.lowStockRows, [])
assert.deepEqual(emptyOverview.warehouseRows, [])
assert.deepEqual(emptyOverview.recentTransactions, [])
