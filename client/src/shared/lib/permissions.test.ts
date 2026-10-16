import { expect, it } from 'vitest'
import { can, type Permission } from './permissions'

it.each([
  ['catalog:read', [true, true, true]], ['supplier:write', [true, false, false]],
  ['inventory:history:read', [true, true, false]], ['user:manage', [true, false, false]], ['audit:read', [true, false, false]],
] as const)('%s mirrors backend roles without widening old grants', (permission, expected) => {
  expect(['admin', 'warehouse', 'client'].map(role => can(role as 'admin' | 'warehouse' | 'client', permission as Permission))).toEqual(expected)
})
