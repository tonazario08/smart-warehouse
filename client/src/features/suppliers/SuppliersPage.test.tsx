import { afterEach, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderRoleRoute, supplierRow } from '../../test/renderRoleRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items = [supplierRow], total = items.length, p = 1) => ({ items, total, page: p, page_size: 20 })

it('allows warehouse but routes clients away from suppliers', async () => {
  renderRoleRoute('/suppliers', 'warehouse', (url) => url.includes('/suppliers?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('Northwind')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /create supplier/i })).not.toBeInTheDocument()
})

it('creates, updates, confirms deletion, maps backend errors, and prevents duplicate submits', async () => {
  let current = supplierRow
  let gate: (() => void) | undefined
  const { fetchMock } = renderRoleRoute('/suppliers', 'admin', (url, init) => {
    if (url.includes('/suppliers?')) return jsonResponse(page([current]))
    if (url.endsWith('/suppliers') && init?.method === 'POST') return new Promise((resolve) => { gate = () => { current = { ...current, name: 'Contoso' }; resolve(jsonResponse(current, 201)) } })
    if (url.endsWith('/suppliers/5') && init?.method === 'PUT') { current = { ...current, name: 'Fabrikam' }; return jsonResponse(current) }
    if (url.endsWith('/suppliers/5') && init?.method === 'DELETE') return new Response(null, { status: 204 })
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  expect(await screen.findByText('Northwind')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /create supplier/i }))
  expect(await screen.findByRole('form', { name: 'Create supplier' })).toBeInTheDocument()
  await user.type(screen.getByLabelText('Name'), 'Contoso')
  await user.click(screen.getByRole('button', { name: 'Save supplier' }))
  const save = screen.getByRole('button', { name: /saving/i })
  expect(save).toBeDisabled()
  await user.click(save)
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  gate?.()
  expect(await screen.findByText('Contoso')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /edit supplier contoso/i }))
  await user.clear(screen.getByLabelText('Name'))
  await user.type(screen.getByLabelText('Name'), 'Fabrikam')
  await user.click(screen.getByRole('button', { name: 'Save supplier' }))
  expect(await screen.findByText('Fabrikam')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /delete supplier fabrikam/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Confirm delete supplier' }))
  expect(await screen.findByText('Supplier deleted.')).toBeInTheDocument()
})

it('applies search, resets pagination, and shows backend conflict details', async () => {
  let currentPage = 2
  const { fetchMock } = renderRoleRoute('/suppliers', 'admin', (url, init) => {
    if (url.includes('/suppliers?')) return jsonResponse(page([supplierRow], 22, url.includes('page=1') ? 1 : currentPage))
    if (url.endsWith('/suppliers') && init?.method === 'POST') return jsonResponse({ detail: { code: 'SUPPLIER_CONFLICT', message: 'Supplier email already exists.', fields: { email: ['Email already exists.'] } } }, 409)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Northwind')
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  await screen.findByText('Page 2 of 2')
  await user.type(screen.getByLabelText('Search suppliers'), 'North')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('search=North'))).toBe(true)
  await user.click(screen.getByRole('button', { name: /create supplier/i }))
  await user.type(screen.getByLabelText('Name'), 'Duplicate')
  await user.type(screen.getByLabelText('Email'), 'dup@example.com')
  await user.click(screen.getByRole('button', { name: 'Save supplier' }))
  expect(await screen.findByText('Supplier email already exists.')).toBeInTheDocument()
  expect(screen.getByLabelText(/^Email/)).toHaveAccessibleDescription('Email already exists.')
})
