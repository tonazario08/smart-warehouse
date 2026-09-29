import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../auth/AuthProvider'

const json = (body: unknown) => new Response(JSON.stringify(body), {
  status: 200, headers: { 'Content-Type': 'application/json' },
})

function renderAudit() {
  localStorage.setItem('smart-warehouse-token', 'admin-token')
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return Promise.resolve(json({ id: 1, email: 'admin@example.com', role: 'admin', is_active: true }))
    if (url.includes('/audit-logs?')) return Promise.resolve(json({
      items: [{
        id: url.includes('page=2') ? 8 : 9, actor_user_id: 1, action: 'user.role_changed',
        target_type: 'user', target_id: 2,
        before_data: { role: 'client', password_hash: 'secret' },
        after_data: { role: '<img src=x onerror=alert(1)>', password: 'secret' },
        created_at: '2026-09-29T09:00:00Z',
      }], total: 21, page: url.includes('page=2') ? 2 : 1, page_size: 20,
    }))
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><MemoryRouter initialEntries={['/audit']}><AppRouter /></MemoryRouter></AuthProvider>
  </QueryClientProvider>)
  return fetchMock
}

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it('renders an append-only ledger with safe before and after facts', async () => {
  renderAudit()
  expect(await screen.findByText('user.role_changed')).toBeInTheDocument()
  expect(screen.getByText('Actor 1')).toBeInTheDocument()
  expect(screen.getByText('user 2')).toBeInTheDocument()
  expect(screen.getByText('client')).toBeInTheDocument()
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument()
  expect(document.querySelector('img')).toBeNull()
  expect(screen.queryByText('secret')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /edit|delete/i })).not.toBeInTheDocument()
  expect(screen.getByText(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date('2026-09-29T09:00:00Z')))).toBeInTheDocument()
})

it('sends action and target filters to the API and keeps pagination bounded', async () => {
  const fetchMock = renderAudit()
  const user = userEvent.setup()
  await screen.findByText('user.role_changed')
  await user.selectOptions(screen.getByLabelText('Action'), 'user.created')
  await user.type(screen.getByLabelText('Target ID'), '2')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('action=user.created') && String(url).includes('target_id=2'))).toBe(true)
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
})
