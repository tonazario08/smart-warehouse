import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from './ApiClient'

describe('ApiClient', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('preserves forbidden domain details without clearing the session', async () => {
    const onUnauthorized = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'PERMISSION_DENIED', message: 'Permission denied.', fields: { role: ['Not allowed.'] } },
    }), { status: 403, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const client = new ApiClient('/api/v1', () => 'valid-token', onUnauthorized)

    await expect(client.request('/users')).rejects.toMatchObject({
      status: 403,
      code: 'PERMISSION_DENIED',
      message: 'Permission denied.',
      fields: { role: ['Not allowed.'] },
    })
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('calls the unauthorized handler exactly once for a 401 response', async () => {
    const onUnauthorized = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Sign in again.', fields: null },
    }), { status: 401, headers: { 'Content-Type': 'application/json' } })))
    const client = new ApiClient('/api/v1', () => 'expired-token', onUnauthorized)

    await expect(client.request('/users')).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('sends JSON requests with the current bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 8 }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const client = new ApiClient('/api/v1', () => 'active-token', vi.fn())

    await expect(client.request<{ id: number }>('/users', {
      method: 'POST',
      body: JSON.stringify({ email: 'worker@example.com' }),
    })).resolves.toEqual({ id: 8 })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/users', expect.objectContaining({ method: 'POST' }))
    const requestHeaders = new Headers(fetchMock.mock.calls[0]?.[1]?.headers)
    expect(requestHeaders.get('Content-Type')).toBe('application/json')
    expect(requestHeaders.get('Authorization')).toBe('Bearer active-token')
  })
})
