import type { ApiClient } from '../../shared/api/ApiClient'
import type { CategoryInput, CategoryPage, Category } from './types'

export interface CategoryFilters { page: number; pageSize: number }
export const categoryKeys = {
  all: ['categories'] as const,
  lists: () => [...categoryKeys.all, 'list'] as const,
  list: (filters: CategoryFilters) => [...categoryKeys.lists(), filters] as const,
}

export const createCategoriesApi = (client: ApiClient) => ({
  list: (filters: CategoryFilters) => client.request<CategoryPage>(`/categories?page=${filters.page}&page_size=${filters.pageSize}`),
  create: (input: CategoryInput) => client.request<Category>('/categories', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: number, input: CategoryInput) => client.request<Category>(`/categories/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  delete: (id: number) => client.request<void>(`/categories/${id}`, { method: 'DELETE' }),
})
