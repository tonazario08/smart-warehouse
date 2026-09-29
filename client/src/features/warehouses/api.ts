import type { ApiClient } from '../../shared/api/ApiClient'
import type { Warehouse, WarehouseFilters, WarehouseInput, WarehousePage } from './types'

export const warehouseKeys = {
  all: ['warehouses'] as const,
  lists: () => [...warehouseKeys.all, 'list'] as const,
  list: (filters: WarehouseFilters) => [...warehouseKeys.lists(), filters] as const,
}
export const createWarehousesApi = (client: ApiClient) => ({
  list: (filters: WarehouseFilters) => {
    const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
    if (filters.search) params.set('search', filters.search)
    return client.request<WarehousePage>(`/warehouses?${params}`)
  },
  create: (input: WarehouseInput) => client.request<Warehouse>('/warehouses', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: number, input: WarehouseInput) => client.request<Warehouse>(`/warehouses/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  delete: (id: number) => client.request<void>(`/warehouses/${id}`, { method: 'DELETE' }),
})
