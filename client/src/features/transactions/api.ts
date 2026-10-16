import type { ApiClient } from '../../shared/api/ApiClient'
import type { TransactionFilters } from '../inventory/types'
import type { TransactionPage } from './types'

export const transactionKeys = {
  all: ['transactions'] as const,
  list: (filters: TransactionFilters) => ['transactions', filters] as const,
}

export const createTransactionsApi = (client: ApiClient) => ({
  list: (filters: TransactionFilters) => {
    const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
    if (filters.warehouseId) params.set('warehouse_id', filters.warehouseId)
    if (filters.productId) params.set('product_id', filters.productId)
    if (filters.createdFrom) params.set('created_from', new Date(filters.createdFrom).toISOString())
    if (filters.createdTo) params.set('created_to', new Date(filters.createdTo).toISOString())
    if (filters.type) params.set('transaction_type', filters.type)
    return client.request<TransactionPage>(`/transactions?${params}`)
  },
})
