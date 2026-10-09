import assert from 'node:assert/strict'
import { test } from 'node:test'
import { api } from '../src/api.js'
import { buildMovementRows, filterMovementRows } from '../src/shared/lib/movements.js'

test('buildMovementRows joins transactions with real product and warehouse labels', () => {
  const rows = buildMovementRows({ transactions: [{ id: 2, transaction_type: 'outbound', warehouse_id: 3, product_id: 4, quantity: 5 }], products: [{ id: 4, sku: 'SP-04', name: 'Thùng carton', unit: 'cái' }], warehouses: [{ id: 3, code: 'HCM-01', name: 'Kho Hồ Chí Minh' }] })
  assert.deepEqual(rows, [{ id: 2, type: 'outbound', warehouseId: 3, productId: 4, productName: 'Thùng carton', sku: 'SP-04', warehouseName: 'Kho Hồ Chí Minh', quantity: 5, unit: 'cái' }])
})

test('filterMovementRows filters by movement type and Vietnamese search text', () => {
  const rows = [{ id: 1, type: 'inbound', warehouseId: 3, productId: 4, productName: 'Thùng carton', sku: 'SP-04', warehouseName: 'Kho Hồ Chí Minh', quantity: 5, unit: 'cái' }]
  assert.deepEqual(filterMovementRows(rows, { search: 'carton', type: 'inbound' }).map((row) => row.id), [1])
  assert.deepEqual(filterMovementRows(rows, { search: '', type: 'outbound' }), [])
})

test('productsAll retrieves every product page for movement list and form selections', async () => {
  const originalFetch = globalThis.fetch
  const requestedUrls = []
  globalThis.fetch = async (input) => {
    requestedUrls.push(String(input))
    const page = requestedUrls.length
    return {
      ok: true,
      status: 200,
      json: async () => ({ items: [{ id: page, sku: `SP-${page}`, name: `Sản phẩm ${page}` }], total: 101, page, page_size: 100 }),
    }
  }

  try {
    assert.deepEqual((await api.productsAll()).map((product) => product.id), [1, 2])
    assert.deepEqual(requestedUrls, [
      'http://localhost:8000/api/v1/products?page=1&page_size=100',
      'http://localhost:8000/api/v1/products?page=2&page_size=100',
    ])
  } finally {
    globalThis.fetch = originalFetch
  }
})
