import { QueryClient, QueryClientProvider, QueryObserver } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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

function renderUsers(
  handler: (url: string, init?: RequestInit) => Response | Promise<Response>,
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  localStorage.setItem('smart-warehouse-token', 'admin-token')
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return Promise.resolve(json(admin))
    return Promise.resolve(handler(url, init))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={queryClient}>
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

it('attaches server field errors to their controls while keeping the domain error visible', async () => {
  renderUsers((url, init) => {
    if (url.includes('/users?')) return json({ items: [], total: 0, page: 1, page_size: 20 })
    if (url.endsWith('/users') && init?.method === 'POST') return json({ detail: {
      code: 'REQUEST_VALIDATION_ERROR', message: 'Request validation failed.',
      fields: { email: ['Email is already in use.'], password: ['Password is not accepted.'] },
    } }, 422)
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('No users found.')
  await user.type(screen.getByLabelText('Email'), 'taken@example.com')
  await user.type(screen.getByLabelText('Password'), 'strong-password-1')
  await user.click(screen.getByRole('button', { name: 'Create user' }))

  const email = screen.getByLabelText('Email')
  const password = screen.getByLabelText('Password')
  expect(await screen.findByRole('alert')).toHaveTextContent('Request validation failed.')
  expect(email).toHaveAttribute('aria-invalid', 'true')
  expect(password).toHaveAttribute('aria-invalid', 'true')
  expect(email).toHaveAccessibleDescription('Email is already in use.')
  expect(password).toHaveAccessibleDescription('Password is not accepted.')
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

it('defaults each new role confirmation from the current role after a successful refetch', async () => {
  let currentRole: 'client' | 'warehouse' = 'client'
  let rosterReads = 0
  const submittedRoles: string[] = []
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const auditFetch = vi.fn().mockResolvedValue({ items: [] })
  const auditObserver = new QueryObserver(queryClient, { queryKey: ['audit', { page: 1 }], queryFn: auditFetch })
  const stopAuditObserver = auditObserver.subscribe(() => undefined)
  await waitFor(() => expect(auditFetch).toHaveBeenCalledTimes(1))
  renderUsers((url, init) => {
    if (url.includes('/users?')) { rosterReads += 1; return json({ items: [{ ...client, role: currentRole }], total: 1, page: 1, page_size: 20 }) }
    if (url.endsWith('/users/2/role') && init?.method === 'PATCH') {
      const requested = (JSON.parse(String(init.body)) as { role: 'client' | 'warehouse' }).role
      submittedRoles.push(requested)
      if (requested === currentRole) return json({ detail: { code: 'USER_ROLE_UNCHANGED', message: 'User already has that role.', fields: null } }, 409)
      currentRole = requested
      return json({ ...client, role: currentRole })
    }
    throw new Error(`Unexpected request: ${url}`)
  }, queryClient)
  const user = userEvent.setup()
  const account = await screen.findByText('client@example.com')
  const row = account.closest('tr') as HTMLTableRowElement

  await user.click(within(row).getByRole('button', { name: 'Change role for client@example.com' }))
  expect(within(row).getByLabelText(/confirm role change for client@example.com/i)).toHaveValue('warehouse')
  await user.click(within(row).getByRole('button', { name: 'Confirm role change' }))
  await waitFor(() => expect(within(row).getByText('warehouse')).toBeInTheDocument())
  expect(rosterReads).toBeGreaterThan(1)

  await user.click(within(row).getByRole('button', { name: 'Change role for client@example.com' }))
  const roleSelect = within(row).getByLabelText(/confirm role change for client@example.com/i)
  expect(roleSelect).toHaveValue('client')
  await user.selectOptions(roleSelect, 'warehouse')
  const readsBeforeRefresh = rosterReads
  await user.click(screen.getByRole('button', { name: 'Refresh roster' }))
  await waitFor(() => expect(rosterReads).toBeGreaterThan(readsBeforeRefresh))
  expect(roleSelect).toHaveValue('warehouse')
  await user.selectOptions(roleSelect, 'client')
  await user.click(within(row).getByRole('button', { name: 'Confirm role change' }))
  await waitFor(() => expect(within(row).getByText('client')).toBeInTheDocument())
  expect(submittedRoles).toEqual(['warehouse', 'client'])
  await waitFor(() => expect(auditFetch).toHaveBeenCalledTimes(3))
  stopAuditObserver()
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
