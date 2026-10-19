import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { jsonResponse, renderTransferRoute, transferHandler, transferPage } from '../../test/renderTransferRoute'

afterEach(() => localStorage.clear())
it('applies the shared wrapping pagination layout and usable button height', async () => {
  const { readFileSync } = await vi.importActual<{ readFileSync: (path: string, encoding: 'utf8') => string }>('node:fs')
  // Vitest normally omits CSS. Apply the real shared stylesheet so this catches
  // a page outside its supported scope, rather than asserting a class name.
  const stylesheet = document.createElement('style')
  stylesheet.textContent = readFileSync('src/shared/styles/management.css', 'utf8')
  document.head.append(stylesheet)
  try {
    renderTransferRoute('/transfers')
    await screen.findByRole('link', { name: 'Phiếu chuyển #8' })
    const pagination = screen.getByRole('navigation', { name: 'Phân trang' })
    expect(getComputedStyle(pagination).display).toBe('flex')
    expect(getComputedStyle(pagination).flexWrap).toBe('wrap')
    expect(getComputedStyle(pagination).gap).toBe('12px')
    expect(getComputedStyle(screen.getByRole('button', { name: 'Trang sau' })).minHeight).toBe('38px')
  } finally { stylesheet.remove() }
})
it('shows real paired identities, actor and supported detail/create destinations', async () => {
  renderTransferRoute('/transfers')
  expect(await screen.findByRole('link', { name: 'Phiếu chuyển #8' })).toHaveAttribute('href', '/transfers/8')
  expect(screen.getByRole('cell', { name: /Bu lông/ })).toHaveTextContent('CK-003')
  expect(screen.getByRole('cell', { name: 'Tài khoản #1' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Tạo phiếu chuyển kho' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Xóa|Chỉnh sửa/ })).not.toBeInTheDocument()
})
it('applies conjunctive filters on the server and resets the page', async () => {
  const { fetchMock } = renderTransferRoute('/transfers', 'admin', url => url.includes('/transfers?') ? jsonResponse(transferPage(undefined, 41, new URL(url).searchParams.get('page') === '2' ? 2 : 1)) : transferHandler(url))
  await screen.findByRole('link', { name: 'Phiếu chuyển #8' })
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText('Trang 2 / 3')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Lọc kho nguồn'), '1')
  await userEvent.selectOptions(screen.getByLabelText('Lọc kho đích'), '2')
  await userEvent.selectOptions(screen.getByLabelText('Lọc sản phẩm'), '3')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => {
    const params = new URL(String(url)).searchParams
    return params.get('source_warehouse_id') === '1' && params.get('destination_warehouse_id') === '2' && params.get('product_id') === '3' && params.get('page') === '1'
  })).toBe(true))
})
it('shows loading, error retry and an honest empty page', async () => {
  let finish!: (response: Response) => void
  let attempt = 0
  renderTransferRoute('/transfers', 'warehouse', url => {
    if (!url.includes('/transfers?')) return transferHandler(url)
    attempt++
    return attempt === 1 ? new Promise(resolve => { finish = resolve }) : jsonResponse(transferPage([]))
  })
  expect(await screen.findByText('Đang tải phiếu chuyển kho...')).toBeInTheDocument()
  finish(jsonResponse({}, 503))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại danh sách' }))
  expect(await screen.findByText('Chưa có phiếu chuyển kho phù hợp')).toBeInTheDocument()
})

it('rejects inverted dates and sends inclusive equal date boundaries as aware timestamps', async () => {
  const { fetchMock } = renderTransferRoute('/transfers')
  await screen.findByRole('link', { name: 'Phiếu chuyển #8' })
  const reads = () => fetchMock.mock.calls.filter(([url]) => String(url).includes('/transfers?'))
  const initial = reads().length
  fireEvent.change(screen.getByLabelText('Từ thời điểm'), { target: { value: '2026-10-18T08:00' } })
  fireEvent.change(screen.getByLabelText('Đến thời điểm'), { target: { value: '2026-10-17T08:00' } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(screen.getByRole('alert')).toHaveTextContent('không sau thời điểm kết thúc')
  expect(reads()).toHaveLength(initial)
  fireEvent.change(screen.getByLabelText('Từ thời điểm'), { target: { value: '2026-10-17T08:00' } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  await waitFor(() => expect(reads()).toHaveLength(initial + 1))
  const params = new URL(String(reads().at(-1)![0])).searchParams
  expect(params.get('created_from')).toBe(new Date('2026-10-17T08:00').toISOString())
  expect(params.get('created_from')).toBe(params.get('created_to'))
})
