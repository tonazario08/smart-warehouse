import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import type { ApiClient } from '../../shared/api/ApiClient'
import { createInventoryApi, inventoryLookup } from './api'
import type { InventoryFilters, TransactionFilters } from './types'

export function InventoryFiltersForm({ client, filters, onChange, onApply, showType = false, onTypeChange, showLookupStatus = true, locale = 'en' }: {
  client: ApiClient
  filters: InventoryFilters | TransactionFilters
  onChange: (filters: InventoryFilters | TransactionFilters) => void
  onApply: (event: FormEvent) => void
  showType?: boolean
  onTypeChange?: (type: string) => void
  locale?: 'en' | 'vi'
  showLookupStatus?: boolean
}) {
  const vi = locale === 'vi'
  const api = createInventoryApi(client)
  const products = useQuery({ queryKey: inventoryLookup.products, queryFn: api.listProducts, retry: false })
  const warehouses = useQuery({ queryKey: inventoryLookup.warehouses, queryFn: api.listWarehouses, retry: false })
  const blocked = products.isPending || products.isError || warehouses.isPending || warehouses.isError

  return <>
    <form className="resource-filters inventory-filters" aria-label={vi ? 'Lọc giao dịch' : 'Filter inventory'} onSubmit={onApply}>
      {showType && <label>{vi ? 'Loại giao dịch' : 'Transaction type'}<select value={'type' in filters ? filters.type : ''} onChange={(event) => onTypeChange?.(event.target.value)}><option value="">{vi ? 'Tất cả loại' : 'All types'}</option><option value="inbound">{vi ? 'Nhập kho' : 'Inbound'}</option><option value="outbound">{vi ? 'Xuất kho' : 'Outbound'}</option></select></label>}
      <label>{vi ? 'Kho hàng' : 'Warehouse'}<select value={filters.warehouseId} disabled={blocked || !warehouses.data?.items.length} onChange={(event) => onChange({ ...filters, warehouseId: event.target.value })}>
        <option value="">{vi ? 'Tất cả kho' : 'All warehouses'}</option>{warehouses.data?.items.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>)}
      </select></label>
      <label>{vi ? 'Sản phẩm' : 'Product'}<select value={filters.productId} disabled={blocked || !products.data?.items.length} onChange={(event) => onChange({ ...filters, productId: event.target.value })}>
        <option value="">{vi ? 'Tất cả sản phẩm' : 'All products'}</option>{products.data?.items.map((product) => <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>)}
      </select></label>
      <label>{vi ? 'Từ thời điểm' : 'Created from'}<input type="datetime-local" value={filters.createdFrom} onChange={(event) => onChange({ ...filters, createdFrom: event.target.value })} /></label>
      <label>{vi ? 'Đến thời điểm' : 'Created to'}<input type="datetime-local" value={filters.createdTo} onChange={(event) => onChange({ ...filters, createdTo: event.target.value })} /></label>
      <button type="submit">{vi ? 'Áp dụng bộ lọc' : 'Apply filters'}</button>
    </form>
    {showLookupStatus && products.isPending && <p className="async-state" role="status">{vi ? 'Đang tải bộ lọc sản phẩm…' : 'Loading product filter options…'}</p>}
    {showLookupStatus && warehouses.isPending && <p className="async-state" role="status">{vi ? 'Đang tải bộ lọc kho hàng…' : 'Loading warehouse filter options…'}</p>}
    {showLookupStatus && products.isError && <p className="async-state async-state-error" role="alert">{vi ? 'Không thể tải bộ lọc sản phẩm.' : products.error instanceof Error ? products.error.message : 'Product lookup could not be loaded.'} <button type="button" className="quiet" onClick={() => void products.refetch()}>{vi ? 'Thử lại sản phẩm' : 'Retry product lookup'}</button></p>}
    {showLookupStatus && warehouses.isError && <p className="async-state async-state-error" role="alert">{vi ? 'Không thể tải bộ lọc kho hàng.' : warehouses.error instanceof Error ? warehouses.error.message : 'Warehouse lookup could not be loaded.'} <button type="button" className="quiet" onClick={() => void warehouses.refetch()}>{vi ? 'Thử lại kho hàng' : 'Retry warehouse lookup'}</button></p>}
    {showLookupStatus && !products.isPending && !products.isError && !products.data?.items.length && <p className="async-state async-state-empty">{vi ? 'Chưa có sản phẩm để lọc.' : 'No products are available to filter.'}</p>}
    {showLookupStatus && !warehouses.isPending && !warehouses.isError && !warehouses.data?.items.length && <p className="async-state async-state-empty">{vi ? 'Chưa có kho hàng để lọc.' : 'No warehouses are available to filter.'}</p>}
  </>
}
