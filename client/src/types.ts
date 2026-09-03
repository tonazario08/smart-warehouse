export type Role = 'admin' | 'warehouse' | 'client'

export type User = { id: number; email: string; role: Role; is_active: boolean }
export type Page<T> = { items: T[]; total: number; page: number; page_size: number }
export type Category = { id: number; name: string; parent_id: number | null }
export type Product = { id: number; sku: string; name: string; description: string | null; category_id: number; supplier_id: number | null; unit: string; reorder_level: number; is_active: boolean }
export type Warehouse = { id: number; code: string; name: string; address: string; latitude: number | null; longitude: number | null }
export type Stock = { id: number; warehouse_id: number; product_id: number; quantity: number }
export type ProductInput = Omit<Product, 'id'>
