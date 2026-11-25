import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildInventoryRows, filterInventoryRows } from '../src/shared/lib/inventory'

const products = [
  { id: 11, sku: 'SP-001', name: 'Bàn phím cơ', description: null, category_id: 1, supplier_id: null, unit: 'cái', reorder_level: 10, is_active: true },
  { id: 12, sku: 'SP-002', name: 'Chuột không dây', description: null, category_id: 1, supplier_id: null, unit: 'cái', reorder_level: 5, is_active: true },
]

const warehouses = [
  { id: 3, code: 'HN-01', name: 'Kho Hà Nội', address: 'Hà Nội', latitude: null, longitude: null },
  { id: 4, code: 'HCM-01', name: 'Kho Hồ Chí Minh', address: 'Hồ Chí Minh', latitude: null, longitude: null },
]

test('buildInventoryRows joins stock with product and warehouse and flags stock at its reorder level', () => {
  const rows = buildInventoryRows({
    stocks: [{ id: 1, warehouse_id: 3, product_id: 11, quantity: 10 }, { id: 2, warehouse_id: 4, product_id: 12, quantity: 6 }],
    products,
    warehouses,
  })

  assert.deepEqual(rows, [
    { id: 1, warehouseId: 3, productId: 11, sku: 'SP-001', productName: 'Bàn phím cơ', warehouseName: 'Kho Hà Nội', quantity: 10, unit: 'cái', reorderLevel: 10, status: 'low' },
    { id: 2, warehouseId: 4, productId: 12, sku: 'SP-002', productName: 'Chuột không dây', warehouseName: 'Kho Hồ Chí Minh', quantity: 6, unit: 'cái', reorderLevel: 5, status: 'healthy' },
  ])
})

test('filterInventoryRows matches Vietnamese product identifiers and warehouse selection', () => {
  const rows = buildInventoryRows({
    stocks: [{ id: 1, warehouse_id: 3, product_id: 11, quantity: 10 }, { id: 2, warehouse_id: 4, product_id: 12, quantity: 6 }],
    products,
    warehouses,
  })

  assert.deepEqual(filterInventoryRows(rows, { search: 'chuột', warehouseId: null }).map((row) => row.id), [2])
  assert.deepEqual(filterInventoryRows(rows, { search: '', warehouseId: 3 }).map((row) => row.id), [1])
})
