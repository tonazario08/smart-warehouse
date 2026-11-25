import { afterEach, expect, it, vi } from 'vitest'
import { advanceApiSession, onApiUnauthorized } from '../../api'
import { createManagementApiClient } from './createManagementApiClient'
import { ApiError } from './ApiError'

const reply = (status: number, detail: unknown) => new Response(JSON.stringify({ detail }), { status })
afterEach(() => vi.unstubAllGlobals())

it('uses the current bearer token and preserves mutation payloads and 204 responses', async () => {
  let token = 'first-test-token'
  const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(null, { status: 204 }))
  vi.stubGlobal('fetch', fetcher)
  const client = createManagementApiClient(() => token)
  token = 'current-test-token'
  expect(await client.request('/categories/7', { method: 'DELETE' })).toBeUndefined()
  await client.request('/users', { method: 'POST', body: JSON.stringify({ email: 'test@example.com', role: 'client' }) })
  expect(new Headers(fetcher.mock.calls[0]?.[1]?.headers).get('Authorization')).toBe('Bearer current-test-token')
  expect(fetcher.mock.calls[1]?.[1]?.body).toBe('{"email":"test@example.com","role":"client"}')
})

it.each([409, 422])('sanitizes %s errors while preserving status, code and field associations', async status => {
  vi.stubGlobal('fetch', vi.fn(async () => reply(status, { code: 'USER_EMAIL_CONFLICT', message: 'internal secret diagnostic', fields: { email: ['raw internal payload'] } })))
  const error = await createManagementApiClient(() => 'test-token').request('/users').catch(cause => cause)
  expect(error).toBeInstanceOf(ApiError)
  if (!(error instanceof ApiError)) throw new Error('Expected a structured management API error')
  expect(error).toMatchObject({ status, code: 'USER_EMAIL_CONFLICT' })
  expect(error.message).toMatch(/Email|Dữ liệu/)
  expect(error.message).not.toContain('internal')
  expect(error.fields?.email).not.toContain('raw internal payload')
  expect(JSON.stringify(error.detail)).not.toContain('secret')
})

it('delegates current-session 401 invalidation to the central transport', async () => {
  const unauthorized = vi.fn()
  const stop = onApiUnauthorized(unauthorized)
  vi.stubGlobal('fetch', vi.fn(async () => reply(401, { code: 'AUTHENTICATION_REQUIRED', fields: null })))
  try {
    await expect(createManagementApiClient(() => 'active-test-token').request('/users')).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).toHaveBeenCalledWith('active-test-token', expect.any(Number))
  } finally { stop() }
})

it('does not invalidate a later same-token session after delayed 401', async () => {
  let resolve!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done })))
  const unauthorized = vi.fn(), stop = onApiUnauthorized(unauthorized)
  try {
    const pending = createManagementApiClient(() => 'same-test-token').request('/users').catch(cause => cause)
    advanceApiSession()
    resolve(reply(401, { code: 'AUTHENTICATION_REQUIRED' }))
    expect(await pending).toMatchObject({ status: 401, staleSession: true })
    expect(unauthorized).not.toHaveBeenCalled()
  } finally { stop() }
})

it('does not invalidate on 403 and uses safe Vietnamese network errors', async () => {
  const unauthorized = vi.fn(), stop = onApiUnauthorized(unauthorized)
  try {
    vi.stubGlobal('fetch', vi.fn(async () => reply(403, { message: 'Forbidden' })))
    await expect(createManagementApiClient(() => 'test-token').request('/users')).rejects.toMatchObject({ status: 403, message: 'Bạn không có quyền thực hiện thao tác này.' })
    expect(unauthorized).not.toHaveBeenCalled()
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('internal transport detail') }))
    await expect(createManagementApiClient(() => 'test-token').request('/users')).rejects.toThrow('Không thể kết nối')
  } finally { stop() }
})
