import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { AuthProvider, useAuth } from './AuthProvider'

const tokenKey = 'smart-warehouse-token'
const user = { id: 1, email: 'operator@example.com', role: 'warehouse', is_active: true }
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const deferred = () => { let resolve!: (response: Response) => void; const promise = new Promise<Response>(done => { resolve = done }); return { promise, resolve } }
function Harness() {
  const auth = useAuth()
  return <><p>{auth.user?.email ?? 'anonymous'}</p><p>{auth.loading ? 'loading' : 'settled'}</p><p>{auth.error}</p>
    <button onClick={auth.logout}>logout</button>
    <button onClick={() => void auth.login('operator@example.com', 'test-password')}>login</button>
    <button onClick={() => void api.products(auth.token ?? '').catch(() => undefined)}>catalogue</button></>
}
const mount = () => render(<AuthProvider><Harness /></AuthProvider>)
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

describe('active Figma session lifecycle', () => {
  it.each([401, 403])('clears an unverified login token and reports /auth/me %s failure', async status => {
    vi.stubGlobal('fetch', vi.fn(async input => String(input).endsWith('/auth/login')
      ? reply({ access_token: 'unverified-token', user })
      : reply({ detail: { code: 'PERMISSION_DENIED', message: 'Unavailable', fields: null } }, status)))
    mount()
    fireEvent.click(screen.getByText('login'))
    await screen.findByText('settled')
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(screen.getByText('anonymous')).toBeInTheDocument()
    expect(screen.getByText(/không chính xác|Không thể đăng nhập/)).toBeInTheDocument()
  })
  it.each([403, 'transport'] as const)('preserves stored session on hydration %s failure', async failure => {
    localStorage.setItem(tokenKey, 'valid-token')
    vi.stubGlobal('fetch', vi.fn(async () => {
      if (failure === 'transport') throw new TypeError('offline')
      return reply({ detail: { code: 'PERMISSION_DENIED', message: 'Denied', fields: null } }, 403)
    }))
    mount()
    await screen.findByText('settled')
    expect(localStorage.getItem(tokenKey)).toBe('valid-token')
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })

  it('clears an expired hydrated session', async () => {
    localStorage.setItem(tokenKey, 'expired-token')
    vi.stubGlobal('fetch', vi.fn(async () => reply({ detail: { code: 'INVALID_CREDENTIALS', message: 'Expired', fields: null } }, 401)))
    mount()
    await screen.findByText('settled')
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })

  it('does not resurrect an in-flight login after logout', async () => {
    const login = deferred()
    vi.stubGlobal('fetch', vi.fn(async input => String(input).endsWith('/auth/login') ? login.promise : reply(user)))
    mount()
    fireEvent.click(screen.getByText('login'))
    fireEvent.click(screen.getByText('logout'))
    await act(async () => { login.resolve(reply({ access_token: 'obsolete-token', user })) })
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })

  it('does not publish an old login hydration after logout', async () => {
    const me = deferred()
    vi.stubGlobal('fetch', vi.fn(async input => String(input).endsWith('/auth/login') ? reply({ access_token: 'new-token', user }) : me.promise))
    mount()
    fireEvent.click(screen.getByText('login'))
    await waitFor(() => expect(localStorage.getItem(tokenKey)).toBe('new-token'))
    fireEvent.click(screen.getByText('logout'))
    await act(async () => { me.resolve(reply(user)) })
    expect(localStorage.getItem(tokenKey)).toBeNull()
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })

  it('allows only the newest login attempt to establish a user', async () => {
    const oldLogin = deferred(), newLogin = deferred()
    let count = 0
    vi.stubGlobal('fetch', vi.fn(async input => {
      if (String(input).endsWith('/auth/login')) return ++count === 1 ? oldLogin.promise : newLogin.promise
      return reply(user)
    }))
    mount()
    fireEvent.click(screen.getByText('login'))
    fireEvent.click(screen.getByText('login'))
    await act(async () => { newLogin.resolve(reply({ access_token: 'newest-token', user })) })
    await screen.findByText('operator@example.com')
    await act(async () => { oldLogin.resolve(reply({ access_token: 'old-token', user })) })
    expect(localStorage.getItem(tokenKey)).toBe('newest-token')
  })

  it('ignores a delayed 401 from an earlier session reusing the same token', async () => {
    localStorage.setItem(tokenKey, 'same-token')
    const oldRead = deferred()
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async input => {
      const url = String(input)
      if (url.includes('/products?')) return ++reads === 1 ? oldRead.promise : reply({ detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Expired', fields: null } }, 401)
      if (url.endsWith('/auth/login')) return reply({ access_token: 'same-token', user })
      return reply(user)
    }))
    mount()
    await screen.findByText('operator@example.com')
    fireEvent.click(screen.getByText('catalogue'))
    fireEvent.click(screen.getByText('logout'))
    fireEvent.click(screen.getByText('login'))
    await screen.findByText('operator@example.com')
    await act(async () => { oldRead.resolve(reply({ detail: { code: 'AUTHENTICATION_REQUIRED', message: 'Old request', fields: null } }, 401)) })
    expect(localStorage.getItem(tokenKey)).toBe('same-token')
    expect(screen.getByText('operator@example.com')).toBeInTheDocument()
    fireEvent.click(screen.getByText('catalogue'))
    await waitFor(() => expect(localStorage.getItem(tokenKey)).toBeNull())
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })
})
