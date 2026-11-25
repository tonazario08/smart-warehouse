import { afterEach, expect, it, vi } from 'vitest'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { categoryRow, jsonResponse, renderManagementRoute } from '../../test/renderManagementRoute'
import { QueryClient } from '@tanstack/react-query'
import type { Category } from './types'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items: Category[] = [categoryRow], total = items.length, pageNumber = 1) => ({ items, total, page: pageNumber, page_size: 20 })

it('loads parents beyond the first 100 and excludes the edited category itself', async () => {
  const { fetchMock } = renderManagementRoute('/categories', 'admin', url => {
    const params = new URL(url).searchParams
    if (params.get('page_size') === '100') return jsonResponse({ items: params.get('page') === '2' ? [{ id: 101, name: 'Danh mục trang hai', parent_id: null }] : Array.from({ length: 100 }, (_, i) => ({ id: i + 1, name: 'Danh mục ' + (i + 1), parent_id: null })), total: 101, page: Number(params.get('page')), page_size: 100 })
    return jsonResponse(page([{ ...categoryRow, parent_id: 101 }]))
  })
  await screen.findByText('Danh mục trang hai')
  await userEvent.click(screen.getByRole('button', { name: 'Sửa danh mục Hardware' }))
  const select = screen.getByLabelText('Danh mục cha')
  expect(within(select).getByRole('option', { name: 'Danh mục trang hai' })).toHaveValue('101')
  expect(within(select).queryByRole('option', { name: /^Danh mục 4$/ })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('page=2&page_size=100'))).toBe(true)
})

it('keeps table and confirmation on in-use deletion, allows retry and recovers an emptied last page', async () => {
  let removed = false, rejected = true
  renderManagementRoute('/categories', 'admin', (url, init) => {
    if (init?.method === 'DELETE') {
      if (rejected) return jsonResponse({ detail: { code: 'CATEGORY_IN_USE' } }, 409)
      removed = true; return new Response(null, { status: 204 })
    }
    const p = new URL(url).searchParams.get('page')
    return jsonResponse(page(p === '2' && removed ? [] : [categoryRow], removed ? 20 : 21, Number(p)))
  })
  await screen.findByText('Hardware')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 2')
  await userEvent.click(screen.getByRole('button', { name: 'Xóa danh mục Hardware' }))
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận xóa danh mục' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể xóa danh mục đang được sử dụng.')
  expect(screen.getByRole('table', { name: 'Danh sách danh mục' })).toBeInTheDocument()
  rejected = false
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận xóa danh mục' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(await screen.findByText('Trang 1 / 1')).toBeInTheDocument()
  expect(screen.getByText('Hardware')).toBeInTheDocument()
})

it.each(['warehouse', 'client'] as const)('allows %s to read categories without admin controls', async (role) => {
  const { fetchMock } = renderManagementRoute('/categories', role, (url) => url.includes('/categories?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Tạo danh mục/i })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/categories?page=1&page_size=20'))).toBe(true)
})

it('creates, edits, confirms deletion, and invalidates category and product lookups', async () => {
  let current = categoryRow
  let reads = 0
  let queryClient!: QueryClient
  const { fetchMock } = renderManagementRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) { reads += 1; return jsonResponse(page([current])) }
    if (url.includes('/categories') && init?.method === 'POST') { current = { ...current, name: 'Fasteners' }; return jsonResponse(current, 201) }
    if (url.endsWith('/categories/4') && init?.method === 'PUT') { current = { ...current, name: 'Bolts' }; return jsonResponse(current) }
    if (url.endsWith('/categories/4') && init?.method === 'DELETE') return new Response(null, { status: 204 })
    throw new Error(`Unexpected request ${url}`)
  }, cache => { queryClient = cache; cache.setQueryData(['products', 'lookup'], page()) })
  const user = userEvent.setup()
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Tạo danh mục/i }))
  await user.type(screen.getByLabelText('Tên danh mục'), 'Fasteners')
  await user.click(screen.getByRole('button', { name: 'Lưu danh mục' }))
  expect(await screen.findByText('Fasteners')).toBeInTheDocument()
  expect(reads).toBeGreaterThan(1)
  expect(queryClient.getQueryState(['products', 'lookup'])?.isInvalidated).toBe(true)
  await user.click(screen.getByRole('button', { name: /Sửa danh mục Fasteners/i }))
  await user.clear(screen.getByLabelText('Tên danh mục'))
  await user.type(screen.getByLabelText('Tên danh mục'), 'Bolts')
  await user.click(screen.getByRole('button', { name: 'Lưu danh mục' }))
  expect(await screen.findByText('Bolts')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Xóa danh mục Bolts/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Xác nhận xóa danh mục' }))
  expect(await screen.findByText('Đã xóa danh mục.')).toBeInTheDocument()
})

it('paginates categories and offers retry after a failed read', async () => {
  let failed = true
  const { fetchMock } = renderManagementRoute('/categories', 'client', (url) => {
    if (url.includes('/categories?') && failed) return jsonResponse({ detail: { code: 'READ_FAILED', message: 'Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.', fields: null } }, 503)
    return jsonResponse(page([categoryRow], 21, url.includes('page=2') ? 2 : 1))
  })
  const user = userEvent.setup()
  expect(await screen.findByRole('alert', { name: 'Lỗi danh sách' })).toHaveTextContent('Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.')
  failed = false
  await user.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText('Hardware')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText('Trang 2 / 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/categories?page=2&page_size=20'))).toBe(true)
})

it('associates backend parent_id errors with the parent selector and keeps the domain error visible', async () => {
  renderManagementRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) return jsonResponse(page([categoryRow]))
    if (url.endsWith('/categories') && init?.method === 'POST') return jsonResponse({ detail: { code: 'CATEGORY_PARENT_INVALID', message: 'Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.', fields: { parent_id: ['Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.'] } } }, 422)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Hardware')
  await user.click(screen.getByRole('button', { name: /Tạo danh mục/i }))
  await user.type(screen.getByLabelText('Tên danh mục'), 'Child')
  await user.selectOptions(screen.getByLabelText('Danh mục cha'), '4')
  await user.click(screen.getByRole('button', { name: 'Lưu danh mục' }))
  expect(await screen.findByText('Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.')).toBeInTheDocument()
  expect(screen.getByLabelText(/^Danh mục cha/)).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText(/^Danh mục cha/)).toHaveAccessibleDescription('Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.')
  expect(screen.getByLabelText('Tên danh mục')).toHaveValue('Child')
  expect(screen.getByLabelText('Danh mục cha')).toHaveValue('4')
})

it('disables category submission and ignores a second click while create is pending', async () => {
  let resolveCreate: (() => void) | undefined
  let posts = 0
  renderManagementRoute('/categories', 'admin', (url, init) => {
    if (url.includes('/categories?')) return jsonResponse(page([categoryRow]))
    if (url.endsWith('/categories') && init?.method === 'POST') {
      posts += 1
      return new Promise((resolve) => { resolveCreate = () => resolve(jsonResponse({ ...categoryRow, name: 'Bolts' }, 201)) })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Hardware')
  await user.click(screen.getByRole('button', { name: /Tạo danh mục/i }))
  await user.type(screen.getByLabelText('Tên danh mục'), 'Bolts')
  await user.click(screen.getByRole('button', { name: 'Lưu danh mục' }))
  const saving = await screen.findByRole('button', { name: /Đang xử lý/i })
  expect(saving).toBeDisabled()
  await user.click(saving)
  expect(posts).toBe(1)
  resolveCreate?.()
})

it('blocks incomplete parent options, retries the actual lookup and preserves a pending cancel boundary', async () => {
  let unavailable = true
  const view = renderManagementRoute('/categories', 'admin', (url, init) => {
    if (init?.method === 'POST') return jsonResponse(categoryRow, 201)
    if (new URL(url).searchParams.get('page_size') === '100' && unavailable) return jsonResponse({ detail: { code: 'LOOKUP_UNAVAILABLE' } }, 503)
    return jsonResponse(page())
  })
  await screen.findByRole('alert', { name: 'Lỗi danh mục cha' })
  await userEvent.click(screen.getByRole('button', { name: 'Tạo danh mục' }))
  await userEvent.type(screen.getByLabelText('Tên danh mục'), 'Giữ bản nháp')
  expect(screen.getByRole('button', { name: 'Lưu danh mục' })).toBeDisabled()
  expect(view.fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  unavailable = false
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại danh mục cha' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu danh mục' })).toBeEnabled())
  expect(screen.getByLabelText('Tên danh mục')).toHaveValue('Giữ bản nháp')
  await userEvent.click(screen.getByRole('button', { name: 'Hủy' }))
  expect(screen.queryByRole('form', { name: 'Tạo danh mục' })).not.toBeInTheDocument()
})

it.each(['create', 'update'] as const)('prevents switching category editors during %s and preserves the original draft on failure', async mode => {
  let finish!: (response: Response) => void
  const method = mode === 'create' ? 'POST' : 'PUT'
  const view = renderManagementRoute('/categories', 'admin', (_, init) => init?.method === method ? new Promise<Response>(resolve => { finish = resolve }) : jsonResponse(page()))
  await screen.findByText('Hardware')
  await userEvent.click(screen.getByRole('button', { name: mode === 'create' ? 'Tạo danh mục' : 'Sửa danh mục Hardware' }))
  await userEvent.clear(screen.getByLabelText('Tên danh mục'))
  await userEvent.type(screen.getByLabelText('Tên danh mục'), 'Bản nháp cần giữ')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu danh mục' }))
  expect(screen.getByRole('button', { name: 'Tạo danh mục' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Sửa danh mục Hardware' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Xóa danh mục Hardware' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Sửa danh mục Hardware' }))
  expect(view.fetchMock.mock.calls.filter(([, init]) => init?.method === method)).toHaveLength(1)
  await act(async () => { finish(jsonResponse({ detail: { code: 'CATEGORY_NAME_CONFLICT' } }, 409)) })
  expect(await screen.findByRole('alert')).toHaveTextContent('Tên danh mục đã tồn tại.')
  expect(screen.getByRole('form', { name: mode === 'create' ? 'Tạo danh mục' : 'Sửa danh mục' })).toBeInTheDocument()
  expect(screen.getByLabelText('Tên danh mục')).toHaveValue('Bản nháp cần giữ')
  expect(screen.getByRole('button', { name: 'Tạo danh mục' })).toBeEnabled()
})
