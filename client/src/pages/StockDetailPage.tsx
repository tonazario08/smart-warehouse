import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './inventory.css'
import { buildInventoryRows, type InventoryRow } from '../shared/lib/inventory'
import { formatQuantity } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'

const errorMessage = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Không thể tải chi tiết tồn kho. Vui lòng thử lại sau.'

export function StockDetailPage() {
  const { warehouseId: warehouseIdParam, productId: productIdParam } = useParams()
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const warehouseId = Number(warehouseIdParam)
  const productId = Number(productIdParam)

  useEffect(() => {
    if (!token) return
    let active = true
    void Promise.all([api.stock(token), api.products(), api.warehouses(token)])
      .then(([stocks, productPage, warehouses]) => { if (active) setRows(buildInventoryRows({ stocks, products: productPage.items, warehouses })) })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, token])

  const row = useMemo(() => rows.find((item) => item.warehouseId === warehouseId && item.productId === productId), [productId, rows, warehouseId])
  if (error) return <FeedbackMessage variant="error">{error}</FeedbackMessage>
  if (loading) return <FeedbackMessage>Đang tải chi tiết tồn kho...</FeedbackMessage>
  if (!row) return <EmptyState action={<Button onClick={() => navigate('/inventory')} variant="secondary">Quay lại tồn kho</Button>} description="Bản ghi tồn kho này không còn tồn tại hoặc bạn không có quyền truy cập." title="Không tìm thấy tồn kho" />

  const statusLabel = row.status === 'low' ? 'Sắp hết hàng' : 'Ổn định'
  const level = Math.min(100, Math.round((row.quantity / Math.max(row.reorderLevel, 1)) * 100))
  const canAdjustStock = can(user?.role, 'inventory:write')

  return <section className="stock-detail-page">
    <PageHeader actions={<Button onClick={() => navigate('/inventory')} variant="secondary">Quay lại</Button>} description="Theo dõi tình trạng và mức tồn tối thiểu của một sản phẩm tại kho hàng." title="Chi tiết tồn kho" />
    <section className="stock-summary-card">
      <div className="stock-summary-card__header"><div><span className="stock-summary-card__eyebrow">{row.sku}</span><h2>{row.productName}</h2><p>{row.warehouseName}</p></div><Badge variant={row.status === 'low' ? 'warning' : 'success'}>{statusLabel}</Badge></div>
      <dl className="stock-summary-card__metrics"><div><dt>Tồn hiện tại</dt><dd>{formatQuantity(row.quantity, row.unit)}</dd></div><div><dt>Mức tồn tối thiểu</dt><dd>{formatQuantity(row.reorderLevel, row.unit)}</dd></div><div><dt>Kho hàng</dt><dd>{row.warehouseName}</dd></div></dl>
    </section>
    <section className="stock-detail-grid">
      <article className="stock-panel"><div className="stock-panel__header"><div><h2>Tình trạng tồn kho</h2><p>So sánh số lượng hiện tại với mức tồn tối thiểu.</p></div><strong>{level}%</strong></div><div aria-label={`Mức tồn kho ${level}%`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={level} className="stock-level" role="progressbar"><span style={{ width: `${level}%` }} /></div><div className="stock-level__labels"><span>0 {row.unit}</span><span>Mức tối thiểu: {formatQuantity(row.reorderLevel, row.unit)}</span></div></article>
      <article className="stock-panel stock-panel--actions"><div><h2>Thao tác tồn kho</h2><p>Phiếu nhập và xuất kho được quản lý theo quyền của bạn.</p></div>{canAdjustStock ? <div className="stock-panel__actions"><Button onClick={() => navigate('/inbound/new')}>Tạo phiếu nhập</Button><Button onClick={() => navigate('/outbound/new')} variant="secondary">Tạo phiếu xuất</Button></div> : <p className="stock-panel__unavailable">Bạn chỉ có quyền xem dữ liệu tồn kho.</p>}</article>
    </section>
    <section className="stock-panel stock-history"><div className="stock-panel__header"><div><h2>Lịch sử biến động gần đây</h2><p>Theo dõi các lần nhập và xuất liên quan đến bản ghi này.</p></div></div><EmptyState description="API hiện chưa cung cấp thời gian, người thực hiện và tham chiếu giao dịch để hiển thị lịch sử biến động đầy đủ." title="Lịch sử biến động chưa khả dụng" /></section>
  </section>
}
