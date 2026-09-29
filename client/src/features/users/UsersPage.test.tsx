import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../auth/AuthProvider'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
const admin = { id: 1, email: 'admin@example.com', role: 'admin', is_active: true }
const client = { id: 2, email: 'client@example.com', role: 'client', is_active: true }
const warehouse = { id: 3, email: 'worker@example.com', role: 'warehouse', is_active: false }

function renderUsers(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  localStorage.setItem('smart-warehouse-token', 'admin-token')
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return Promise.resolve(json(admin))
    return Promise.resolve(handler(url, init))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><MemoryRouter initialEntries={['/users']}><AppRouter /></MemoryRouter></AuthProvider>
  </QueryClientProvider>)
  return fetchMock
}

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it('lists paginated users and never offers admin account creation', async () => {
  const fetchMock = renderUsers((url) => json(url.includes('page=2')
    ? { items: [warehouse], total: 21, page: 2, page_size: 20 }
    : { items: [admin, client], total: 21, page: 1, page_size: 20 }))
  const user = userEvent.setup()
  expect(await screen.findByText('client@example.com')).toBeInTheDocument()
  const role = screen.getByLabelText('Role', { selector: '#create-user-role' })
  expect(within(role).queryByRole('option', { name: /admin/i })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /change role for admin@example.com/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /change status for admin@example.com/i })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('worker@example.com')).toBeInTheDocument()
  expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/users?page=2&page_size=20'))).toBe(true)
})

it('validates a new user, creates a managed account, and refreshes the roster', async () => {
  let created = false
  let rosterReads = 0
  const fetchMock = renderUsers((url, init) => {
    if (url.includes('/users?')) { rosterReads += 1; return json({ items: created ? [client] : [], total: created ? 1 : 0, page: 1, page_size: 20 }) }
    if (url.endsWith('/users') && init?.method === 'POST') { created = true; return json(client, 201) }
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('No users found.')
  await user.click(screen.getByRole('button', { name: 'Create user' }))
  expect(screen.getByText(/valid email/i)).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  await user.type(screen.getByLabelText('Email'), 'client@example.com')
  await user.type(screen.getByLabelText('Password'), 'strong-password-1')
  await user.click(screen.getByRole('button', { name: 'Create user' }))
  expect(await screen.findByText('client@example.com')).toBeInTheDocument()
  expect(rosterReads).toBeGreaterThan(1)
})

it('requires a visible confirmation for role changes and surfaces domain failures', async () => {
  const fetchMock = renderUsers((url, init) => {
    if (url.includes('/users?')) return json({ items: [client], total: 1, page: 1, page_size: 20 })
    if (url.endsWith('/users/2/role') && init?.method === 'PATCH') return json({ detail: { code: 'USER_ROLE_UNCHANGED', message: 'User already has that role.', fields: null } }, 409)
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('client@example.com')
  await user.click(screen.getByRole('button', { name: 'Change role for client@example.com' }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
  expect(screen.getByLabelText(/confirm role change for client@example.com/i)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Confirm role change' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('User already has that role.')
  expect(screen.getByText('admin@example.com')).toBeInTheDocument()
})

it('confirms status changes and refreshes the roster and audit cache', async () => {
  let changed = false
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['audit', { page: 1 }], { items: ['stale'] })
  localStorage.setItem('smart-warehouse-token', 'admin-token')
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return Promise.resolve(json(admin))
    if (url.includes('/users?')) return Promise.resolve(json({ items: [{ ...client, is_active: !changed }], total: 1, page: 1, page_size: 20 }))
    if (url.endsWith('/users/2/status') && init?.method === 'PATCH') { changed = true; return Promise.resolve(json({ ...client, is_active: false })) }
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={queryClient}>
    <AuthProvider><MemoryRouter initialEntries={['/users']}><AppRouter /></MemoryRouter></AuthProvider>
  </QueryClientProvider>)
  const user = userEvent.setup()
  await screen.findByText('client@example.com')
  await user.click(screen.getByRole('button', { name: 'Deactivate client@example.com' }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Confirm deactivation' }))
  expect(await screen.findByText('Inactive')).toBeInTheDocument()
  expect(queryClient.getQueryState(['audit', { page: 1 }])?.isInvalidated).toBe(true)
})
