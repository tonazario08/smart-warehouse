import { afterEach, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { categoryRow, jsonResponse, renderRoleRoute } from '../../test/renderRoleRoute'
import { QueryClient } from '@tanstack/react-query'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items = [categoryRow], total = items.length, pageNumber = 1) => ({ items, total, page: pageNumber, page_size: 20 })

it.each(['warehouse', 'client'] as const)('allows %s to read categories without admin controls', async (role) => {
  const { fetchMock } = renderRoleRoute('/categories', role, (url) => url.includes('/categories?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /create category/i })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/categories?page=1&page_size=20'))).toBe(true)
})

it('creates, edits, confirms deletion, and invalidates category and product lookups', async () => {
  let current = categoryRow
  let reads = 0
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['products', 'lookup'], page())
  const { fetchMock } = renderRoleRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) { reads += 1; return jsonResponse(page([current])) }
    if (url.includes('/categories') && init?.method === 'POST') { current = { ...current, name: 'Fasteners' }; return jsonResponse(current, 201) }
    if (url.endsWith('/categories/4') && init?.method === 'PUT') { current = { ...current, name: 'Bolts' }; return jsonResponse(current) }
    if (url.endsWith('/categories/4') && init?.method === 'DELETE') return new Response(null, { status: 204 })
    throw new Error(`Unexpected request ${url}`)
  }, queryClient)
  const user = userEvent.setup()
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /create category/i }))
  await user.type(screen.getByLabelText('Name'), 'Fasteners')
  await user.click(screen.getByRole('button', { name: 'Save category' }))
  expect(await screen.findByText('Fasteners')).toBeInTheDocument()
  expect(reads).toBeGreaterThan(1)
  expect(queryClient.getQueryState(['products', 'lookup'])?.isInvalidated).toBe(true)
  await user.click(screen.getByRole('button', { name: /edit category fasteners/i }))
  await user.clear(screen.getByLabelText('Name'))
  await user.type(screen.getByLabelText('Name'), 'Bolts')
  await user.click(screen.getByRole('button', { name: 'Save category' }))
  expect(await screen.findByText('Bolts')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /delete category bolts/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Confirm delete category' }))
  expect(await screen.findByText('Category deleted.')).toBeInTheDocument()
})

it('paginates categories and offers retry after a failed read', async () => {
  let failed = true
  const { fetchMock } = renderRoleRoute('/categories', 'client', (url) => {
    if (url.includes('/categories?') && failed) return jsonResponse({ detail: { code: 'READ_FAILED', message: 'Catalogue unavailable.', fields: null } }, 503)
    return jsonResponse(page([categoryRow], 21, url.includes('page=2') ? 2 : 1))
  })
  const user = userEvent.setup()
  expect(await screen.findByRole('alert')).toHaveTextContent('Catalogue unavailable.')
  failed = false
  await user.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/categories?page=2&page_size=20'))).toBe(true)
})

it('associates backend parent_id errors with the parent selector and keeps the domain error visible', async () => {
  renderRoleRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) return jsonResponse(page([categoryRow]))
    if (url.endsWith('/categories') && init?.method === 'POST') return jsonResponse({ detail: { code: 'CATEGORY_PARENT_INVALID', message: 'Parent category was rejected.', fields: { parent_id: ['Select an existing parent.'] } } }, 422)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Hardware')
  await user.click(screen.getByRole('button', { name: /create category/i }))
  await user.type(screen.getByLabelText('Name'), 'Child')
  await user.selectOptions(screen.getByLabelText('Parent category'), '4')
  await user.click(screen.getByRole('button', { name: 'Save category' }))
  expect(await screen.findByText('Parent category was rejected.')).toBeInTheDocument()
  expect(screen.getByLabelText(/^Parent category/)).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText(/^Parent category/)).toHaveAccessibleDescription('Select an existing parent.')
})

it('disables category submission and ignores a second click while create is pending', async () => {
  let resolveCreate: (() => void) | undefined
  let posts = 0
  renderRoleRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) return jsonResponse(page([categoryRow]))
    if (url.endsWith('/categories') && init?.method === 'POST') {
      posts += 1
      return new Promise((resolve) => { resolveCreate = () => resolve(jsonResponse({ ...categoryRow, name: 'Bolts' }, 201)) })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Hardware')
  await user.click(screen.getByRole('button', { name: /create category/i }))
  await user.type(screen.getByLabelText('Name'), 'Bolts')
  await user.click(screen.getByRole('button', { name: 'Save category' }))
  const saving = await screen.findByRole('button', { name: /saving/i })
  expect(saving).toBeDisabled()
  await user.click(saving)
  expect(posts).toBe(1)
  resolveCreate?.()
})
