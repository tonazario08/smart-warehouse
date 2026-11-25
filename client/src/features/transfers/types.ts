export type TransferInput = {
  source_warehouse_id: number
  destination_warehouse_id: number
  product_id: number
  quantity: number
  reference: string | null
  note: string | null
}
export type Transfer = TransferInput & {
  id: number
  created_by_id: number
  created_at: string
  outbound_id: number
  inbound_id: number
  outbound_transaction_id: number
  inbound_transaction_id: number
  source_quantity_before: number
  source_quantity_after: number
  destination_quantity_before: number
  destination_quantity_after: number
}
export type TransferFilters = {
  source_warehouse_id?: number
  destination_warehouse_id?: number
  product_id?: number
  created_from?: string
  created_to?: string
  page?: number
  page_size?: number
}
export type TransferDraft = {
  source: string
  destination: string
  product: string
  quantity: string
  reference: string
  note: string
}
