/**
 * Actor- and direction-scoped idempotency keys for inbound/outbound creates.
 *
 * Approved decision D-05: the key is a UUID generated with
 * `crypto.randomUUID()` and kept in `sessionStorage` while the outcome of a
 * create is unknown, so a retry after a timeout, a lost connection, or a
 * page reload reuses the exact same key and the server replays the original
 * record instead of creating a duplicate. The stored record holds only the
 * key, the movement direction, and the normalized movement input needed to
 * recognize the same transaction again; it never holds credentials, tokens,
 * or any other sensitive data. A key is never reused for a different
 * transaction: a stored entry whose fingerprint does not match the current
 * input is discarded and a fresh key is generated.
 */

export type MovementDirection = 'inbound' | 'outbound'

export interface MovementInputLike {
  warehouse_id: number
  product_id: number
  quantity: number
  reference: string | null
  note: string | null
}

export interface PendingMovement {
  key: string
  direction: MovementDirection
  fingerprint: string
  input: MovementInputLike
}

export type PendingMovementStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const STORAGE_PREFIX = 'sw:movement:v1'

/** The tab session store when one exists (browser); null on the server or in Node. */
export function browserSessionStorage(): PendingMovementStorage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage
  } catch {
    return null
  }
}

export function newMovementKey(): string {
  return crypto.randomUUID()
}

export function normalizeMovementInput(
  input: Omit<MovementInputLike, 'reference' | 'note'> & {
    reference?: string | null
    note?: string | null
  },
): MovementInputLike {
  const text = (value: string | null | undefined) => {
    const trimmed = typeof value === 'string' ? value.trim() : ''
    return trimmed ? trimmed : null
  }
  return {
    warehouse_id: input.warehouse_id,
    product_id: input.product_id,
    quantity: input.quantity,
    reference: text(input.reference),
    note: text(input.note),
  }
}

/** Stable fingerprint of the normalized body; identical input, identical value. */
export function movementFingerprint(input: MovementInputLike): string {
  const normalized = normalizeMovementInput(input)
  return JSON.stringify([
    normalized.warehouse_id,
    normalized.product_id,
    normalized.quantity,
    normalized.reference,
    normalized.note,
  ])
}

export function pendingMovementStorageKey(
  accountId: number | string,
  direction: MovementDirection,
): string {
  return `${STORAGE_PREFIX}:${accountId}:${direction}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function savePendingMovement(
  storage: PendingMovementStorage | null,
  accountId: number | string,
  direction: MovementDirection,
  key: string,
  input: MovementInputLike,
): void {
  if (!storage) return
  const normalized = normalizeMovementInput(input)
  const pending: PendingMovement = {
    key,
    direction,
    fingerprint: movementFingerprint(normalized),
    input: normalized,
  }
  try {
    storage.setItem(pendingMovementStorageKey(accountId, direction), JSON.stringify(pending))
  } catch {
    // Storage can be unavailable (private mode, disabled cookies). The key
    // still lives in memory for this page; only reload recovery is lost.
  }
}

export function readPendingMovement(
  storage: PendingMovementStorage | null,
  accountId: number | string,
  direction: MovementDirection,
): PendingMovement | null {
  if (!storage) return null
  let raw: string | null
  try {
    raw = storage.getItem(pendingMovementStorageKey(accountId, direction))
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) return null
    const input = parsed.input
    if (
      typeof parsed.key !== 'string' ||
      !parsed.key ||
      parsed.direction !== direction ||
      typeof parsed.fingerprint !== 'string' ||
      !isRecord(input) ||
      typeof input.warehouse_id !== 'number' ||
      typeof input.product_id !== 'number' ||
      typeof input.quantity !== 'number' ||
      !(input.reference === null || typeof input.reference === 'string') ||
      !(input.note === null || typeof input.note === 'string')
    ) {
      return null
    }
    const normalized = normalizeMovementInput(input as unknown as MovementInputLike)
    if (movementFingerprint(normalized) !== parsed.fingerprint) return null
    return {
      key: parsed.key,
      direction,
      fingerprint: parsed.fingerprint,
      input: normalized,
    }
  } catch {
    return null
  }
}

export function clearPendingMovement(
  storage: PendingMovementStorage | null,
  accountId: number | string,
  direction: MovementDirection,
): void {
  if (!storage) return
  try {
    storage.removeItem(pendingMovementStorageKey(accountId, direction))
  } catch {
    // Nothing to recover if storage is unavailable.
  }
}
