import type { Page } from '../../shared/api/types'

export interface TransactionRow {
  id: number
  transaction_type: string
  warehouse_id: number
  product_id: number
  quantity: number
  inbound_id: number | null
  outbound_id: number | null
  created_by_id: number
  created_at: string
}

export type TransactionPage = Page<TransactionRow>
