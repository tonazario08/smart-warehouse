import type { Category, DashboardStats, Movement, MovementInput, Page, Product, ProductInput, Stock, Supplier, Transaction, User, Warehouse, WarehouseInput } from './types'

const apiBaseUrl = 'http://localhost:8000/api/v1'
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(typeof body?.detail === 'string' ? body.detail : 'Request failed', response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) => request<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<User>('/auth/me', {}, token),
  products: (page = 1) => request<Page<Product>>(`/products?page=${page}&page_size=100`),
  productsAll: async () => {
    const firstPage = await api.products()
    const totalPages = Math.ceil(firstPage.total / firstPage.page_size)

    if (totalPages <= 1) return firstPage.items

    const remainingPages = await Promise.all(
      Array.from({ length: totalPages - 1 }, (_, index) => api.products(index + 2)),
    )

    return [...firstPage.items, ...remainingPages.flatMap((page) => page.items)]
  },
  product: (id: number) => request<Product>(`/products/${id}`),
  categories: () => request<Page<Category>>('/categories?page_size=100'),
  suppliers: (token: string) => request<Page<Supplier>>('/suppliers?page_size=100', {}, token),
  warehouses: (token: string) => request<Warehouse[]>('/warehouses', {}, token),
  warehouse: (token: string, id: number) => request<Warehouse>(`/warehouses/${id}`, {}, token),
  stock: (token: string) => request<Stock[]>('/stock', {}, token),
  dashboardStats: (token: string) => request<DashboardStats>('/dashboard/stats', {}, token),
  transactions: (token: string) => request<Transaction[]>('/transactions', {}, token),
  createInbound: (token:string,input:MovementInput) => request<Movement>('/inbounds',{method:'POST',body:JSON.stringify(input)},token),
  createOutbound: (token:string,input:MovementInput) => request<Movement>('/outbounds',{method:'POST',body:JSON.stringify(input)},token),
  createProduct: (token: string, input: ProductInput) => request<Product>('/products', { method: 'POST', body: JSON.stringify(input) }, token),
  updateProduct: (token: string, id: number, input: ProductInput) => request<Product>(`/products/${id}`, { method: 'PUT', body: JSON.stringify(input) }, token),
  deleteProduct: (token: string, id: number) => request<void>(`/products/${id}`, { method: 'DELETE' }, token),
  createWarehouse: (token: string, input: WarehouseInput) => request<Warehouse>('/warehouses', { method: 'POST', body: JSON.stringify(input) }, token),
  updateWarehouse: (token: string, id: number, input: WarehouseInput) => request<Warehouse>(`/warehouses/${id}`, { method: 'PUT', body: JSON.stringify(input) }, token),
}
