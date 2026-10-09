import type { Role } from '../../types'

export type Permission =
  | 'product:read'
  | 'product:write'
  | 'supplier:read'
  | 'warehouse:read'
  | 'warehouse:write'
  | 'inventory:read'
  | 'inventory:write'
  | 'dashboard:read'

const permissionRoles: Readonly<Record<Permission, readonly Role[]>> = {
  'product:read': ['admin', 'warehouse', 'client'],
  'product:write': ['admin'],
  'supplier:read': ['admin', 'warehouse'],
  'warehouse:read': ['admin', 'warehouse', 'client'],
  'warehouse:write': ['admin'],
  'inventory:read': ['admin', 'warehouse', 'client'],
  'inventory:write': ['admin', 'warehouse'],
  'dashboard:read': ['admin'],
}

export function can(role: Role | null | undefined, permission: Permission) {
  return role !== null && role !== undefined && permissionRoles[permission].includes(role)
}

export { permissionRoles }
