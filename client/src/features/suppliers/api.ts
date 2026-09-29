import type { ApiClient } from '../../shared/api/ApiClient'
import type { Supplier, SupplierInput, SupplierPage } from './types'

export interface SupplierFilters { page: number; pageSize: number; search: string }
export const supplierKeys = {
  all: ['suppliers'] as const,
  lists: () => [...supplierKeys.all, 'list'] as const,
  list: (filters: SupplierFilters) => [...supplierKeys.lists(), filters] as const,
}
export const createSuppliersApi = (client: ApiClient) => ({
  list: (filters: SupplierFilters) => {
    const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
    if (filters.search) params.set('search', filters.search)
    return client.request<SupplierPage>(`/suppliers?${params}`)
  },
  create: (input: SupplierInput) => client.request<Supplier>('/suppliers', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: number, input: SupplierInput) => client.request<Supplier>(`/suppliers/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  delete: (id: number) => client.request<void>(`/suppliers/${id}`, { method: 'DELETE' }),
})
