import type { Page } from '../../shared/api/types'

export interface Supplier {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
}
export type SupplierPage = Page<Supplier>
export interface SupplierInput { name: string; email: string | null; phone: string | null; address: string | null }
