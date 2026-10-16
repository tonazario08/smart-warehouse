import { useQuery, useQueryClient } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthProvider'
import { ManagementProvider, useManagementSession } from './ManagementProvider'

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const account = { id: 1, email: 'first@example.com', role: 'admin', is_active: true }
let identity = account
let read: () => Promise<Response> = async () => reply({ value: identity.email })
const caches: ReturnType<typeof useQueryClient>[] = []
function Probe() {
  const { user, client } = useManagementSession()
  const cache = useQueryClient()
  caches.push(cache)
  const result = useQuery({ queryKey: ['private-record'], queryFn: () => client.request<{ value: string }>('/users'), staleTime: Infinity })
  return <><p>{user?.email}</p><p>{result.data?.value ?? (result.error ? result.error.message : 'Đang đọc')}</p>
    <button onClick={() => void client.request('/users/mutation', { method: 'PATCH' }).catch(() => undefined)}>Gửi thay đổi</button></>
}
function Harness() {
  const auth = useAuth()
  return <><button onClick={auth.logout}>Đăng xuất thử</button><button onClick={() => void auth.login('test@example.com', 'synthetic-password')}>Đăng nhập thử</button>
    {auth.user ? <ManagementProvider><Probe /></ManagementProvider> : <p>Chưa đăng nhập</p>}</>
}
function mount() {
  localStorage.setItem('smart-warehouse-token', 'same-test-token')
  vi.stubGlobal('fetch', vi.fn(async input => {
    const url = String(input)
    if (url.endsWith('/auth/login')) return reply({ access_token: 'same-test-token', user: identity })
    if (url.endsWith('/auth/me')) return reply(identity)
    return read()
  }))
  return render(<AuthProvider><Harness /></AuthProvider>)
}
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); caches.length = 0; identity = account; read = async () => reply({ value: identity.email }) })

it('usesActiveAuthWithoutLegacyProvider', async () => {
  mount()
  await waitFor(() => expect(screen.getAllByText('first@example.com')).toHaveLength(2))
})
it('discardsCacheBetweenAccounts and clears detached query data', async () => {
  mount(); await screen.findAllByText('first@example.com')
  await waitFor(() => expect(caches[0].getQueryData(['private-record'])).toBeDefined())
  const oldCache = caches[0]
  fireEvent.click(screen.getByText('Đăng xuất thử'))
  identity = { ...account, id: 2, email: 'second@example.com' }
  fireEvent.click(screen.getByText('Đăng nhập thử'))
  await waitFor(() => expect(screen.getAllByText('second@example.com')).toHaveLength(2))
  expect(screen.queryByText('first@example.com')).not.toBeInTheDocument()
  expect(oldCache.getQueryData(['private-record'])).toBeUndefined()
  expect(caches.at(-1)).not.toBe(oldCache)
})
it('ignoresOldSessionResults', async () => {
  let finish!: (response: Response) => void
  read = () => new Promise<Response>(resolve => { finish = resolve })
  mount(); await screen.findByText('first@example.com')
  fireEvent.click(screen.getByText('Đăng xuất thử'))
  identity = { ...account, email: 'new@example.com', role: 'warehouse' }
  read = async () => reply({ value: 'new-data' })
  fireEvent.click(screen.getByText('Đăng nhập thử'))
  await screen.findByText('new-data')
  await act(async () => { finish(reply({ value: 'obsolete-private-data' })) })
  expect(screen.queryByText('obsolete-private-data')).not.toBeInTheDocument()
})
it('preservesNewSessionAfterDelayed401', async () => {
  mount(); await screen.findAllByText('first@example.com')
  let finish!: (response: Response) => void
  read = () => new Promise<Response>(resolve => { finish = resolve })
  fireEvent.click(screen.getByText('Gửi thay đổi'))
  fireEvent.click(screen.getByText('Đăng xuất thử'))
  read = async () => reply({ value: 'new-data' })
  fireEvent.click(screen.getByText('Đăng nhập thử'))
  await screen.findByText('new-data')
  await act(async () => { finish(reply({ detail: { code: 'AUTHENTICATION_REQUIRED' } }, 401)) })
  expect(localStorage.getItem('smart-warehouse-token')).toBe('same-test-token')
})
it('doesNotLogoutOn403 but clears current session on 401', async () => {
  mount(); await screen.findAllByText('first@example.com')
  read = async () => reply({ detail: { code: 'PERMISSION_DENIED' } }, 403)
  fireEvent.click(screen.getByText('Gửi thay đổi'))
  await act(async () => {})
  expect(localStorage.getItem('smart-warehouse-token')).toBe('same-test-token')
  read = async () => reply({ detail: { code: 'AUTHENTICATION_REQUIRED' } }, 401)
  fireEvent.click(screen.getByText('Gửi thay đổi'))
  await waitFor(() => expect(localStorage.getItem('smart-warehouse-token')).toBeNull())
})

it('discards prior query errors when the same identity logs in with a changed role', async () => {
  read = async () => reply({ detail: { code: 'PERMISSION_DENIED' } }, 403)
  mount()
  await screen.findByText('Bạn không có quyền thực hiện thao tác này.')
  const oldCache = caches.at(-1)!
  fireEvent.click(screen.getByText('Đăng xuất thử'))
  identity = { ...account, role: 'warehouse' }
  read = async () => reply({ value: 'new-role-data' })
  fireEvent.click(screen.getByText('Đăng nhập thử'))
  await screen.findByText('new-role-data')
  expect(screen.queryByText('Bạn không có quyền thực hiện thao tác này.')).not.toBeInTheDocument()
  expect(oldCache.getQueryState(['private-record'])).toBeUndefined()
  expect(caches.at(-1)).not.toBe(oldCache)
})
