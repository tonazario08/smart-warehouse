import assert from 'node:assert/strict'
import { filterProducts } from '../src/shared/lib/products'

const products = [
  { id: 1, sku: 'LABEL-01', name: 'Nhãn nhiệt', category_id: 1, is_active: true },
  { id: 2, sku: 'BOX-01', name: 'Thùng carton', category_id: 2, is_active: false },
]

assert.deepEqual(filterProducts(products, { categoryId: null, search: 'nhãn' }).map((product) => product.id), [1])
assert.deepEqual(filterProducts(products, { categoryId: 2, search: '' }).map((product) => product.id), [2])
assert.deepEqual(filterProducts(products, { categoryId: 1, search: 'carton' }), [])
