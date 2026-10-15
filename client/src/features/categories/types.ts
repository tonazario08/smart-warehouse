import type { Page } from '../../shared/api/types'

export interface Category {
  id: number
  name: string
  parent_id: number | null
}

export type CategoryPage = Page<Category>
export interface CategoryInput { name: string; parent_id: number | null }
