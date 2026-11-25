import type { ApiClient } from '../../shared/api/ApiClient'

export interface DashboardStats {
  product_count: number
  total_stock: number
  low_stock_count: number
}

export const createDashboardApi = (client: ApiClient) => ({
  stats: () => client.request<DashboardStats>('/dashboard/stats'),
})
