import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { formatDateTime } from '../../shared/lib/formatters'
import userEvent from '@testing-library/user-event'
import { jsonResponse, renderManagementRoute, warehouseRow } from '../../test/renderManagementRoute'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

const product = { id: 6, sku: 'SKU-001', name: 'Steel bolt', description: null, category_id: 4, supplier_id: 5, unit: 'piece', reorder_level: 3, is_active: true }
const event = { id: 88, transaction_type: 'inbound', warehouse_id: 7, product_id: 6, quantity: 5, inbound_id: 30, outbound_id: null, created_by_id: 12, created_at: '2026-09-29T02:45:00Z' }
const page = (items = [event], total = items.length, current = 1) => ({ items, total, page: current, page_size: 20 })

it('shows transaction direction, resolved labels, actor, linked movement, quantity, and local time', async () => {
  renderManagementRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })

  expect(await screen.findByText('Nhập kho', { selector: '.movement-direction' })).toBeInTheDocument()
  expect(screen.getByText('SKU-001')).toBeInTheDocument()
  expect(screen.getByText('WH-01')).toBeInTheDocument()
  expect(screen.getByText('Tài khoản #12')).toBeInTheDocument()
  expect(screen.getByText('Phiếu nhập #30')).toBeInTheDocument()
  expect(screen.getByText('5')).toBeInTheDocument()
  expect(screen.getByText(formatDateTime(event.created_at))).toBeInTheDocument()
})

it('resolves labels by ID when product and warehouse are outside lookup pages', async () => {
  const { fetchMock } = renderManagementRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [{ ...product, id: Number(new URL(url).searchParams.get('page')) + 1, sku: new URL(url).searchParams.get('page') === '2' ? 'SKU-OTHER-2' : 'SKU-OTHER', name: 'Different item' }], total: 2, page: Number(new URL(url).searchParams.get('page')), page_size: 1 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [{ ...warehouseRow, id: 3, code: 'WH-OTHER' }], total: 44, page: 1, page_size: 100 })
    if (url.endsWith('/products/6')) return jsonResponse(product)
    if (url.endsWith('/warehouses/7')) return jsonResponse(warehouseRow)
    return jsonResponse({})
  })

  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(await screen.findByText('WH-01')).toBeInTheDocument()
  expect(screen.queryByText('SKU-OTHER')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/products/6'))).toBe(true)
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/warehouses/7'))).toBe(true)
})

it('retains transaction details while retrying only a failed warehouse label', async () => {
  let productRequests = 0
  let warehouseRequests = 0
  let resolveRetry: ((response: Response) => void) | undefined
  const warehouse = { ...warehouseRow, id: 7, code: 'WH-01', name: 'Main warehouse' }
  const { fetchMock } = renderManagementRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [{ ...product, id: Number(new URL(url).searchParams.get('page')) + 1, sku: new URL(url).searchParams.get('page') === '2' ? 'SKU-OTHER-2' : 'SKU-OTHER', name: 'Other item' }], total: 2, page: Number(new URL(url).searchParams.get('page')), page_size: 1 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [{ ...warehouse, id: 3, code: 'WH-OTHER' }], total: 44, page: 1, page_size: 100 })
    if (url.endsWith('/products/6')) {
      productRequests += 1
      return jsonResponse(product)
    }
    if (url.endsWith('/warehouses/7')) {
      warehouseRequests += 1
      if (warehouseRequests === 1) return jsonResponse({ detail: { code: 'LOOKUP_DOWN', message: 'Không thể tải tên sản phẩm và kho hàng.', fields: null } }, 503)
      return new Promise<Response>((resolve) => { resolveRetry = resolve })
    }
    return jsonResponse({})
  })

  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  expect(await screen.findByText('Kho hàng #7')).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải tên sản phẩm và kho hàng.')
  expect(screen.getByText('Tài khoản #12')).toBeInTheDocument()
  expect(screen.getByText('Phiếu nhập #30')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Thử lại tên hiển thị' }))
  expect(await screen.findByText('Đang tải tên sản phẩm và kho hàng…')).toHaveAttribute('role', 'status')
  expect(screen.getByText('SKU-001')).toBeInTheDocument()
  expect(screen.getByText('Tài khoản #12')).toBeInTheDocument()
  expect(screen.getByText('Phiếu nhập #30')).toBeInTheDocument()
  expect(productRequests).toBe(1)
  expect(warehouseRequests).toBe(2)
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/products/6'))).toHaveLength(1)

  resolveRetry?.(jsonResponse(warehouse))
  expect(await screen.findByText('WH-01')).toBeInTheDocument()
})

it('filters transaction type and timezone-aware date range and resets pagination', async () => {
  const { fetchMock } = renderManagementRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page([event], 41, url.includes('page=2') ? 2 : 1))
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  await user.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 3')
  await user.selectOptions(screen.getByLabelText('Loại giao dịch'), 'outbound')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Kho hàng' }), '7')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Sản phẩm' }), '6')
  await user.type(screen.getByLabelText('Từ thời điểm'), '2026-09-28T08:00')
  await user.type(screen.getByLabelText('Đến thời điểm'), '2026-09-29T08:00')
  await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))

  expect(await screen.findByText('Trang 1 / 3')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => {
    const params = new URL(String(url)).searchParams
    return params.get('transaction_type') === 'outbound' && params.get('warehouse_id') === '7' && params.get('product_id') === '6' && params.get('created_from') === new Date('2026-09-28T08:00').toISOString() && params.get('created_to') === new Date('2026-09-29T08:00').toISOString() && params.get('page') === '1'
  })).toBe(true)
})

it('rejects inverted transaction dates without sending another request', async () => {
  const { fetchMock } = renderManagementRoute('/transactions', 'admin', (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  const user = userEvent.setup()
  await screen.findByText('SKU-001')
  const requests = fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?')).length
  await user.type(screen.getByLabelText('Từ thời điểm'), '2026-09-29T12:00')
  await user.type(screen.getByLabelText('Đến thời điểm'), '2026-09-28T12:00')
  await user.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/Thời điểm bắt đầu phải trước thời điểm kết thúc/)
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?'))).toHaveLength(requests)
})

it.each(['admin', 'warehouse'] as const)('provides bounded transaction pagination to %s', async (role) => {
  renderManagementRoute('/transactions', role, (url) => {
    if (url.includes('/transactions?')) return jsonResponse(page([event], 61, url.includes('page=2') ? 2 : 1))
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText('Trang 2 / 4')).toBeInTheDocument()
})

it('shows transaction service errors and lets the user retry the history query', async () => {
  let attempts = 0
  renderManagementRoute('/transactions', 'warehouse', (url) => {
    if (url.includes('/transactions?')) {
      attempts += 1
      return attempts === 1
        ? jsonResponse({ detail: { code: 'HISTORY_DOWN', message: 'Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.', fields: null } }, 503)
        : jsonResponse(page())
    }
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    if (url.includes('/warehouses?')) return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
    return jsonResponse({})
  })

  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại giao dịch' }))
  expect(await screen.findByText('SKU-001')).toBeInTheDocument()
})

it.each(['0', '1.5', '2147483648'])('rejects an invalid stale product option %s before querying history', async value => {
  const { fetchMock } = renderManagementRoute('/transactions', 'warehouse', url => {
    if (url.includes('/transactions?')) return jsonResponse(page())
    if (url.includes('/products?')) return jsonResponse({ items: [product], total: 1, page: 1, page_size: 100 })
    return jsonResponse({ items: [warehouseRow], total: 1, page: 1, page_size: 100 })
  })
  await screen.findByText('SKU-001')
  const before = fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?')).length
  const select = screen.getByRole('combobox', { name: 'Sản phẩm' })
  const invalid = document.createElement('option')
  invalid.value = value; invalid.textContent = 'Stale option'; select.append(invalid)
  fireEvent.change(select, { target: { value } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Chọn mã sản phẩm và kho hàng hợp lệ.')
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/transactions?'))).toHaveLength(before)
})
