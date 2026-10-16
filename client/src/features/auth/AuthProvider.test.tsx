import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'

const tokenKey = 'smart-warehouse-token'
const currentUser = { id: 7, email: 'operator@example.com', role: 'warehouse', is_active: true }

function AuthHarness() {
  const auth = useAuth()
  return (
    <>
      <p>Session: {auth.status}</p>
      <p>Current user: {auth.user?.email ?? 'none'}</p>
      <p>Current role: {auth.user?.role ?? 'none'}</p>
      <button onClick={() => void auth.logout()}>Sign out</button>
      <button onClick={() => void auth.client.request('/users').catch(() => undefined)}>Request users</button>
      <form onSubmit={(event) => {
        event.preventDefault()
        void auth.login({ email: 'operator@example.com', password: 'correct-password' }).catch(() => undefined)
      }}>
        <button type="submit">Sign in</button>
      </form>
    </>
  )
}

function renderAuth(queryClient = new QueryClient()) {
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider><AuthHarness /></AuthProvider>
    </QueryClientProvider>,
  )
  return queryClient
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('AuthProvider', () => {
  it('hydrates the current user from /auth/me before declaring the session authenticated', async () => {
    localStorage.setItem(tokenKey, 'saved-token')
    let finishMe!: (response: Response) => void
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      if (String(input).endsWith('/auth/me')) return new Promise<Response>((resolve) => { finishMe = resolve })
      throw new Error(`Unexpected request: ${String(input)}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderAuth()

    expect(screen.getByText('Session: loading')).toBeInTheDocument()
    expect(screen.getByText('Current user: none')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get('Authorization')).toBe('Bearer saved-token')

    await act(async () => { finishMe(jsonResponse(currentUser)) })
    expect(await screen.findByText('Current user: operator@example.com')).toBeInTheDocument()
    expect(screen.getByText('Current role: warehouse')).toBeInTheDocument()
    expect(screen.getByText('Session: authenticated')).toBeInTheDocument()
  })

  it('does not request /auth/me when no token is stored', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderAuth()

    expect(screen.getByText('Session: anonymous')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('stores a token only after login succeeds and then loads the authoritative current user', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/auth/login')) {
        expect(localStorage.getItem(tokenKey)).toBeNull()
        expect(JSON.parse(String(init?.body))).toEqual({ email: 'operator@example.com', password: 'correct-password' })
        return jsonResponse({ access_token: 'new-token', token_type: 'bearer', user: { ...currentUser, role: 'admin' } })
      }
      if (String(input).endsWith('/auth/me')) {
        expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer new-token')
        return jsonResponse(currentUser)
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderAuth()
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Current user: operator@example.com')).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBe('new-token')
    expect(screen.getByText('Session: authenticated')).toBeInTheDocument()
  })

  it('does not retain a token or user after login fails', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      detail: { code: 'INVALID_CREDENTIALS', message: 'Email or password is incorrect.', fields: null },
    }, 401))
    vi.stubGlobal('fetch', fetchMock)
    localStorage.setItem(tokenKey, 'stale-token')

    renderAuth()
    await screen.findByText('Current user: operator@example.com').catch(() => undefined)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(localStorage.getItem(tokenKey)).toBeNull())
    expect(screen.getByText('Current user: none')).toBeInTheDocument()
    expect(screen.getByText('Session: anonymous')).toBeInTheDocument()
  })

  it('clears authentication and all cached queries on logout', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(currentUser)))
    localStorage.setItem(tokenKey, 'saved-token')
    const queryClient = new QueryClient()
    queryClient.setQueryData(['private-data'], ['secret'])

    renderAuth(queryClient)
    await screen.findByText('Current user: operator@example.com')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(screen.getByText('Session: anonymous')).toBeInTheDocument()
    expect(screen.getByText('Current user: none')).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(queryClient.getQueryData(['private-data'])).toBeUndefined()
  })

  it('invalidates authentication and cached queries when /auth/me returns 401', async () => {
    localStorage.setItem(tokenKey, 'expired-token')
    const queryClient = new QueryClient()
    queryClient.setQueryData(['private-data'], ['secret'])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Sign in again.', fields: null },
    }, 401)))

    renderAuth(queryClient)

    await waitFor(() => expect(screen.getByText('Session: anonymous')).toBeInTheDocument())
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(queryClient.getQueryData(['private-data'])).toBeUndefined()
  })

  it('ignores a delayed 401 from an earlier session even when a later session reuses its token', async () => {
    const user = userEvent.setup()
    const nextUser = { id: 8, email: 'new-operator@example.com', role: 'admin', is_active: true }
    localStorage.setItem(tokenKey, 'reused-token')
    let finishOldUsersRequest!: (response: Response) => void
    let meRequestCount = 0
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) {
        meRequestCount += 1
        return jsonResponse(meRequestCount === 1 ? currentUser : nextUser)
      }
      if (url.endsWith('/auth/login')) {
        return jsonResponse({ access_token: 'reused-token', token_type: 'bearer', user: currentUser })
      }
      if (url.endsWith('/users')) {
        expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer reused-token')
        return new Promise<Response>((resolve) => { finishOldUsersRequest = resolve })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient()

    renderAuth(queryClient)
    await screen.findByText('Current user: operator@example.com')
    await user.click(screen.getByRole('button', { name: 'Request users' }))
    await waitFor(() => expect(finishOldUsersRequest).toBeTypeOf('function'))

    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByText('Current user: new-operator@example.com')
    queryClient.setQueryData(['new-session-data'], ['session B'])

    await act(async () => {
      finishOldUsersRequest(jsonResponse({
        detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Old session expired.', fields: null },
      }, 401))
    })

    expect(screen.getByText('Session: authenticated')).toBeInTheDocument()
    expect(screen.getByText('Current user: new-operator@example.com')).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBe('reused-token')
    expect(queryClient.getQueryData(['new-session-data'])).toEqual(['session B'])
  })

  it('clears the newly issued token and cache when login cannot establish /auth/me', async () => {
    const user = userEvent.setup()
    let finishMe!: (response: Response) => void
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/login')) {
        return jsonResponse({ access_token: 'unverified-token', token_type: 'bearer', user: currentUser })
      }
      if (String(input).endsWith('/auth/me')) {
        return new Promise<Response>((resolve) => { finishMe = resolve })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient()

    renderAuth(queryClient)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(localStorage.getItem(tokenKey)).toBe('unverified-token'))
    queryClient.setQueryData(['unverified-session-data'], ['must be cleared'])

    await act(async () => {
      finishMe(jsonResponse({
        detail: { code: 'PERMISSION_DENIED', message: 'Current user is unavailable.', fields: null },
      }, 403))
    })

    await waitFor(() => expect(screen.getByText('Session: anonymous')).toBeInTheDocument())
    expect(screen.getByText('Current user: none')).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(queryClient.getQueryData(['unverified-session-data'])).toBeUndefined()
  })

  it('preserves token, current user, and cached queries when an API request returns 403', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/me')) return jsonResponse(currentUser)
      return jsonResponse({ detail: { code: 'PERMISSION_DENIED', message: 'Permission denied.', fields: null } }, 403)
    })
    vi.stubGlobal('fetch', fetchMock)
    localStorage.setItem(tokenKey, 'valid-token')
    const queryClient = new QueryClient()
    queryClient.setQueryData(['private-data'], ['secret'])

    renderAuth(queryClient)
    await screen.findByText('Current user: operator@example.com')
    await user.click(screen.getByRole('button', { name: 'Request users' }))

    expect(screen.getByText('Session: authenticated')).toBeInTheDocument()
    expect(screen.getByText('Current user: operator@example.com')).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBe('valid-token')
    expect(queryClient.getQueryData(['private-data'])).toEqual(['secret'])
  })
})
