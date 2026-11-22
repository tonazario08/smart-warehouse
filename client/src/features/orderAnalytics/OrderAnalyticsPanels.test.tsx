import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { getOpenDemand, getOrderChecks, getOrderWarehouses, getReplenishmentPosition } from './api'
import { OpenDemandPanel, OrderChecksPanel, ReplenishmentPositionPanel } from './OrderAnalyticsPanels'
import type { Warehouse } from '../warehouses/types'
import type { OpenDemand, OrderCheck, ReplenishmentPosition } from './types'

vi.mock('./api')
beforeEach(() => vi.resetAllMocks())

const warehouse = (id: number, code: string, name: string): Warehouse => ({
  id, code, name, address: '', latitude: null, longitude: null, created_at: '', updated_at: '',
})
const warehouses = [warehouse(2, 'HCM-01', 'Central Warehouse'), warehouse(3, 'HCM-02', 'North Warehouse')]

const target = { warehouse_id: 2, product_id: 5 }
const stamp = '2026-11-22T00:00:00Z'
const demand: OpenDemand = {
  ...target, sku: 'SKU-5', unit: 'unit', state: 'available', reason_code: null, computed_at: stamp,
  forecast_run_id: 'demo', forecast_dataset_class: 'fixture', forecast_stale: true,
  pending_quantity: 9, approved_quantity: 2, open_quantity: 11, order_count: 2,
}
const position: ReplenishmentPosition = {
  ...target, sku: 'SKU-5', unit: 'unit', state: 'available', reason_code: null, computed_at: stamp,
  on_hand: 10, open_quantity: 11, projected_quantity: -1, rop: 3, rop_date: '2026-11-21',
  eoq: 86, recommendation: true, dataset_class: 'fixture', run_id: 'demo',
}
const selection = { algorithm: 'persistence', lead_time: 1, service: '0.90', policy: 'proposed', reference_date: '2026-11-21' }

it('labels known open demand as unallocated, separate and demo-only, and does not invent quantities when baseline is absent', async () => {
  vi.mocked(getOpenDemand).mockResolvedValueOnce(demand).mockResolvedValueOnce({ ...demand, state: 'insufficient_data', reason_code: 'BASELINE_NOT_FOUND', open_quantity: null })
  const view = render(<OpenDemandPanel token="t" context="run-a" target={target} />)
  expect(await screen.findByText('11 đơn vị')).toBeInTheDocument()
  expect(screen.getByText(/Chưa gán kỳ/)).toBeInTheDocument()
  expect(screen.getByText('Dữ liệu demo/fixture')).toBeInTheDocument()
  view.rerender(<OpenDemandPanel token="t" context="run-b" target={target} />)
  expect(screen.queryByText('11 đơn vị')).not.toBeInTheDocument()
  expect(await screen.findByText(/Chưa có dự báo nền phù hợp/)).toBeInTheDocument()
  expect(screen.queryByText(/Tổng chờ giao/)).not.toBeInTheDocument()
})

it('rejects a delayed prior-run response when the operator changes away and back', async () => {
  let first!: (value: OpenDemand) => void
  let second!: (value: OpenDemand) => void
  vi.mocked(getOpenDemand)
    .mockReturnValueOnce(new Promise(resolve => { first = resolve }))
    .mockReturnValueOnce(new Promise(resolve => { second = resolve }))
    .mockResolvedValueOnce({ ...demand, open_quantity: 17 })
  const view = render(<OpenDemandPanel token="t" context="A" target={target} />)
  view.rerender(<OpenDemandPanel token="t" context="B" target={target} />)
  view.rerender(<OpenDemandPanel token="t" context="A" target={target} />)
  expect(await screen.findByText('17 đơn vị')).toBeInTheDocument()
  await act(async () => { second({ ...demand, open_quantity: 22 }); first(demand) })
  expect(screen.getByText('17 đơn vị')).toBeInTheDocument()
  expect(screen.queryByText('11 đơn vị')).not.toBeInTheDocument()
  expect(screen.queryByText('22 đơn vị')).not.toBeInTheDocument()
  expect(vi.mocked(getOpenDemand).mock.calls[0][2].aborted).toBe(true)
})

it('shows negative projected stock without treating a fixture ROP as operational', async () => {
  vi.mocked(getReplenishmentPosition)
    .mockResolvedValueOnce({ ...position, state: 'insufficient_data', reason_code: 'OPERATIONAL_ROP_NOT_FOUND', rop: null, eoq: null })
    .mockResolvedValueOnce(position)
  render(<>
    <ReplenishmentPositionPanel token="t" context="run" target={target} view="operational" selection={selection} />
    <ReplenishmentPositionPanel token="t" context="run" target={target} view="demo" selection={selection} />
  </>)
  const operational = within(screen.getByRole('region', { name: 'Tồn dự kiến (tạm tính)' }))
  expect(await operational.findByText(/Chưa có ROP vận hành/)).toBeInTheDocument()
  expect(operational.getByText('-1 đơn vị')).toBeInTheDocument()
  const demo = within(screen.getByRole('region', { name: /Tham chiếu demo/ }))
  expect(await demo.findByText(/ROP ngày 2026-11-21/)).toBeInTheDocument()
  expect(demo.getByText(/không phải ngưỡng vận hành/)).toBeInTheDocument()
  expect(screen.queryByText('Đề xuất xem xét bổ sung')).not.toBeInTheDocument()
})

it('clears checks for a changed warehouse and reports rule outcomes separately from model alerts', async () => {
  const check: OrderCheck = {
    ...target, purchase_request_id: 37, state: 'available', reason_code: null, computed_at: stamp,
    flagged: true, rule_id: 'rule', rule_version: 1, sample_count: 8, median: 2, mad: 0, score: null, label: 'Kiểm tra đơn tạm tính',
  }
  vi.mocked(getOrderChecks).mockResolvedValueOnce({ items: [check], total: 1, page: 1, page_size: 20 })
  vi.mocked(getOrderWarehouses).mockResolvedValue(warehouses)
  render(<OrderChecksPanel token="t" context="admin" />)
  const option = await screen.findByRole('option', { name: 'HCM-01 - Central Warehouse' })
  expect(option).toHaveValue('2')
  fireEvent.change(screen.getByRole('combobox', { name: 'Kho' }), { target: { value: '2' } })
  fireEvent.change(screen.getByLabelText('ID sản phẩm'), { target: { value: '5' } })
  fireEvent.click(screen.getByRole('button', { name: 'Xem kiểm tra đơn' }))
  expect(await screen.findByText('Cần xem xét')).toBeInTheDocument()
  expect(screen.getByText(/tách riêng khỏi cảnh báo mô hình/)).toBeInTheDocument()
  expect(getOrderChecks).toHaveBeenCalledWith('t', { warehouse_id: 2, product_id: 5 }, 1, expect.any(AbortSignal))
  fireEvent.change(screen.getByRole('combobox', { name: 'Kho' }), { target: { value: '3' } })
  expect(screen.queryByText('Cần xem xét')).not.toBeInTheDocument()
  await waitFor(() => expect(getOrderChecks).toHaveBeenCalledTimes(1))
})

it('polls a queued analysis and stops after the worker result arrives', async () => {
  vi.useFakeTimers()
  try {
    vi.mocked(getOpenDemand)
      .mockResolvedValueOnce({ ...demand, state: 'computing', open_quantity: null })
      .mockResolvedValueOnce(demand)
    render(<OpenDemandPanel token="t" context="run" target={target} />)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText(/^Đang tính/)).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(screen.getByText('11 đơn vị')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(getOpenDemand).toHaveBeenCalledTimes(2)
  } finally {
    vi.useRealTimers()
  }
})

it('does not display a demo result for a different simulation run', async () => {
  vi.mocked(getReplenishmentPosition).mockResolvedValue(position)
  render(<ReplenishmentPositionPanel token="t" context="run" target={target} view="demo" selection={{ ...selection, run_id: 'current-run' }} />)
  expect(await screen.findByText('Cập nhật lỗi')).toBeInTheDocument()
  expect(screen.queryByText(/ROP ngày 2026-11-21/)).not.toBeInTheDocument()
})

it('keeps the warehouse select disabled on load error and allows retry', async () => {
  vi.mocked(getOrderWarehouses).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(warehouses)
  render(<OrderChecksPanel token="t" context="admin" />)
  const select = screen.getByRole('combobox', { name: 'Kho' })
  expect(select).toBeDisabled()
  const retry = await screen.findByRole('button', { name: /danh s.ch kho/i })
  expect(select).toBeDisabled()
  fireEvent.click(retry)
  expect(await screen.findByRole('option', { name: 'HCM-01 - Central Warehouse' })).toBeInTheDocument()
  expect(select).toBeEnabled()
})
