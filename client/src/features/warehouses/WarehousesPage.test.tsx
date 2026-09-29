import { afterEach, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderRoleRoute, warehouseRow } from '../../test/renderRoleRoute'
import { warehouseSchema } from './schemas'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items = [warehouseRow], total = items.length, p = 1) => ({ items, total, page: p, page_size: 20 })

it.each(['warehouse', 'client'] as const)('shows warehouses to %s without mutation controls', async (role) => {
  renderRoleRoute('/warehouses', role, (url) => url.includes('/warehouses?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('WH-01')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /create warehouse/i })).not.toBeInTheDocument()
  expect(screen.getByText(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(warehouseRow.created_at)))).toBeInTheDocument()
})

it('matches the backend coordinate bounds and rejects nonnumeric coordinates', () => {
  const values = { code: 'WH-2', name: 'Second', address: 'Bay', latitude: '', longitude: '' }
  expect(warehouseSchema.safeParse({ ...values, latitude: '-90', longitude: '-180' }).success).toBe(true)
  expect(warehouseSchema.safeParse({ ...values, latitude: '90', longitude: '180' }).success).toBe(true)
  expect(warehouseSchema.safeParse({ ...values, latitude: '-90.01', longitude: '0' }).success).toBe(false)
  expect(warehouseSchema.safeParse({ ...values, latitude: '0', longitude: '180.01' }).success).toBe(false)
  expect(warehouseSchema.safeParse({ ...values, latitude: 'east', longitude: '0' }).success).toBe(false)
})

it('searches warehouses and resets pagination to page one', async () => {
  const { fetchMock } = renderRoleRoute('/warehouses', 'client', (url) => url.includes('/warehouses?')
    ? jsonResponse(page([warehouseRow], 25, url.includes('page=2') ? 2 : 1))
    : jsonResponse({}))
  const user = userEvent.setup()
  await screen.findByText('WH-01')
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  await screen.findByText('Page 2 of 2')
  await user.type(screen.getByLabelText('Search warehouses'), 'Main')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('search=Main&page=1') || String(url).includes('page=1&page_size=20&search=Main'))).toBe(true)
})

it('rejects unpaired coordinates before submit and treats empty coordinates as omitted', async () => {
  const { fetchMock } = renderRoleRoute('/warehouses', 'admin', (url) => url.includes('/warehouses?') ? jsonResponse(page([])) : jsonResponse({}))
  const user = userEvent.setup()
  await screen.findByText('No warehouses match this search.')
  await user.click(screen.getByRole('button', { name: /create warehouse/i }))
  await user.type(screen.getByLabelText('Code'), 'W-2')
  await user.type(screen.getByLabelText('Name'), 'Second')
  await user.type(screen.getByLabelText('Address'), 'Bay')
  await user.type(await screen.findByLabelText(/^Latitude/), '10')
  await user.click(screen.getByRole('button', { name: 'Save warehouse' }))
  expect(await screen.findByText(/latitude and longitude.*together/i)).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

it('normalizes code, creates and edits warehouses, confirms delete, and surfaces conflicts', async () => {
  let current = warehouseRow
  const { fetchMock } = renderRoleRoute('/warehouses', 'admin', (url, init) => {
    if (url.includes('/warehouses?')) return jsonResponse(page([current]))
    if (url.endsWith('/warehouses') && init?.method === 'POST') { current = { ...current, code: 'WH-02' }; return jsonResponse(current, 201) }
    if (url.endsWith('/warehouses/7') && init?.method === 'PUT') { current = { ...current, name: 'Updated' }; return jsonResponse(current) }
    if (url.endsWith('/warehouses/7') && init?.method === 'DELETE') return jsonResponse({ detail: { code: 'WAREHOUSE_IN_USE', message: 'Warehouse contains historical inventory.', fields: null } }, 409)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('WH-01')
  await user.click(screen.getByRole('button', { name: /create warehouse/i }))
  const code = screen.getByLabelText('Code')
  await user.type(code, 'wh-02')
  expect(code).toHaveValue('WH-02')
  await user.type(screen.getByLabelText('Name'), 'Second')
  await user.type(screen.getByLabelText('Address'), '2 Bay Street')
  await user.click(screen.getByRole('button', { name: 'Save warehouse' }))
  expect(await screen.findByText('WH-02')).toBeInTheDocument()
  const createRequest = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]
  expect(JSON.parse(String(createRequest?.body))).toMatchObject({ latitude: null, longitude: null })
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/warehouses?')).length).toBeGreaterThan(1)
  await user.click(screen.getByRole('button', { name: /edit warehouse wh-02/i }))
  await user.clear(screen.getByLabelText('Name'))
  await user.type(screen.getByLabelText('Name'), 'Updated')
  await user.click(screen.getByRole('button', { name: 'Save warehouse' }))
  expect(await screen.findByText('Updated', { selector: 'small' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /delete warehouse wh-02/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Confirm delete warehouse' }))
  expect(await screen.findByText('Warehouse contains historical inventory.')).toBeInTheDocument()
})
