import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './inventory.css'
import { buildInventoryRows, getStockScale, inventoryStatusLabels, inventoryStatusVariants, type InventoryRow } from '../shared/lib/inventory'
import { formatDateTime, formatQuantity } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import type { MovementRead } from '../types'

type HistoryRow = MovementRead & { type: 'inbound' | 'outbound' }
const historyColumns: DataTableColumn<HistoryRow>[] = [
  { id: 'time', header: 'Thời gian', render: item => formatDateTime(item.created_at) },
  { id: 'type', header: 'Loại', render: item => item.type === 'inbound' ? 'Nhập kho' : 'Xuất kho' },
  { id: 'quantity', header: 'Số lượng', render: item => item.quantity.toLocaleString('vi-VN') },
  { id: 'reference', header: 'Mã phiếu', render: item => item.reference || '—' },
  { id: 'note', header: 'Ghi chú', render: item => item.note || '—' },
  { id: 'actor', header: 'Người thực hiện', render: item => `Tài khoản #${item.created_by_id}` },
]

export function StockDetailPage() {
  const { warehouseId: warehouseIdParam, productId: productIdParam } = useParams()
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [history, setHistory] = useState<HistoryRow[]>([])
  const [historyError, setHistoryError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(false)
  const warehouseId = Number(warehouseIdParam)
  const productId = Number(productIdParam)
  const canReadHistory = can(user?.role, 'inventory:write')

  useEffect(() => {
    setHistory([])
    setHistoryError('')
    if (!token || !canReadHistory || !Number.isInteger(warehouseId) || warehouseId < 1 || !Number.isInteger(productId) || productId < 1) return
    let active = true
    setHistoryLoading(true)
    const filters = { warehouse_id: warehouseId, product_id: productId }
    void Promise.all([api.inbounds(token, filters), api.outbounds(token, filters)])
      .then(([inbounds, outbounds]) => {
        if (active) setHistory([
          ...inbounds.map(item => ({ ...item, type: 'inbound' as const })),
          ...outbounds.map(item => ({ ...item, type: 'outbound' as const })),
        ].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at) || right.id - left.id))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setHistoryError(cause instanceof ApiError ? cause.message : 'Không thể tải lịch sử. Vui lòng thử lại.')
      })
      .finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [canReadHistory, logout, productId, reload, token, warehouseId])

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    setError('')
    void Promise.all([api.stock(token), api.productsAll(token), api.warehouses(token)])
      .then(([stocks, products, warehouses]) => { if (active) setRows(buildInventoryRows({ stocks, products, warehouses })) })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setError('Không thể tải chi tiết tồn kho. Vui lòng thử lại.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, reload, token, warehouseId, productId])

  const row = useMemo(() => rows.find(item => item.warehouseId === warehouseId && item.productId === productId), [productId, rows, warehouseId])
  if (error) return <FeedbackMessage variant="error">{error} <Button onClick={() => setReload(value => value + 1)} size="small" variant="secondary">Thử lại</Button></FeedbackMessage>
  if (loading) return <FeedbackMessage>Đang tải chi tiết tồn kho...</FeedbackMessage>
  if (!row) return <EmptyState action={<Button onClick={() => navigate('/inventory')} variant="secondary">Quay lại tồn kho</Button>} description="Bản ghi tồn kho này không còn tồn tại hoặc bạn không có quyền truy cập." title="Không tìm thấy tồn kho" />

  const scale = getStockScale(row.quantity, row.reorderLevel)
  const canAdjustStock = can(user?.role, 'inventory:write')

  return <section className="stock-detail-page">
    <PageHeader description={`${row.productName} tại ${row.warehouseName}`} title="Chi tiết tồn kho" />
    <section className="stock-detail-card">
      <article className="stock-panel stock-summary-card"><h2>Tổng quan tồn kho</h2><dl className="stock-summary-card__rows">
        <div><dt>SKU</dt><dd>{row.sku}</dd></div>
        <div><dt>Sản phẩm</dt><dd>{row.productName}</dd></div>
        <div><dt>Kho hàng</dt><dd>{row.warehouseName}</dd></div>
        <div><dt>Số lượng hiện tại</dt><dd>{formatQuantity(row.quantity, row.unit)}</dd></div>
        <div><dt>Mức tồn tối thiểu</dt><dd>{formatQuantity(row.reorderLevel, row.unit)}</dd></div>
        <div><dt>Tình trạng</dt><dd><Badge variant={inventoryStatusVariants[row.status]}>{inventoryStatusLabels[row.status]}</Badge></dd></div>
      </dl></article>
      <article className="stock-panel"><h2>Tình trạng tồn kho</h2><div className="stock-level__labels"><span>Tồn hiện tại</span><span>Mức tối thiểu</span></div><div className="stock-level__values"><strong>{formatQuantity(row.quantity, row.unit)}</strong><strong>{formatQuantity(row.reorderLevel, row.unit)}</strong></div><div aria-label="So sánh tồn hiện tại với mức tối thiểu" aria-valuemax={scale.maximum} aria-valuemin={0} aria-valuenow={row.quantity} aria-valuetext={`Tồn hiện tại ${formatQuantity(row.quantity, row.unit)}, mức tối thiểu ${formatQuantity(row.reorderLevel, row.unit)}`} className="stock-level" role="meter"><span className="stock-level__fill" style={{ width: `${scale.currentPercent}%` }} /><span className="stock-level__minimum" style={{ left: `${scale.minimumPercent}%` }} /></div></article>
      <article className="stock-panel stock-history"><h2>Lịch sử biến động gần đây</h2>{!canReadHistory ? <p>Bạn không có quyền xem lịch sử nhập và xuất kho.</p> : historyLoading ? <FeedbackMessage>Đang tải lịch sử...</FeedbackMessage> : historyError ? <FeedbackMessage variant="error">{historyError} <Button onClick={() => setReload(value => value + 1)} size="small" variant="secondary">Thử lại</Button></FeedbackMessage> : <DataTable caption="Lịch sử nhập và xuất của sản phẩm tại kho" columns={historyColumns} emptyMessage="Chưa có biến động tồn kho." getRowKey={item => item.type + item.id} rows={history.slice(0, 10)} />}</article>
      <div className="stock-panel__actions">{canAdjustStock ? <><Button onClick={() => navigate('/inbound/new')}><span aria-hidden="true">+</span> Tạo phiếu nhập</Button><Button onClick={() => navigate('/outbound/new')} variant="secondary">Tạo phiếu xuất</Button></> : <p className="stock-panel__unavailable">Bạn chỉ có quyền xem dữ liệu tồn kho.</p>}<Button onClick={() => navigate('/inventory')} variant="ghost">Quay lại tồn kho</Button></div>
    </section>
  </section>
}
