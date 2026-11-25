import type { ApiClient } from '../../shared/api/ApiClient'
import { collectAllPages } from '../../shared/api/collectAllPages'
import type { MovementInputLike } from '../../shared/api/movementIdempotency'
import type { Product } from '../products/types'
import { createProductsApi, productKeys } from '../products/api'
import type { Warehouse } from '../warehouses/types'
import { createWarehousesApi, warehouseKeys } from '../warehouses/api'
import type { InventoryFilters, MovementCreateResponse, MovementInput, MovementPageData, MovementRow, StockPageData, StockRow } from './types'

/** Accepts both the form input (optional text) and a stored pending input (explicit nulls). */
export type MovementCreateInput = Omit<MovementInputLike, 'reference' | 'note'> & {
  reference?: string | null
  note?: string | null
}

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
  products: [...productKeys.all, 'lookup', 'all'] as const,
  warehouses: [...warehouseKeys.all, 'lookup', 'all'] as const,
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

export const createInventoryApi = (client: ApiClient) => {
  const productsApi = createProductsApi(client)
  const warehousesApi = createWarehousesApi(client)
  return {
  listStock: (filters: InventoryFilters) => client.request<StockPageData>(`/stock?${makeParams(filters)}`),
  listInbounds: (filters: InventoryFilters) => client.request<MovementPageData>(`/inbounds?${makeParams(filters)}`),
  listOutbounds: (filters: InventoryFilters) => client.request<MovementPageData>(`/outbounds?${makeParams(filters)}`),
  createInbound: (input: MovementCreateInput, key: string) => client.request<MovementCreateResponse>('/inbounds', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(normalizeMovement(input)) }),
  createOutbound: (input: MovementCreateInput, key: string) => client.request<MovementCreateResponse>('/outbounds', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(normalizeMovement(input)) }),
  getInboundByKey: (key: string) => client.request<MovementCreateResponse>('/inbounds/by-key/' + encodeURIComponent(key)),
  getOutboundByKey: (key: string) => client.request<MovementCreateResponse>('/outbounds/by-key/' + encodeURIComponent(key)),
  listProducts: () => collectAllPages((page) => productsApi.list({ page, pageSize: 100, search: '', categoryId: '', supplierId: '', isActive: '' })),
  listWarehouses: () => collectAllPages((page) => warehousesApi.list({ page, pageSize: 100, search: '' })),
  getProduct: (id: number) => client.request<Product>(`/products/${id}`),
  getWarehouse: (id: number) => client.request<Warehouse>(`/warehouses/${id}`),
  }
}

function normalizeMovement(input: MovementCreateInput): MovementInput {
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
