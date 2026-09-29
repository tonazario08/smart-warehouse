import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import type { ApiClient } from '../../shared/api/ApiClient'
import { createInventoryApi, inventoryLookup } from './api'
import type { InventoryFilters, TransactionFilters } from './types'

export function InventoryFiltersForm({ client, filters, onChange, onApply, showType = false, onTypeChange, showLookupStatus = true }: {
  client: ApiClient
  filters: InventoryFilters | TransactionFilters
  onChange: (filters: InventoryFilters | TransactionFilters) => void
  onApply: (event: FormEvent) => void
  showType?: boolean
  onTypeChange?: (type: string) => void
  showLookupStatus?: boolean
}) {
  const api = createInventoryApi(client)
  const products = useQuery({ queryKey: inventoryLookup.products, queryFn: api.listProducts, retry: false })
  const warehouses = useQuery({ queryKey: inventoryLookup.warehouses, queryFn: api.listWarehouses, retry: false })
  const blocked = products.isPending || products.isError || warehouses.isPending || warehouses.isError

  return <>
    <form className="resource-filters inventory-filters" aria-label="Filter inventory" onSubmit={onApply}>
      {showType && <label>Transaction type<select value={'type' in filters ? filters.type : ''} onChange={(event) => onTypeChange?.(event.target.value)}><option value="">All types</option><option value="inbound">Inbound</option><option value="outbound">Outbound</option></select></label>}
      <label>Warehouse<select value={filters.warehouseId} disabled={blocked || !warehouses.data?.items.length} onChange={(event) => onChange({ ...filters, warehouseId: event.target.value })}>
        <option value="">All warehouses</option>{warehouses.data?.items.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>)}
      </select></label>
      <label>Product<select value={filters.productId} disabled={blocked || !products.data?.items.length} onChange={(event) => onChange({ ...filters, productId: event.target.value })}>
        <option value="">All products</option>{products.data?.items.map((product) => <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>)}
      </select></label>
      <label>Created from<input type="datetime-local" value={filters.createdFrom} onChange={(event) => onChange({ ...filters, createdFrom: event.target.value })} /></label>
      <label>Created to<input type="datetime-local" value={filters.createdTo} onChange={(event) => onChange({ ...filters, createdTo: event.target.value })} /></label>
      <button type="submit">Apply filters</button>
    </form>
    {showLookupStatus && products.isPending && <p className="async-state" role="status">Loading product filter options…</p>}
    {showLookupStatus && warehouses.isPending && <p className="async-state" role="status">Loading warehouse filter options…</p>}
    {showLookupStatus && products.isError && <p className="async-state async-state-error" role="alert">{products.error instanceof Error ? products.error.message : 'Product lookup could not be loaded.'} <button type="button" className="quiet" onClick={() => void products.refetch()}>Retry product lookup</button></p>}
    {showLookupStatus && warehouses.isError && <p className="async-state async-state-error" role="alert">{warehouses.error instanceof Error ? warehouses.error.message : 'Warehouse lookup could not be loaded.'} <button type="button" className="quiet" onClick={() => void warehouses.refetch()}>Retry warehouse lookup</button></p>}
    {showLookupStatus && !products.isPending && !products.isError && !products.data?.items.length && <p className="async-state async-state-empty">No products are available to filter.</p>}
    {showLookupStatus && !warehouses.isPending && !warehouses.isError && !warehouses.data?.items.length && <p className="async-state async-state-empty">No warehouses are available to filter.</p>}
  </>
}
