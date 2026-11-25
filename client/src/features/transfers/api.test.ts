import { afterEach, expect, it, vi } from 'vitest'
import { advanceApiSession, ApiError, onApiUnauthorized } from '../../api'
import { createTransfer, getTransfer, getTransferByKey, listTransfers } from './api'
import { validateTransfer } from './schemas'

const input = { source_warehouse_id: 1, destination_warehouse_id: 2, product_id: 3, quantity: 4, reference: null, note: null }
const key = 'c5ee13a1-2aa4-4d0d-ac57-ec4ed64b76bc'
afterEach(() => vi.unstubAllGlobals())

it('sends the exact confirmed payload and UUID through the active bearer transport', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 8, ...input }), { status: 201 }))
  vi.stubGlobal('fetch', fetcher)
  expect((await createTransfer('current-token', key, input)).id).toBe(8)
  const [url, options] = fetcher.mock.calls[0]
  expect(url).toMatch(/\/api\/v1\/transfers$/)
  expect(options.method).toBe('POST')
  expect(options.headers).toMatchObject({ Authorization: 'Bearer current-token', 'Idempotency-Key': key })
  expect(JSON.parse(options.body)).toEqual(input)
})

it('never automatically retries a failed POST and keeps the body and key on explicit retry', async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ detail: { code: 'TRANSFER_RETRY_REQUIRED', message: 'safe', fields: null } }), { status: 503 }))
  vi.stubGlobal('fetch', fetcher)
  await expect(createTransfer('token', key, input)).rejects.toMatchObject({ status: 503, code: 'TRANSFER_RETRY_REQUIRED' })
  expect(fetcher).toHaveBeenCalledTimes(1)
  await expect(createTransfer('token', key, input)).rejects.toBeInstanceOf(ApiError)
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect(fetcher.mock.calls[1][1]).toEqual(fetcher.mock.calls[0][1])
  expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe(key)
})

it('encodes supported conjunctive server filters, pages, detail and own-key routes', async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response('{}'))
  vi.stubGlobal('fetch', fetcher)
  await listTransfers('token', { source_warehouse_id: 1, destination_warehouse_id: 2, product_id: 3, created_from: '2026-10-17T00:00:00+07:00', page: 2, page_size: 20 })
  const url = new URL(fetcher.mock.calls[0][0])
  expect(Object.fromEntries(url.searchParams)).toEqual({ source_warehouse_id: '1', destination_warehouse_id: '2', product_id: '3', created_from: '2026-10-17T00:00:00+07:00', page: '2', page_size: '20' })
  await getTransfer('token', 9)
  expect(fetcher.mock.calls[1][0]).toMatch(/\/transfers\/9$/)
  await getTransferByKey('token', key)
  expect(fetcher.mock.calls[2][0]).toMatch(new RegExp('/transfers/by-key/' + key + '$'))
})

it('inherits current401 invalidation, stale401 suppression and403 retention', async () => {
  let finish!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve })))
  const invalidated = vi.fn(), unsubscribe = onApiUnauthorized(invalidated)
  const pending = getTransfer('old-token', 9)
  advanceApiSession()
  finish(new Response('{}', { status: 401 }))
  await expect(pending).rejects.toMatchObject({ staleSession: true, status: 401 })
  expect(invalidated).not.toHaveBeenCalled()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })))
  await expect(getTransfer('current-token', 9)).rejects.toMatchObject({ staleSession: false })
  expect(invalidated).toHaveBeenCalledTimes(1)
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 403 })))
  await expect(getTransfer('current-token', 9)).rejects.toMatchObject({ status: 403 })
  expect(invalidated).toHaveBeenCalledTimes(1)
  unsubscribe()
})

const draft = { source: '1', destination: '2', product: '3', quantity: '4', reference: '  CK-01  ', note: ' \n' }
it('normalizes confirmed input once without actor or purpose metadata', () => {
  expect(validateTransfer(draft)).toEqual({ input: { ...input, reference: 'CK-01' } })
})
it.each(['', '0', '-1', '1.5', '2147483648', 'true'])('rejects invalid integer input %s before confirmation', quantity => {
  expect(validateTransfer({ ...draft, quantity }).error).toBeTruthy()
})
it('rejects identical warehouses, invalid IDs and overlong text', () => {
  for (const change of [{ destination: '1' }, { source: '0' }, { product: '1.5' }, { reference: 'x'.repeat(121) }, { note: 'x'.repeat(2001) }]) {
    expect(validateTransfer({ ...draft, ...change }).error).toBeTruthy()
  }
})
