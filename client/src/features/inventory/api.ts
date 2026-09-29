import type { ApiClient } from '../../shared/api/ApiClient'
import type { Product } from '../products/types'
import { createProductsApi, productKeys } from '../products/api'
import type { Warehouse } from '../warehouses/types'
import { createWarehousesApi, warehouseKeys } from '../warehouses/api'
import type { InventoryFilters, MovementCreateResponse, MovementInput, MovementPageData, MovementRow, StockPageData, StockRow } from './types'

export const stockKeys = {
  all: ['stock'] as const,
  list: (filters: InventoryFilters) => ['stock', filters] as const,
}

export const inboundKeys = {
  all: ['inbounds'] as const,
  list: (filters: InventoryFilters) => ['inbounds', filters] as const,
}

export const outboundKeys = {
  all: ['outbounds'] as const,
  list: (filters: InventoryFilters) => ['outbounds', filters] as const,
}

export const inventoryLookup = {
  products: productKeys.list({ page: 1, pageSize: 100, search: '', categoryId: '', supplierId: '', isActive: '' }),
  warehouses: warehouseKeys.list({ page: 1, pageSize: 100, search: '' }),
  product: (id: number) => ['products', 'detail', id] as const,
  warehouse: (id: number) => ['warehouses', 'detail', id] as const,
}

function makeParams(filters: InventoryFilters, transactionType?: string) {
  const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
  if (filters.warehouseId) params.set('warehouse_id', filters.warehouseId)
  if (filters.productId) params.set('product_id', filters.productId)
  if (filters.createdFrom) params.set('created_from', new Date(filters.createdFrom).toISOString())
  if (filters.createdTo) params.set('created_to', new Date(filters.createdTo).toISOString())
  if (transactionType) params.set('transaction_type', transactionType)
  return params
}

export const createInventoryApi = (client: ApiClient) => ({
  listStock: (filters: InventoryFilters) => client.request<StockPageData>(`/stock?${makeParams(filters)}`),
  listInbounds: (filters: InventoryFilters) => client.request<MovementPageData>(`/inbounds?${makeParams(filters)}`),
  listOutbounds: (filters: InventoryFilters) => client.request<MovementPageData>(`/outbounds?${makeParams(filters)}`),
  createInbound: (input: MovementInput) => client.request<MovementCreateResponse>('/inbounds', { method: 'POST', body: JSON.stringify(normalizeMovement(input)) }),
  createOutbound: (input: MovementInput) => client.request<MovementCreateResponse>('/outbounds', { method: 'POST', body: JSON.stringify(normalizeMovement(input)) }),
  listProducts: () => createProductsApi(client).list({ page: 1, pageSize: 100, search: '', categoryId: '', supplierId: '', isActive: '' }),
  listWarehouses: () => createWarehousesApi(client).list({ page: 1, pageSize: 100, search: '' }),
  getProduct: (id: number) => client.request<Product>(`/products/${id}`),
  getWarehouse: (id: number) => client.request<Warehouse>(`/warehouses/${id}`),
})

function normalizeMovement(input: MovementInput): MovementInput {
  const reference = input.reference?.trim()
  const note = input.note?.trim()
  return {
    warehouse_id: input.warehouse_id,
    product_id: input.product_id,
    quantity: input.quantity,
    ...(reference ? { reference } : {}),
    ...(note ? { note } : {}),
  }
}
