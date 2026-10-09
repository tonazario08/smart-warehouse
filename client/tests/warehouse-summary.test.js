import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildWarehouseSummaries, filterWarehouseSummaries } from '../src/shared/lib/warehouses'

const warehouses = [
  { id: 2, code: 'HCM-01', name: 'Kho Hồ Chí Minh', address: 'Quận 1', latitude: 10.77, longitude: 106.7 },
  { id: 1, code: 'HN-01', name: 'Kho Hà Nội', address: 'Ba Đình', latitude: null, longitude: null },
]

const rows = [
  { id: 1, warehouseId: 2, productId: 11, sku: 'SP-001', productName: 'Bàn phím cơ', warehouseName: 'Kho Hồ Chí Minh', quantity: 8, unit: 'cái', reorderLevel: 10, status: 'low' },
  { id: 2, warehouseId: 2, productId: 12, sku: 'SP-002', productName: 'Chuột không dây', warehouseName: 'Kho Hồ Chí Minh', quantity: 6, unit: 'cái', reorderLevel: 5, status: 'healthy' },
]

test('buildWarehouseSummaries preserves warehouses without stock and aggregates their real inventory', () => {
  assert.deepEqual(buildWarehouseSummaries({ warehouses, rows }), [
    { id: 2, code: 'HCM-01', name: 'Kho Hồ Chí Minh', address: 'Quận 1', latitude: 10.77, longitude: 106.7, productCount: 2, totalQuantity: 14, lowStockCount: 1 },
    { id: 1, code: 'HN-01', name: 'Kho Hà Nội', address: 'Ba Đình', latitude: null, longitude: null, productCount: 0, totalQuantity: 0, lowStockCount: 0 },
  ])
})

test('filterWarehouseSummaries matches a warehouse code or Vietnamese name', () => {
  const summaries = buildWarehouseSummaries({ warehouses, rows })

  assert.deepEqual(filterWarehouseSummaries(summaries, 'hà nội').map((warehouse) => warehouse.id), [1])
  assert.deepEqual(filterWarehouseSummaries(summaries, 'HCM-01').map((warehouse) => warehouse.id), [2])
})
