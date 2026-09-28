import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { navigationForRole } from '../../app/navigation'
import { AuthProvider } from './AuthProvider'

const tokenKey = 'smart-warehouse-token'

function renderRoute(
  path: string,
  role?: 'admin' | 'warehouse' | 'client',
  fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    id: 12, email: 'user@example.com', role, is_active: true,
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })),
) {
  if (role) localStorage.setItem(tokenKey, 'route-token')
  vi.stubGlobal('fetch', fetchMock)

  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}><AppRouter /></MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('role-aware application routes', () => {
  it('redirects an anonymous user from a protected catalogue route to sign in', async () => {
    renderRoute('/products')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary navigation' })).not.toBeInTheDocument()
  })

  it.each([
    ['admin', '/dashboard', 'Overview'],
    ['warehouse', '/inbound', 'Inbound'],
    ['client', '/stock', 'Stock'],
  ] as const)('renders the %s role route at %s inside the accessible shell', async (role, path, navLabel) => {
    renderRoute(path, role)

    expect(await screen.findByRole('heading', { name: navLabel })).toBeInTheDocument()
    expect(screen.getByText(/later phase 1 workstream/i)).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: navLabel })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute('href', '#main-content')
    expect(screen.getByText(/user@example.com/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('shows an explicit forbidden route for an authenticated role without access', async () => {
    renderRoute('/dashboard', 'client')

    expect(await screen.findByRole('heading', { name: 'Permission required' })).toBeInTheDocument()
    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument()
  })

  it('redirects an authenticated visitor away from public sign-in to an allowed landing route', async () => {
    renderRoute('/login', 'warehouse')

    expect(await screen.findByRole('heading', { name: 'Products' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Products' })).toHaveAttribute('aria-current', 'page')
  })

  it('derives navigation only from the current role permission lists', () => {
    expect(navigationForRole('admin').map((item) => item.href)).toEqual([
      '/dashboard', '/users', '/audit', '/categories', '/products', '/suppliers', '/warehouses', '/stock', '/inbound', '/outbound', '/transactions',
    ])
    expect(navigationForRole('warehouse').map((item) => item.href)).toEqual([
      '/categories', '/products', '/suppliers', '/warehouses', '/stock', '/inbound', '/outbound', '/transactions',
    ])
    expect(navigationForRole('client').map((item) => item.href)).toEqual([
      '/categories', '/products', '/warehouses', '/stock',
    ])
  })

  it('provides a public registration page to anonymous visitors', async () => {
    renderRoute('/register')

    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary navigation' })).not.toBeInTheDocument()
  })

  it('returns a user to the protected destination after successful sign in', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/login')) {
        return new Response(JSON.stringify({ access_token: 'fresh-token', token_type: 'bearer', user: { id: 12 } }), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      if (String(input).endsWith('/auth/me')) {
        return new Response(JSON.stringify({ id: 12, email: 'user@example.com', role: 'warehouse', is_active: true }), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })
    renderRoute('/inbound', undefined, fetchMock)

    await user.type(await screen.findByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Inbound' })).toBeInTheDocument()
    expect(localStorage.getItem(tokenKey)).toBe('fresh-token')
  })
})
