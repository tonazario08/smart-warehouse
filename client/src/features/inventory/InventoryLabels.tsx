import { useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { ApiClient } from '../../shared/api/ApiClient'
import type { Product } from '../products/types'
import type { Warehouse } from '../warehouses/types'
import { createInventoryApi, inventoryLookup } from './api'

const detailConcurrency = 4
const uniqueSortedIds = (values: number[]) => [...new Set(values)].sort((left, right) => left - right)

type DetailTask = { kind: 'product'; id: number } | { kind: 'warehouse'; id: number }
type ResolvedLabels = {
  products: Map<number, Product>
  warehouses: Map<number, Warehouse>
  failures: Map<string, Error>
}

const detailKey = (task: DetailTask) => task.kind === 'product'
  ? inventoryLookup.product(task.id)
  : inventoryLookup.warehouse(task.id)

export function useInventoryLabels(client: ApiClient, productIds: number[], warehouseIds: number[]) {
  const api = createInventoryApi(client)
  const cache = useQueryClient()
  const products = useQuery({ queryKey: inventoryLookup.products, queryFn: api.listProducts, retry: false })
  const warehouses = useQuery({ queryKey: inventoryLookup.warehouses, queryFn: api.listWarehouses, retry: false })
  const uniqueProductIds = uniqueSortedIds(productIds)
  const uniqueWarehouseIds = uniqueSortedIds(warehouseIds)
  const missingProductIds = products.data
    ? uniqueProductIds.filter((id) => !products.data.items.some((product) => product.id === id))
    : []
  const missingWarehouseIds = warehouses.data
    ? uniqueWarehouseIds.filter((id) => !warehouses.data.items.some((warehouse) => warehouse.id === id))
    : []
  const labelsKey = ['inventory', 'labels', missingProductIds, missingWarehouseIds] as const
  const resolver = useQuery<ResolvedLabels>({
    queryKey: labelsKey,
    enabled: products.isSuccess && warehouses.isSuccess && (missingProductIds.length > 0 || missingWarehouseIds.length > 0),
    retry: false,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const resolved: ResolvedLabels = { products: new Map(), warehouses: new Map(), failures: new Map() }
      const tasks: DetailTask[] = [
        ...missingProductIds.map((id) => ({ kind: 'product' as const, id })),
        ...missingWarehouseIds.map((id) => ({ kind: 'warehouse' as const, id })),
      ].filter((task) => {
        const value = cache.getQueryData<Product | Warehouse>(detailKey(task))
        if (!value) return true
        if (task.kind === 'product') resolved.products.set(task.id, value as Product)
        else resolved.warehouses.set(task.id, value as Warehouse)
        return false
      })
      let nextTask = 0
      const worker = async () => {
        while (nextTask < tasks.length) {
          const task = tasks[nextTask++]
          try {
            const value = task.kind === 'product' ? await api.getProduct(task.id) : await api.getWarehouse(task.id)
            cache.setQueryData(detailKey(task), value)
            if (task.kind === 'product') resolved.products.set(task.id, value as Product)
            else resolved.warehouses.set(task.id, value as Warehouse)
          } catch (error) {
            resolved.failures.set(`${task.kind}:${task.id}`, error instanceof Error ? error : new Error('Label lookup failed.'))
          }
        }
      }
      await Promise.all(Array.from({ length: Math.min(detailConcurrency, tasks.length) }, worker))
      return resolved
    },
  })

  const productMap = useMemo(() => new Map<number, Product>([
    ...(products.data?.items ?? []).map((product) => [product.id, product] as const),
    ...(resolver.data?.products ?? new Map()).entries(),
  ]), [products.data, resolver.data])
  const warehouseMap = useMemo(() => new Map<number, Warehouse>([
    ...(warehouses.data?.items ?? []).map((warehouse) => [warehouse.id, warehouse] as const),
    ...(resolver.data?.warehouses ?? new Map()).entries(),
  ]), [warehouses.data, resolver.data])
  const lookupError = products.error ?? warehouses.error ?? resolver.data?.failures.values().next().value
  const hasMissingLabels = missingProductIds.length > 0 || missingWarehouseIds.length > 0

  return {
    product: (id: number) => ({
      record: productMap.get(id),
      loading: products.isPending || (missingProductIds.includes(id) && resolver.isPending),
      error: Boolean(products.error || resolver.data?.failures.has(`product:${id}`)),
    }),
    warehouse: (id: number) => ({
      record: warehouseMap.get(id),
      loading: warehouses.isPending || (missingWarehouseIds.includes(id) && resolver.isPending),
      error: Boolean(warehouses.error || resolver.data?.failures.has(`warehouse:${id}`)),
    }),
    loading: products.isPending || warehouses.isPending || (hasMissingLabels && resolver.isPending),
    error: lookupError,
    retry: () => {
      if (products.error || warehouses.error) {
        return Promise.all([products.error ? products.refetch() : undefined, warehouses.error ? warehouses.refetch() : undefined])
      }
      return resolver.refetch()
    },
  }
}

export function ProductIdentity({ id, lookup }: { id: number; lookup: ReturnType<typeof useInventoryLabels> }) {
  const result = lookup.product(id)
  return <div className="inventory-identity">
    <strong className="scan-code">{result.record?.sku ?? `Product #${id}`}</strong>
    <small>{result.record?.name ?? (result.loading ? 'Resolving label…' : result.error ? 'Label lookup failed' : 'Record unavailable')}</small>
  </div>
}

export function WarehouseIdentity({ id, lookup }: { id: number; lookup: ReturnType<typeof useInventoryLabels> }) {
  const result = lookup.warehouse(id)
  return <div className="inventory-identity">
    <strong className="scan-code">{result.record?.code ?? `Warehouse #${id}`}</strong>
    <small>{result.record?.name ?? (result.loading ? 'Resolving label…' : result.error ? 'Label lookup failed' : 'Record unavailable')}</small>
  </div>
}
