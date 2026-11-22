import { useState } from 'react'
import { formatDateTime } from '../../shared/lib/formatters'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { Input } from '../../shared/ui/Input'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { getOpenDemand, getOrderChecks, getOrderWarehouses, getReplenishmentPosition } from './api'
import { analyticsTarget } from './types'
import type { AnalyticsStatus, AnalyticsTarget, SimulationSelection } from './types'
import { useOrderAnalytics } from './useOrderAnalytics'

const labels = { computing: 'Đang tính', available: 'Có kết quả', insufficient_data: 'Chưa đủ dữ liệu', failed: 'Cập nhật lỗi' }
const reasons: Record<string, string> = {
  BASELINE_NOT_FOUND: 'Chưa có dự báo nền phù hợp.',
  OPERATIONAL_ROP_NOT_FOUND: 'Chưa có ROP vận hành',
  DEMO_ROP_NOT_FOUND: 'Chưa có ROP mô phỏng phù hợp.',
  STOCK_ROW_MISSING: 'Chưa có bản ghi tồn kho.',
  INSUFFICIENT_HISTORY: 'Chưa đủ lịch sử đơn để đánh giá.',
}
const format = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 })
const amount = (value: number | null, unit: string) => value === null ? 'Chưa có dữ liệu' : `${format.format(value)} ${unit === 'unit' ? 'đơn vị' : unit}`
const requestKey = (...parts: unknown[]) => JSON.stringify(parts)
const match = (data: AnalyticsTarget, target: AnalyticsTarget) => data.product_id === target.product_id && data.warehouse_id === target.warehouse_id
const isPending = (data: AnalyticsStatus) => data.state === 'computing'

function Status({ data, error, retry }: { data: AnalyticsStatus | null; error: boolean; retry: () => void }) {
  if (error) return <><FeedbackMessage variant="error">Cập nhật lỗi</FeedbackMessage><Button onClick={retry}>Thử lại phân tích đơn</Button></>
  if (!data) return <FeedbackMessage>Đang tính</FeedbackMessage>
  return <p role="status">{labels[data.state]}{data.reason_code && reasons[data.reason_code] ? `. ${reasons[data.reason_code]}` : ''}{data.computed_at ? ` · Cập nhật: ${formatDateTime(data.computed_at)}` : ''}</p>
}

type RunPanelProps = { token: string; context: string; target: AnalyticsTarget }
export function OpenDemandPanel({ token, context, target }: RunPanelProps) {
  const [retry, setRetry] = useState(0)
  const { data, error } = useOrderAnalytics(
    requestKey(context, token, target, retry),
    async signal => {
      const result = await getOpenDemand(token, target, signal)
      if (!match(result, target)) throw new Error('order analytics target mismatch')
      return result
    }, isPending,
  )
  return <section className="forecast-panel" aria-label="Nhu cầu chờ giao (tạm tính)">
    <h2>Nhu cầu chờ giao (tạm tính)</h2>
    <p>Chưa gán kỳ. Tách riêng khỏi dự báo nền.</p>
    <Status data={data} error={error} retry={() => setRetry(n => n + 1)} />
    {data?.forecast_dataset_class === 'fixture' && <p>Dữ liệu demo/fixture</p>}
    {data?.forecast_stale && <p>Dự báo nền không còn cập nhật.</p>}
    {data?.state === 'available' && data.open_quantity !== null && <dl className="forecast-facts">
      <div><dt>Tổng chờ giao</dt><dd>{amount(data.open_quantity, data.unit)}</dd></div>
      <div><dt>Chờ duyệt</dt><dd>{amount(data.pending_quantity, data.unit)}</dd></div>
      <div><dt>Đã duyệt, chưa giao</dt><dd>{amount(data.approved_quantity, data.unit)}</dd></div>
      {data.order_count !== null && <div><dt>Số đơn đang mở</dt><dd>{data.order_count}</dd></div>}
    </dl>}
  </section>
}

export function ReplenishmentPositionPanel({ token, context, target, view, selection }: RunPanelProps & { view: 'operational' | 'demo'; selection: SimulationSelection }) {
  const [retry, setRetry] = useState(0)
  const { data, error } = useOrderAnalytics(
    requestKey(context, token, target, view, selection, retry),
    async signal => {
      const result = await getReplenishmentPosition(token, target, view, selection, signal)
      if (!match(result, target)) throw new Error('order analytics target mismatch')
      if (view === 'demo' && selection.run_id && result.run_id && result.run_id !== selection.run_id) {
        throw new Error('order analytics simulation mismatch')
      }
      return result
    }, isPending,
  )
  const validRop = data?.state === 'available' && data.rop !== null && Number.isFinite(data.rop) && data.rop >= 0 && data.projected_quantity !== null
    && (view === 'demo' ? data.dataset_class === 'fixture' : Boolean(data.dataset_class && !['fixture', 'research'].includes(data.dataset_class)))
  const title = view === 'demo' ? 'Tham chiếu demo: tồn dự kiến so với ROP mô phỏng' : 'Tồn dự kiến (tạm tính)'
  return <section className="replenishment-panel" aria-label={title}>
    {view === 'demo' ? <h3>{title}</h3> : <h2>{title}</h2>}
    <Status data={data} error={error} retry={() => setRetry(n => n + 1)} />
    {view === 'demo' && <p>Dữ liệu demo/fixture; ROP thuộc ngày mô phỏng, không phải ngưỡng vận hành đã phê duyệt.</p>}
    {data && <>
      <dl className="replenishment-facts">
        <div><dt>Tồn thực</dt><dd>{amount(data.on_hand, data.unit)}</dd></div>
        <div><dt>Lượng chờ giao</dt><dd>{amount(data.open_quantity, data.unit)}</dd></div>
        <div><dt>Tồn dự kiến = tồn thực − lượng chờ</dt><dd>{amount(data.projected_quantity, data.unit)}</dd></div>
      </dl>
      {validRop && <>
        <p>ROP {data.rop_date ? `ngày ${data.rop_date}` : 'tham chiếu'}: {amount(data.rop, data.unit)}.</p>
        {view === 'demo' && data.projected_quantity !== null && data.rop !== null && <p>{data.projected_quantity <= data.rop ? 'Tồn dự kiến tại hoặc dưới ROP mô phỏng.' : 'Tồn dự kiến trên ROP mô phỏng.'}</p>}
        {view === 'operational' && data.recommendation && <FeedbackMessage variant="warning">Đề xuất xem xét bổ sung</FeedbackMessage>}
        {data.eoq !== null && Number.isSafeInteger(data.eoq) && data.eoq > 0 && <p>Lượng đặt tham khảo theo EOQ: {amount(data.eoq, data.unit)}.</p>}
      </>}
    </>}
  </section>
}

export function OrderChecksPanel({ token, context }: { token: string; context: string }) {
  const [warehouseId, setWarehouseId] = useState('')
  const [warehouseRetry, setWarehouseRetry] = useState(0)
  const { data: warehouses, error: warehouseError } = useOrderAnalytics(
    requestKey(context, token, warehouseRetry),
    signal => getOrderWarehouses(token, signal),
    () => false,
  )
  const selectedWarehouse = warehouses?.find(item => String(item.id) === warehouseId)
  const [productInput, setProductInput] = useState('')
  const [target, setTarget] = useState<AnalyticsTarget | null>(null)
  const [page, setPage] = useState(1)
  const [retry, setRetry] = useState(0)
  const { data, error } = useOrderAnalytics(
    target ? requestKey(context, token, target, page, retry) : null,
    async signal => {
      if (!target) throw new Error('order analytics target missing')
      const result = await getOrderChecks(token, target, page, signal)
      if (result.items.some(item => !match(item, target))) throw new Error('order analytics target mismatch')
      return result
    },
    result => result.items.some(isPending),
  )
  return <section className="anomalies-order-checks" aria-label="Kiểm tra đơn tạm tính">
    <h2>Kiểm tra đơn tạm tính</h2>
    <p>Quy tắc thống kê cho yêu cầu mua B2B, tách riêng khỏi cảnh báo mô hình và SHAP.</p>
    <form className="anomalies-order-checks__filters" onSubmit={event => {
      event.preventDefault()
      const next = analyticsTarget({
        warehouse_id: selectedWarehouse?.id ?? null,
        product_id: /^\d+$/.test(productInput) ? Number(productInput) : null,
      })
      setTarget(next)
      setPage(1)
      setRetry(n => n + 1)
    }}>
      <Select label={'Kho'} required value={selectedWarehouse ? warehouseId : ''}
        disabled={!warehouses?.length}
        placeholder={warehouseError ? 'Không tải được danh sách kho' : warehouses ? (warehouses.length ? 'Chọn kho' : 'Chưa có kho') : 'Đang tải danh sách kho…'}
        options={(warehouses ?? []).map(item => ({ value: item.id, label: item.code + ' - ' + item.name }))}
        onChange={event => { setWarehouseId(event.target.value); setTarget(null) }} />
      {warehouseError && <Button type="button" onClick={() => setWarehouseRetry(n => n + 1)}>{'Tải lại danh sách kho'}</Button>}
      <Input label="ID sản phẩm" type="text" inputMode="numeric" pattern="[1-9][0-9]*" required value={productInput} onChange={event => { setProductInput(event.target.value); setTarget(null) }} />
      <Button type="submit" disabled={!selectedWarehouse}>Xem kiểm tra đơn</Button>
    </form>
    {target && !data && <Status data={null} error={error} retry={() => setRetry(n => n + 1)} />}
    {data && (data.items.length === 0 ? <p>Chưa có kết quả kiểm tra cho kho và sản phẩm này.</p> : <>
      <div className="anomalies-scroll" role="region" aria-label="Cuộn kết quả kiểm tra đơn" tabIndex={0}><DataTable caption="Kết quả kiểm tra đơn tạm tính" rows={data.items} getRowKey={row => row.purchase_request_id} columns={[
        { id: 'request', header: 'ID yêu cầu mua', render: row => row.purchase_request_id },
        { id: 'state', header: 'Trạng thái', render: row => <>{labels[row.state]}{row.reason_code && reasons[row.reason_code] ? `: ${reasons[row.reason_code]}` : ''}</> },
        { id: 'flag', header: 'Kết luận của quy tắc', render: row => row.flagged === true ? 'Cần xem xét' : row.flagged === false ? 'Không có cờ' : 'Chưa đánh giá' },
        { id: 'samples', header: 'Số mẫu', render: row => row.sample_count ?? 'Chưa có' },
        { id: 'score', header: 'Điểm', render: row => row.score === null ? 'Không xác định' : format.format(row.score) },
        { id: 'at', header: 'Thời điểm tính', render: row => row.computed_at ? formatDateTime(row.computed_at) : 'Chưa có' },
      ]} /></div>
      <Pagination locale="vi" page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
    </>)}
  </section>
}
