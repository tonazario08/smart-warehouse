import { afterEach, describe, expect, it } from 'vitest'
import {
  clearPendingMovement,
  movementFingerprint,
  newMovementKey,
  normalizeMovementInput,
  readPendingMovement,
  savePendingMovement,
} from './movementIdempotency'

afterEach(() => { sessionStorage.clear() })

const input = { warehouse_id: 7, product_id: 6, quantity: 5, reference: 'ASN 12', note: null }

describe('movement idempotency keys (D-05)', () => {
  it('generates UUID keys', () => {
    const key = newMovementKey()
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)
    expect(newMovementKey()).not.toBe(key)
  })

  it('normalizes reference and note before fingerprinting', () => {
    expect(normalizeMovementInput({ ...input, reference: '  ASN 12  ', note: '   ' })).toEqual(input)
    expect(movementFingerprint({ ...input, reference: '  ASN 12  ' })).toBe(movementFingerprint(input))
    expect(movementFingerprint({ ...input, quantity: 6 })).not.toBe(movementFingerprint(input))
  })

  it('stores a pending key per account and direction, and clears it', () => {
    savePendingMovement(sessionStorage, 42, 'inbound', 'key-in', input)
    savePendingMovement(sessionStorage, 42, 'outbound', 'key-out', input)
    savePendingMovement(sessionStorage, 7, 'inbound', 'key-other-account', input)
    expect(readPendingMovement(sessionStorage, 42, 'inbound')?.key).toBe('key-in')
    expect(readPendingMovement(sessionStorage, 42, 'outbound')?.key).toBe('key-out')
    expect(readPendingMovement(sessionStorage, 7, 'inbound')?.key).toBe('key-other-account')
    expect(readPendingMovement(sessionStorage, 7, 'outbound')).toBeNull()

    clearPendingMovement(sessionStorage, 42, 'inbound')
    expect(readPendingMovement(sessionStorage, 42, 'inbound')).toBeNull()
    expect(readPendingMovement(sessionStorage, 42, 'outbound')?.key).toBe('key-out')
  })

  it('ignores corrupted or mismatched stored entries', () => {
    sessionStorage.setItem('sw:movement:v1:42:inbound', 'not-json')
    expect(readPendingMovement(sessionStorage, 42, 'inbound')).toBeNull()
    sessionStorage.setItem('sw:movement:v1:42:inbound', JSON.stringify({ key: 'x' }))
    expect(readPendingMovement(sessionStorage, 42, 'inbound')).toBeNull()
    // Fingerprint mismatch: the stored input is not the pending transaction.
    savePendingMovement(sessionStorage, 42, 'inbound', 'key-in', input)
    sessionStorage.setItem(
      'sw:movement:v1:42:inbound',
      JSON.stringify({
        key: 'key-in',
        direction: 'inbound',
        fingerprint: 'tampered',
        input,
      }),
    )
    expect(readPendingMovement(sessionStorage, 42, 'inbound')).toBeNull()
  })
})
