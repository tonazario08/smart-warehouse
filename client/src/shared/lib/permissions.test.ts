import { expect, it } from 'vitest'
import { can, type Permission } from './permissions'

it.each([
  ['catalog:read', [true, true, true]], ['supplier:write', [true, false, false]],
  ['inventory:history:read', [true, true, false]], ['user:manage', [true, false, false]], ['audit:read', [true, false, false]],
  ['product:read', [true, true, true]], ['product:write', [true, false, false]],
  ['supplier:read', [true, true, false]], ['warehouse:read', [true, true, true]],
  ['warehouse:write', [true, false, false]], ['inventory:read', [true, true, true]],
  ['inventory:write', [true, true, false]], ['dashboard:read', [true, false, false]],
  ['purchase_request:read', [true, true, true]], ['purchase_request:create', [false, false, true]],
  ['purchase_request:review', [true, false, false]], ['purchase_request:fulfill', [true, true, false]],
] as const)('%s mirrors backend roles without widening old grants', (permission, expected) => {
  expect(['admin', 'warehouse', 'client'].map(role => can(role as 'admin' | 'warehouse' | 'client', permission as Permission))).toEqual(expected)
})

it('denies missing and unknown roles for each permission', () => {
  const permissions = ['catalog:read', 'purchase_request:read', 'purchase_request:create',
    'purchase_request:review', 'purchase_request:fulfill'] as Permission[]
  for (const permission of permissions) {
    expect(can(null, permission)).toBe(false)
    expect(can(undefined, permission)).toBe(false)
    expect(can('unknown' as 'client', permission)).toBe(false)
  }
})
