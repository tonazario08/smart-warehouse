import type { Warehouse } from '../../types'
import type { InventoryRow } from './inventory'

export type WarehouseSummary = Warehouse & {
  productCount: number
  totalQuantity: number
  lowStockCount: number
}

export function buildWarehouseSummaries({ rows, warehouses }: { rows: InventoryRow[]; warehouses: Warehouse[] }): WarehouseSummary[] {
  return warehouses.map((warehouse) => {
    const stockRows = rows.filter((row) => row.warehouseId === warehouse.id)
    return {
      ...warehouse,
      productCount: new Set(stockRows.map((row) => row.productId)).size,
      totalQuantity: stockRows.reduce((total, row) => total + row.quantity, 0),
      lowStockCount: stockRows.filter((row) => row.status === 'low').length,
    }
  }).sort((left, right) => left.code.localeCompare(right.code, 'vi'))
}

export function filterWarehouseSummaries(warehouses: WarehouseSummary[], search: string) {
  const query = search.trim().toLocaleLowerCase('vi')
  if (query === '') return warehouses
  return warehouses.filter((warehouse) => `${warehouse.code} ${warehouse.name} ${warehouse.address}`.toLocaleLowerCase('vi').includes(query))
}
