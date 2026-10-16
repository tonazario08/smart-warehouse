import type { Page } from '../../shared/api/types'

export interface Warehouse {
  id: number; code: string; name: string; address: string; latitude: number | null
  longitude: number | null; created_at: string; updated_at: string
}
export type WarehousePage = Page<Warehouse>
export interface WarehouseInput { code: string; name: string; address: string; latitude: number | null; longitude: number | null }
export interface WarehouseFilters { page: number; pageSize: number; search: string }
