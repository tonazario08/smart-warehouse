import type { Product, Stock, Warehouse } from '../../types'

export type InventoryStatus = 'healthy' | 'low' | 'out'

export const inventoryStatusLabels: Record<InventoryStatus, string> = {
  healthy: 'Ổn định',
  low: 'Sắp hết hàng',
  out: 'Hết hàng',
}

export const inventoryStatusVariants = { healthy: 'success', low: 'warning', out: 'danger' } as const

export function getInventoryStatus(quantity: number, reorderLevel: number): InventoryStatus {
  return quantity <= 0 ? 'out' : quantity <= reorderLevel ? 'low' : 'healthy'
}

// The scale compares stock with its minimum; it does not imply warehouse capacity.
export function getStockScale(quantity: number, reorderLevel: number) {
  const maximum = Math.max(quantity * 1.25, reorderLevel * 2, 1)
  return { maximum, currentPercent: Math.max(0, quantity / maximum * 100), minimumPercent: Math.max(0, reorderLevel / maximum * 100) }
}

export type InventoryRow = {
  id: number
  warehouseId: number
  productId: number
  sku: string
  productName: string
  warehouseName: string
  quantity: number
  unit: string
  reorderLevel: number
  status: InventoryStatus
}

export function buildInventoryRows({ products, stocks, warehouses }: { products: Product[]; stocks: Stock[]; warehouses: Warehouse[] }): InventoryRow[] {
  const productsById = new Map(products.map((product) => [product.id, product]))
  const warehousesById = new Map(warehouses.map((warehouse) => [warehouse.id, warehouse]))

  return stocks.flatMap((stock) => {
    const product = productsById.get(stock.product_id)
    const warehouse = warehousesById.get(stock.warehouse_id)
    if (!product || !warehouse) return []

    return [{
      id: stock.id,
      warehouseId: warehouse.id,
      productId: product.id,
      sku: product.sku,
      productName: product.name,
      warehouseName: warehouse.name,
      quantity: stock.quantity,
      unit: product.unit,
      reorderLevel: product.reorder_level,
      status: getInventoryStatus(stock.quantity, product.reorder_level),
    }]
  })
}

export function filterInventoryRows(rows: InventoryRow[], { search, warehouseId, status, categoryProductIds }: { search: string; warehouseId: number | null; status?: InventoryStatus | ''; categoryProductIds?: Set<number> }) {
  const query = search.trim().toLocaleLowerCase('vi')
  return rows.filter((row) => {
    const matchesWarehouse = warehouseId === null || row.warehouseId === warehouseId
    const matchesSearch = query === '' || `${row.sku} ${row.productName} ${row.warehouseName}`.toLocaleLowerCase('vi').includes(query)
    const matchesStatus = !status || row.status === status
    const matchesCategory = categoryProductIds === undefined || categoryProductIds.has(row.productId)
    return matchesWarehouse && matchesSearch && matchesStatus && matchesCategory
  })
}
