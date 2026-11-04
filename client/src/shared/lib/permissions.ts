import type { Role } from '../../types'

export type Permission =
  | 'replenishment:read'
  | 'replenishment:research:read'
  | 'forecast:read'
  | 'forecast:research:read'
  | 'catalog:read'
  | 'supplier:write'
  | 'inventory:history:read'
  | 'user:manage'
  | 'audit:read'
  | 'product:read'
  | 'product:write'
  | 'supplier:read'
  | 'warehouse:read'
  | 'warehouse:write'
  | 'inventory:read'
  | 'inventory:write'
  | 'dashboard:read'
  | 'purchase_request:read'
  | 'purchase_request:create'
  | 'purchase_request:review'
  | 'purchase_request:fulfill'

const permissionRoles: Readonly<Record<Permission, readonly Role[]>> = {
  'replenishment:read': ['admin', 'warehouse'],
  'replenishment:research:read': ['admin'],
  'forecast:read': ['admin', 'warehouse'],
  'forecast:research:read': ['admin'],
  'catalog:read': ['admin', 'warehouse', 'client'],
  'supplier:write': ['admin'],
  'inventory:history:read': ['admin', 'warehouse'],
  'user:manage': ['admin'],
  'audit:read': ['admin'],
  'product:read': ['admin', 'warehouse', 'client'],
  'product:write': ['admin'],
  'supplier:read': ['admin', 'warehouse'],
  'warehouse:read': ['admin', 'warehouse', 'client'],
  'warehouse:write': ['admin'],
  'inventory:read': ['admin', 'warehouse', 'client'],
  'inventory:write': ['admin', 'warehouse'],
  'dashboard:read': ['admin'],
  'purchase_request:read': ['admin', 'warehouse', 'client'],
  'purchase_request:create': ['client'],
  'purchase_request:review': ['admin'],
  'purchase_request:fulfill': ['admin', 'warehouse'],
}

export function can(role: Role | null | undefined, permission: Permission) {
  return role !== null && role !== undefined && permissionRoles[permission].includes(role)
}

export { permissionRoles }
