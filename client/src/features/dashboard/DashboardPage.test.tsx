import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AppRouter } from '../../test/LegacyAppRouter'
import { AuthProvider } from '../auth/AuthProvider'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})

function renderDashboard(stats: () => Promise<Response>) {
  localStorage.setItem('smart-warehouse-token', 'admin-token')
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input).endsWith('/auth/me')) return Promise.resolve(json({ id: 1, email: 'admin@example.com', role: 'admin', is_active: true }))
    if (String(input).endsWith('/dashboard/stats')) return stats()
    throw new Error(`Unexpected request: ${String(input)}`)
  }))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><MemoryRouter initialEntries={['/dashboard']}><AppRouter /></MemoryRouter></AuthProvider>
  </QueryClientProvider>)
}

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it('shows an accessible loading state and labelled warehouse metrics', async () => {
  let resolveStats!: (response: Response) => void
  renderDashboard(() => new Promise((resolve) => { resolveStats = resolve }))
  expect(await screen.findByRole('status', { name: /loading warehouse status/i })).toBeInTheDocument()
  await waitFor(() => expect(resolveStats).toBeTypeOf('function'))
  resolveStats(json({ product_count: 12, total_stock: 420, low_stock_count: 3 }))
  expect(await screen.findByText('420')).toBeInTheDocument()
  expect(screen.getByLabelText('Warehouse status')).toHaveTextContent('Products')
  expect(screen.getByText('Total stock')).toBeInTheDocument()
  expect(screen.getByText('Low-stock balances')).toBeInTheDocument()
})

it('shows the server error and retries without ending the admin session', async () => {
  let attempts = 0
  renderDashboard(() => Promise.resolve(++attempts === 1
    ? json({ detail: { code: 'NO_STATS', message: 'Warehouse totals unavailable.', fields: null } }, 403)
    : json({ product_count: 0, total_stock: 0, low_stock_count: 0 })))
  expect(await screen.findByRole('alert')).toHaveTextContent('Warehouse totals unavailable.')
  expect(screen.getByText('admin@example.com')).toBeInTheDocument()
  expect(localStorage.getItem('smart-warehouse-token')).toBe('admin-token')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('Total stock')).toBeInTheDocument()
  expect(screen.getAllByText('0')).toHaveLength(3)
})
