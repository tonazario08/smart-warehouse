export type Role = 'admin' | 'warehouse' | 'client'

export type User = { id: number; email: string; role: Role; is_active: boolean }
export type Page<T> = { items: T[]; total: number; page: number; page_size: number }
export type Category = { id: number; name: string; parent_id: number | null }
export type Supplier = { id: number; name: string; email: string | null; phone: string | null; address: string | null }
export type Product = { id: number; sku: string; name: string; description: string | null; category_id: number; supplier_id: number | null; unit: string; reorder_level: number; is_active: boolean }
export type Warehouse = { id: number; code: string; name: string; address: string; latitude: number | null; longitude: number | null }
export type WarehouseInput = Omit<Warehouse, 'id'>
export type Stock = { id: number; warehouse_id: number; product_id: number; quantity: number }
export type DashboardStats = { product_count: number; total_stock: number; low_stock_count: number }
export type Transaction = { id: number; transaction_type: 'inbound' | 'outbound'; warehouse_id: number; product_id: number; quantity: number; inbound_id?: number | null; outbound_id?: number | null; created_by_id?: number; created_at?: string }
export type MovementInput = { warehouse_id:number; product_id:number; quantity:number; reference:string | null; note:string | null }
export type Movement = MovementInput & { id:number }
export type MovementRead = Movement & { created_by_id: number; created_at: string }
export type ProductInput = Omit<Product, 'id'>
