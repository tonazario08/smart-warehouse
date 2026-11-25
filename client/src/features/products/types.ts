import type { Page } from '../../shared/api/types'

export interface Product {
  id: number; sku: string; name: string; description: string | null; category_id: number
  supplier_id: number | null; unit: string; reorder_level: number; is_active: boolean
}
export type ProductPage = Page<Product>
export interface ProductInput extends Omit<Product, 'id'> {}
export interface ProductFilters { page: number; pageSize: number; search: string; categoryId: string; supplierId: string; isActive: string }
