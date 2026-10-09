import type { Product, Stock, Warehouse } from '../../types'

export type InventoryStatus = 'healthy' | 'low'

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
      status: stock.quantity <= product.reorder_level ? 'low' : 'healthy',
    }]
  })
}

export function filterInventoryRows(rows: InventoryRow[], { search, warehouseId }: { search: string; warehouseId: number | null }) {
  const query = search.trim().toLocaleLowerCase('vi')
  return rows.filter((row) => {
    const matchesWarehouse = warehouseId === null || row.warehouseId === warehouseId
    const matchesSearch = query === '' || `${row.sku} ${row.productName} ${row.warehouseName}`.toLocaleLowerCase('vi').includes(query)
    return matchesWarehouse && matchesSearch
  })
}
