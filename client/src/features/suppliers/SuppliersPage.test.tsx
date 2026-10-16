import { afterEach, expect, it, vi } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderManagementRoute, supplierRow } from '../../test/renderManagementRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
const page = (items = [supplierRow], total = items.length, p = 1) => ({ items, total, page: p, page_size: 20 })

it('allows warehouse but routes clients away from suppliers', async () => {
  renderManagementRoute('/suppliers', 'warehouse', (url) => url.includes('/suppliers?') ? jsonResponse(page()) : jsonResponse({}))
  expect(await screen.findByText('Northwind')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Tạo nhà cung cấp/i })).not.toBeInTheDocument()
})

it('creates, updates, confirms deletion, maps backend errors, and prevents duplicate submits', async () => {
  let current = supplierRow
  let gate: (() => void) | undefined
  const { fetchMock } = renderManagementRoute('/suppliers', 'admin', (url, init) => {
    if (url.includes('/suppliers?')) return jsonResponse(page([current]))
    if (url.endsWith('/suppliers') && init?.method === 'POST') return new Promise((resolve) => { gate = () => { current = { ...current, name: 'Contoso' }; resolve(jsonResponse(current, 201)) } })
    if (url.endsWith('/suppliers/5') && init?.method === 'PUT') { current = { ...current, name: 'Fabrikam' }; return jsonResponse(current) }
    if (url.endsWith('/suppliers/5') && init?.method === 'DELETE') return new Response(null, { status: 204 })
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  expect(await screen.findByText('Northwind')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Tạo nhà cung cấp/i }))
  expect(await screen.findByRole('form', { name: 'Tạo nhà cung cấp' })).toBeInTheDocument()
  await user.type(screen.getByLabelText('Tên nhà cung cấp'), 'Contoso')
  await user.click(screen.getByRole('button', { name: 'Lưu nhà cung cấp' }))
  const save = screen.getByRole('button', { name: /Đang xử lý/i })
  expect(save).toBeDisabled()
  await user.click(save)
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  gate?.()
  expect(await screen.findByText('Contoso')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Sửa nhà cung cấp Contoso/i }))
  await user.clear(screen.getByLabelText('Tên nhà cung cấp'))
  await user.type(screen.getByLabelText('Tên nhà cung cấp'), 'Fabrikam')
  await user.click(screen.getByRole('button', { name: 'Lưu nhà cung cấp' }))
  expect(await screen.findByText('Fabrikam')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Xóa nhà cung cấp Fabrikam/i }))
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Xác nhận xóa nhà cung cấp' }))
  expect(await screen.findByText('Đã xóa nhà cung cấp.')).toBeInTheDocument()
})

it('applies search, resets pagination, and shows backend conflict details', async () => {
  let currentPage = 2
  const { fetchMock } = renderManagementRoute('/suppliers', 'admin', (url, init) => {
    if (url.includes('/suppliers?')) return jsonResponse(page([supplierRow], 22, url.includes('page=1') ? 1 : currentPage))
    if (url.endsWith('/suppliers') && init?.method === 'POST') return jsonResponse({ detail: { code: 'SUPPLIER_CONFLICT', message: 'Thông tin nhà cung cấp bị trùng. Vui lòng kiểm tra lại.', fields: { email: ['Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.'] } } }, 409)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Northwind')
  await user.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 2')
  await user.type(screen.getByLabelText('Tìm nhà cung cấp'), 'North')
  await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(await screen.findByText('Trang 1 / 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('search=North'))).toBe(true)
  await user.click(screen.getByRole('button', { name: /Tạo nhà cung cấp/i }))
  await user.type(screen.getByLabelText('Tên nhà cung cấp'), 'Duplicate')
  await user.type(screen.getByLabelText('Email'), 'dup@example.com')
  await user.click(screen.getByRole('button', { name: 'Lưu nhà cung cấp' }))
  expect(await screen.findByText('Thông tin nhà cung cấp bị trùng. Vui lòng kiểm tra lại.')).toBeInTheDocument()
  expect(screen.getByLabelText(/^Email/)).toHaveAccessibleDescription('Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.')
})

it('associates supplier phone and address errors with their controls', async () => {
  renderManagementRoute('/suppliers', 'admin', (url, init) => {
    if (url.includes('/suppliers?')) return jsonResponse(page([]))
    if (url.endsWith('/suppliers') && init?.method === 'POST') return jsonResponse({ detail: { code: 'SUPPLIER_FIELDS_INVALID', message: 'Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.', fields: { phone: ['Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.'], address: ['Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.'] } } }, 422)
    throw new Error(`Unexpected request ${url}`)
  })
  const user = userEvent.setup()
  await screen.findByText('Không có nhà cung cấp phù hợp.')
  await user.click(screen.getByRole('button', { name: /Tạo nhà cung cấp/i }))
  await user.type(screen.getByLabelText('Tên nhà cung cấp'), 'Contoso')
  await user.type(screen.getByLabelText('Số điện thoại'), 'not a number')
  await user.type(screen.getByLabelText('Địa chỉ'), 'Test Road')
  await user.click(screen.getByRole('button', { name: 'Lưu nhà cung cấp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.')
  for (const [label, message] of [['Số điện thoại', 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.'], ['Địa chỉ', 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.']]) {
    const control = screen.getByLabelText(new RegExp(`^${label}`))
    expect(control).toHaveAttribute('aria-invalid', 'true')
    expect(control).toHaveAccessibleDescription(message)
  }
  expect(screen.getByLabelText('Tên nhà cung cấp')).toHaveValue('Contoso')
  expect(screen.getByLabelText('Số điện thoại')).toHaveValue('not a number')
})

it('preserves table and delete confirmation on in-use failure and recovers the final page after retry', async () => {
  let rejected = true, removed = false
  const view = renderManagementRoute('/suppliers', 'admin', (url, init) => {
    if (init?.method === 'DELETE') {
      if (rejected) return jsonResponse({ detail: { code: 'SUPPLIER_IN_USE' } }, 409)
      removed = true; return new Response(null, { status: 204 })
    }
    const current = Number(new URL(url).searchParams.get('page'))
    return jsonResponse(page(current === 2 && removed ? [] : [supplierRow], removed ? 20 : 21, current))
  })
  await screen.findByText('Northwind')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 2')
  await userEvent.click(screen.getByRole('button', { name: 'Xóa nhà cung cấp Northwind' }))
  await userEvent.click(screen.getByRole('button', { name: 'Hủy' }))
  expect(view.fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'Xóa nhà cung cấp Northwind' }))
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận xóa nhà cung cấp' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể xóa nhà cung cấp đang được sử dụng.')
  expect(screen.getByRole('table', { name: 'Danh sách nhà cung cấp' })).toBeInTheDocument()
  rejected = false
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận xóa nhà cung cấp' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(await screen.findByText('Trang 1 / 1')).toBeInTheDocument()
})

it.each(['create', 'update'] as const)('blocks filter/editor context switches during %s and keeps the failed supplier draft actionable', async mode => {
  let finish!: (response: Response) => void
  const method = mode === 'create' ? 'POST' : 'PUT'
  const view = renderManagementRoute('/suppliers', 'admin', (_, init) => init?.method === method ? new Promise<Response>(resolve => { finish = resolve }) : jsonResponse(page()))
  await screen.findByText('Northwind')
  await userEvent.click(screen.getByRole('button', { name: mode === 'create' ? 'Tạo nhà cung cấp' : 'Sửa nhà cung cấp Northwind' }))
  await userEvent.clear(screen.getByLabelText('Tên nhà cung cấp'))
  await userEvent.type(screen.getByLabelText('Tên nhà cung cấp'), 'Bản nháp đối tác')
  await userEvent.clear(screen.getByLabelText('Email'))
  await userEvent.type(screen.getByLabelText('Email'), 'draft@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Lưu nhà cung cấp' }))
  expect(screen.getByRole('button', { name: 'Tạo nhà cung cấp' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Sửa nhà cung cấp Northwind' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Xóa nhà cung cấp Northwind' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Áp dụng bộ lọc' })).toBeDisabled()
  expect(screen.getByLabelText('Tìm nhà cung cấp')).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(view.fetchMock.mock.calls.filter(([, init]) => init?.method === method)).toHaveLength(1)
  await act(async () => { finish(jsonResponse({ detail: { code: 'SUPPLIER_CONFLICT' } }, 409)) })
  expect(await screen.findByRole('alert')).toHaveTextContent('Thông tin nhà cung cấp bị trùng.')
  expect(screen.getByLabelText('Tên nhà cung cấp')).toHaveValue('Bản nháp đối tác')
  expect(screen.getByLabelText('Email')).toHaveValue('draft@example.com')
  expect(screen.getByRole('button', { name: 'Lưu nhà cung cấp' })).toBeEnabled()
})
