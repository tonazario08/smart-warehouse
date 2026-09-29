import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import type { ApiClient } from '../../shared/api/ApiClient'
import { createInventoryApi, inventoryLookup } from './api'
import type { Product } from '../products/types'
import type { Warehouse } from '../warehouses/types'

const uniqueIds = (values: number[]) => [...new Set(values)]

export function useInventoryLabels(client: ApiClient, productIds: number[], warehouseIds: number[]) {
  const api = createInventoryApi(client)
  const products = useQuery({ queryKey: inventoryLookup.products, queryFn: api.listProducts, retry: false })
  const warehouses = useQuery({ queryKey: inventoryLookup.warehouses, queryFn: api.listWarehouses, retry: false })
  const missingProductIds = products.data ? uniqueIds(productIds).filter((id) => !products.data.items.some((product) => product.id === id)) : []
  const missingWarehouseIds = warehouses.data ? uniqueIds(warehouseIds).filter((id) => !warehouses.data.items.some((warehouse) => warehouse.id === id)) : []
  const productDetails = useQueries({ queries: missingProductIds.map((id) => ({
    queryKey: inventoryLookup.product(id), queryFn: () => api.getProduct(id), retry: false,
  })) })
  const warehouseDetails = useQueries({ queries: missingWarehouseIds.map((id) => ({
    queryKey: inventoryLookup.warehouse(id), queryFn: () => api.getWarehouse(id), retry: false,
  })) })
  const productMap = useMemo(() => new Map<number, Product>([
    ...(products.data?.items ?? []).map((product) => [product.id, product] as const),
    ...productDetails.flatMap((query, index) => query.data ? [[missingProductIds[index], query.data] as const] : []),
  ]), [products.data, productDetails, missingProductIds])
  const warehouseMap = useMemo(() => new Map<number, Warehouse>([
    ...(warehouses.data?.items ?? []).map((warehouse) => [warehouse.id, warehouse] as const),
    ...warehouseDetails.flatMap((query, index) => query.data ? [[missingWarehouseIds[index], query.data] as const] : []),
  ]), [warehouses.data, warehouseDetails, missingWarehouseIds])

  return {
    product: (id: number) => {
      const record = productMap.get(id)
      const detailIndex = missingProductIds.indexOf(id)
      const detail = detailIndex < 0 ? undefined : productDetails[detailIndex]
      return { record, loading: products.isPending || detail?.isPending, error: products.error ?? detail?.error, retry: () => detail?.refetch() ?? products.refetch() }
    },
    warehouse: (id: number) => {
      const record = warehouseMap.get(id)
      const detailIndex = missingWarehouseIds.indexOf(id)
      const detail = detailIndex < 0 ? undefined : warehouseDetails[detailIndex]
      return { record, loading: warehouses.isPending || detail?.isPending, error: warehouses.error ?? detail?.error, retry: () => detail?.refetch() ?? warehouses.refetch() }
    },
    productLookup: products,
    warehouseLookup: warehouses,
  }
}

export function ProductIdentity({ id, lookup }: { id: number; lookup: ReturnType<typeof useInventoryLabels> }) {
  const result = lookup.product(id)
  return <div className="inventory-identity">
    <strong className="scan-code">{result.record?.sku ?? `Product #${id}`}</strong>
    <small>{result.record?.name ?? (result.loading ? 'Resolving label…' : result.error ? 'Label lookup failed' : 'Record unavailable')}</small>
    {result.error && <button type="button" className="quiet lookup-retry" onClick={() => void result.retry()}>Retry product lookup for ID {id}</button>}
  </div>
}

export function WarehouseIdentity({ id, lookup }: { id: number; lookup: ReturnType<typeof useInventoryLabels> }) {
  const result = lookup.warehouse(id)
  return <div className="inventory-identity">
    <strong className="scan-code">{result.record?.code ?? `Warehouse #${id}`}</strong>
    <small>{result.record?.name ?? (result.loading ? 'Resolving label…' : result.error ? 'Label lookup failed' : 'Record unavailable')}</small>
    {result.error && <button type="button" className="quiet lookup-retry" onClick={() => void result.retry()}>Retry warehouse lookup for ID {id}</button>}
  </div>
}
