export type ManagedRole = 'client' | 'warehouse'

export interface ManagedUser {
  id: number
  email: string
  role: ManagedRole | 'admin'
  is_active: boolean
}

export interface UserPage {
  items: ManagedUser[]
  total: number
  page: number
  page_size: number
}
