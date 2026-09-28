import type { Role } from '../features/auth/types'

export interface NavigationItem {
  label: string
  href: string
}

export interface RoleNavigationItem extends NavigationItem {
  roles: readonly Role[]
}

const allRoles = ['admin', 'warehouse', 'client'] as const
const adminAndWarehouse = ['admin', 'warehouse'] as const
const adminOnly = ['admin'] as const

export const navigationItems: readonly RoleNavigationItem[] = [
  { label: 'Overview', href: '/dashboard', roles: adminOnly },
  { label: 'Users', href: '/users', roles: adminOnly },
  { label: 'Audit', href: '/audit', roles: adminOnly },
  { label: 'Categories', href: '/categories', roles: allRoles },
  { label: 'Products', href: '/products', roles: allRoles },
  { label: 'Suppliers', href: '/suppliers', roles: adminAndWarehouse },
  { label: 'Warehouses', href: '/warehouses', roles: allRoles },
  { label: 'Stock', href: '/stock', roles: allRoles },
  { label: 'Inbound', href: '/inbound', roles: adminAndWarehouse },
  { label: 'Outbound', href: '/outbound', roles: adminAndWarehouse },
  { label: 'Transactions', href: '/transactions', roles: adminAndWarehouse },
]

export function navigationForRole(role: Role) {
  return navigationItems.filter((item) => item.roles.includes(role))
}

export function landingPathForRole(role: Role) {
  return role === 'admin' ? '/dashboard' : '/products'
}
