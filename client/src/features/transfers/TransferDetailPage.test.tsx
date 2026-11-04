import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { jsonResponse, renderTransferRoute, transfer, transferHandler } from '../../test/renderTransferRoute'

afterEach(() => localStorage.clear())
it('labels historical balance snapshots and movement IDs without inventing detail links', async () => {
  const { fetchMock } = renderTransferRoute('/transfers/8')
  expect(await screen.findByText('Phiếu chuyển #8')).toBeInTheDocument()
  expect(screen.getByText('Ngừng hoạt động')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Tồn kho tại thời điểm chuyển' })).toBeInTheDocument()
  expect(screen.getByText('Phiếu xuất #11 · Giao dịch #21')).toBeInTheDocument()
  expect(screen.getByText('Phiếu nhập #12 · Giao dịch #22')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: '7 cái' })).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: '5 cái' })).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/stock'))).toBe(false)
  expect(screen.queryByRole('link', { name: /Phiếu xuất|Phiếu nhập/ })).not.toBeInTheDocument()
})
it('handles404 and supports a deliberate retry', async () => {
  let count = 0
  renderTransferRoute('/transfers/8', 'warehouse', url => url.endsWith('/transfers/8') && ++count === 1 ? jsonResponse({}, 404) : transferHandler(url))
  expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy phiếu chuyển kho.')
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại chi tiết' }))
  expect(await screen.findByText('Phiếu chuyển #8')).toBeInTheDocument()
})
it('discards a previous route response and never posts during hydration or refresh', async () => {
  let finish!: (response: Response) => void
  const { active, fetchMock } = renderTransferRoute('/transfers/8', 'warehouse', url => {
    if (url.endsWith('/transfers/8')) return new Promise(resolve => { finish = resolve })
    if (url.endsWith('/transfers/9')) return jsonResponse({ ...transfer, id: 9 })
    return transferHandler(url)
  })
  await waitFor(() => expect(finish).toBeDefined())
  await act(async () => { await active.navigate('/transfers/9') })
  expect(await screen.findByText('Phiếu chuyển #9')).toBeInTheDocument()
  await act(async () => finish(jsonResponse(transfer)))
  expect(screen.queryByText('Phiếu chuyển #8')).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
