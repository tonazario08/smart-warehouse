import type { ApiClient } from '../../shared/api/ApiClient'
import type { Product, ProductFilters, ProductInput, ProductPage } from './types'

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
}
export const createProductsApi = (client: ApiClient) => ({
  list: (filters: ProductFilters) => {
    const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
    if (filters.search) params.set('search', filters.search)
    if (filters.categoryId) params.set('category_id', filters.categoryId)
    if (filters.supplierId) params.set('supplier_id', filters.supplierId)
    if (filters.isActive) params.set('is_active', filters.isActive)
    return client.request<ProductPage>(`/products?${params}`)
  },
  create: (input: ProductInput) => client.request<Product>('/products', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: number, input: ProductInput) => client.request<Product>(`/products/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  delete: (id: number) => client.request<void>(`/products/${id}`, { method: 'DELETE' }),
})
