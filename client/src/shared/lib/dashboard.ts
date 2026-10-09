import type { DashboardStats, Product, Stock, Transaction, Warehouse } from '../../types'

type DashboardInput = {
  products: Pick<Product, 'id' | 'sku' | 'name' | 'unit' | 'reorder_level'>[]
  stats: DashboardStats
  stock: Stock[]
  transactions: Transaction[]
  warehouses: Pick<Warehouse, 'id' | 'code' | 'name'>[]
}

export type StockStatus = 'low' | 'healthy'

export type DashboardStockRow = {
  id: number
  productName: string
  sku: string
  warehouseName: string
  quantity: number
  unit: string
  reorderLevel: number
  status: StockStatus
}

export type DashboardWarehouseRow = {
  id: number
  code: string
  name: string
  productCount: number
  totalStock: number
  lowStockCount: number
}

export type DashboardTransactionRow = {
  id: number
  kind: 'inbound' | 'outbound'
  productName: string
  warehouseName: string
  quantity: number
  unit: string
}

export function buildDashboardOverview({ products, stats, stock, transactions, warehouses }: DashboardInput) {
  const productsById = new Map(products.map((product) => [product.id, product]))
  const warehousesById = new Map(warehouses.map((warehouse) => [warehouse.id, warehouse]))
  const stockRows: DashboardStockRow[] = stock.map((item) => {
    const product = productsById.get(item.product_id)
    const warehouse = warehousesById.get(item.warehouse_id)
    const reorderLevel = product?.reorder_level ?? 0
    const status: StockStatus = item.quantity <= reorderLevel ? 'low' : 'healthy'
    return {
      id: item.id,
      productName: product?.name ?? 'Sản phẩm không xác định',
      sku: product?.sku ?? '—',
      warehouseName: warehouse?.name ?? 'Kho không xác định',
      quantity: item.quantity,
      unit: product?.unit ?? '',
      reorderLevel,
      status,
    }
  }).sort((left, right) => {
    if (left.status !== right.status) return left.status === 'low' ? -1 : 1
    return (left.quantity - left.reorderLevel) - (right.quantity - right.reorderLevel)
  })

  const warehouseRows = warehouses.map((warehouse) => {
    const warehouseStock = stockRows.filter((item) => item.warehouseName === warehouse.name)
    return {
      id: warehouse.id,
      code: warehouse.code,
      name: warehouse.name,
      productCount: new Set(warehouseStock.map((item) => item.sku)).size,
      totalStock: warehouseStock.reduce((total, item) => total + item.quantity, 0),
      lowStockCount: warehouseStock.filter((item) => item.status === 'low').length,
    }
  }).sort((left, right) => left.code.localeCompare(right.code, 'vi'))

  const recentTransactions: DashboardTransactionRow[] = [...transactions].sort((left, right) => right.id - left.id).slice(0, 5).map((transaction) => {
    const product = productsById.get(transaction.product_id)
    const warehouse = warehousesById.get(transaction.warehouse_id)
    return {
      id: transaction.id,
      kind: transaction.transaction_type,
      productName: product?.name ?? 'Sản phẩm không xác định',
      warehouseName: warehouse?.name ?? 'Kho không xác định',
      quantity: transaction.quantity,
      unit: product?.unit ?? '',
    }
  })

  return {
    stats: {
      productCount: stats.product_count,
      totalStock: stats.total_stock,
      lowStockCount: stats.low_stock_count,
      warehouseCount: warehouses.length,
    },
    stockRows,
    lowStockRows: stockRows.filter((item) => item.status === 'low'),
    warehouseRows,
    recentTransactions,
  }
}
