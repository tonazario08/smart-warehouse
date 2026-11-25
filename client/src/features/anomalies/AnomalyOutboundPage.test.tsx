import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api'
import { AnomalyOutboundPage } from './AnomalyOutboundPage'
import * as api from './api'
import type { AlertOutbound } from './types'

const auth = vi.hoisted(() => ({ token: 'token', id: 1, role: 'warehouse' }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => ({ token: auth.token, user: { id: auth.id, role: auth.role } }) }))
vi.mock('./api')
const voucher = {
  outbound_id: 701, product_name: 'Sản phẩm mẫu', product_sku: 'SKU-A',
  warehouse_code: 'KHO-A', warehouse_name: 'Kho A',
  quantity: 10000, unit: 'each', occurred_at: '2026-01-16T23:00:00Z', performed_by_id: 17,
}
const view = () => <MemoryRouter initialEntries={['/anomalies/alert/outbound']}><Routes><Route path="/anomalies/:alertId/outbound" element={<AnomalyOutboundPage />} /></Routes></MemoryRouter>
beforeEach(() => {
  vi.resetAllMocks()
  Object.assign(auth, { token: 'token', id: 1, role: 'warehouse' })
  vi.mocked(api.getAlertOutbound).mockResolvedValue(voucher)
})

it('opens exact verified voucher and renders only read-only warehouse information', async () => {
  render(view())
  expect(await screen.findByRole('heading', { name: 'Phiếu xuất #701' })).toBeVisible()
  expect(api.getAlertOutbound).toHaveBeenCalledWith('token', 'alert')
  expect(screen.getByText('Sản phẩm mẫu (SKU-A)')).toBeVisible()
  expect(screen.getByText('Kho A (KHO-A)')).toBeVisible()
  expect(screen.getByText('10.000 each')).toBeVisible()
  expect(screen.getByText('Người dùng #17')).toBeVisible()
  expect(screen.getByText(/06:00.*17\/01\/2026.*giờ Việt Nam/)).toBeVisible()
  expect(screen.getByRole('link', { name: 'Về chi tiết cảnh báo' })).toHaveAttribute('href', '/anomalies/alert')
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it.each([
  [404, 'Chưa liên kết được phiếu xuất đối chiếu.'],
  [403, 'Bạn không có quyền xem phiếu xuất.'],
  [500, 'Không thể kiểm tra liên kết phiếu xuất lúc này.'],
])('handles endpoint status %s without showing voucher data', async (code, copy) => {
  vi.mocked(api.getAlertOutbound).mockRejectedValue(new ApiError('detail ignored', code))
  render(view())
  expect(await screen.findByText(copy)).toBeVisible()
  expect(screen.queryByText('detail ignored')).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: /Phiếu xuất #/ })).not.toBeInTheDocument()
})

it('never fetches the voucher on a direct route when client lacks permission', () => {
  auth.role = 'client'
  render(view())
  expect(screen.getByText('Bạn không có quyền xem phiếu xuất.')).toBeVisible()
  expect(api.getAlertOutbound).not.toHaveBeenCalled()
})

it('drops a late voucher response when the session loses authorization', async () => {
  let resolve!: (data: AlertOutbound) => void
  vi.mocked(api.getAlertOutbound).mockReturnValue(new Promise(done => { resolve = done }))
  const rendered = render(view())
  expect(api.getAlertOutbound).toHaveBeenCalledTimes(1)
  Object.assign(auth, { token: 'next', id: 2, role: 'client' })
  rendered.rerender(view())
  await act(async () => resolve(voucher))
  expect(screen.getByText('Bạn không có quyền xem phiếu xuất.')).toBeVisible()
  expect(screen.queryByText('10.000 each')).not.toBeInTheDocument()
  expect(api.getAlertOutbound).toHaveBeenCalledTimes(1)
})
