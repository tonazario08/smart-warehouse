import type { Category, Page, Product, ProductInput, Stock, User, Warehouse } from './types'

const apiBaseUrl = 'http://localhost:8000/api/v1'
export class ApiError extends Error {}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(typeof body?.detail === 'string' ? body.detail : 'Request failed')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) => request<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<User>('/auth/me', {}, token),
  products: () => request<Page<Product>>('/products?page_size=100'),
  categories: () => request<Page<Category>>('/categories?page_size=100'),
  warehouses: (token: string) => request<Warehouse[]>('/warehouses', {}, token),
  stock: (token: string) => request<Stock[]>('/stock', {}, token),
  createProduct: (token: string, input: ProductInput) => request<Product>('/products', { method: 'POST', body: JSON.stringify(input) }, token),
  updateProduct: (token: string, id: number, input: ProductInput) => request<Product>(`/products/${id}`, { method: 'PUT', body: JSON.stringify(input) }, token),
  deleteProduct: (token: string, id: number) => request<void>(`/products/${id}`, { method: 'DELETE' }, token),
}
