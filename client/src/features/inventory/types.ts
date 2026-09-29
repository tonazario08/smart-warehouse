import type { Page } from '../../shared/api/types'

export interface StockRow {
  id: number
  warehouse_id: number
  product_id: number
  quantity: number
  created_at: string
}

export interface MovementRow {
  id: number
  warehouse_id: number
  product_id: number
  quantity: number
  reference: string | null
  note: string | null
  created_by_id: number
  created_at: string
}

export interface MovementInput {
  warehouse_id: number
  product_id: number
  quantity: number
  reference?: string
  note?: string
}

export type StockPageData = Page<StockRow>
export type MovementPageData = Page<MovementRow>

export interface InventoryFilters {
  page: number
  pageSize: number
  warehouseId: string
  productId: string
  createdFrom: string
  createdTo: string
}

export interface TransactionFilters extends InventoryFilters {
  type: string
}
