import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './warehouses.css'
import { buildInventoryRows, type InventoryRow } from '../shared/lib/inventory'
import { formatNumber, formatQuantity } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'
import type { Warehouse } from '../types'

const errorMessage = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Không thể tải chi tiết kho hàng. Vui lòng thử lại sau.'

export function WarehouseDetailPage() {
  const { id } = useParams()
  const warehouseId = Number(id)
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [warehouse, setWarehouse] = useState<Warehouse | null>(null)
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    if (!Number.isInteger(warehouseId)) { setLoading(false); return }
    let active = true
    void Promise.all([api.warehouse(token, warehouseId), api.stock(token), api.products()])
      .then(([nextWarehouse, stocks, productPage]) => {
        if (!active) return
        setWarehouse(nextWarehouse)
        setRows(buildInventoryRows({ warehouses: [nextWarehouse], stocks, products: productPage.items }).filter((row) => row.warehouseId === warehouseId))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, token, warehouseId])

  const totalQuantity = rows.reduce((total, row) => total + row.quantity, 0)
  const canWrite = can(user?.role, 'warehouse:write')
  const columns: DataTableColumn<InventoryRow>[] = [
    { id: 'product', header: 'Sản phẩm', render: (row) => <div className="warehouse-name-cell"><strong>{row.productName}</strong><span>{row.sku}</span></div> },
    { id: 'quantity', header: 'Tồn kho', render: (row) => <strong>{formatQuantity(row.quantity, row.unit)}</strong> },
    { id: 'reorder', header: 'Tối thiểu', render: (row) => formatQuantity(row.reorderLevel, row.unit) },
    { id: 'status', header: 'Trạng thái', render: (row) => <Badge variant={row.status === 'low' ? 'warning' : 'success'}>{row.status === 'low' ? 'Sắp hết hàng' : 'Ổn định'}</Badge> },
    { id: 'action', header: <span className="visually-hidden">Thao tác</span>, render: (row) => <Button onClick={() => navigate(`/inventory/${row.warehouseId}/${row.productId}`)} size="small" variant="ghost">Chi tiết</Button> },
  ]

  if (error) return <FeedbackMessage variant="error">{error}</FeedbackMessage>
  if (loading) return <FeedbackMessage>Đang tải chi tiết kho hàng...</FeedbackMessage>
  if (!warehouse) return <EmptyState action={<Button onClick={() => navigate('/warehouses')} variant="secondary">Quay lại kho hàng</Button>} description="Kho hàng này không còn tồn tại hoặc bạn không có quyền truy cập." title="Không tìm thấy kho hàng" />
  const coordinate = warehouse.latitude === null || warehouse.longitude === null ? 'Chưa cập nhật' : `${warehouse.latitude}, ${warehouse.longitude}`

  return <section className="warehouse-detail-page">
    <PageHeader actions={<div className="warehouse-page-actions"><Button onClick={() => navigate('/warehouses')} variant="secondary">Quay lại</Button>{canWrite && <Button onClick={() => navigate(`/warehouses/${warehouse.id}/edit`)}>Chỉnh sửa kho</Button>}</div>} description="Theo dõi thông tin và tồn kho tại một địa điểm." title="Chi tiết kho hàng" />
    <section className="warehouse-summary-card"><div><span className="warehouse-summary-card__code">{warehouse.code}</span><h2>{warehouse.name}</h2><p>{warehouse.address}</p></div><dl><div><dt>Tổng sản phẩm</dt><dd>{formatNumber(rows.length)}</dd></div><div><dt>Tổng tồn kho</dt><dd>{formatNumber(totalQuantity)}</dd></div><div><dt>Tọa độ</dt><dd>{coordinate}</dd></div></dl></section>
    <section className="warehouse-detail-card"><div className="warehouses-list-card__header"><div><h2>Tồn kho tại kho</h2><p>Các sản phẩm hiện có tại {warehouse.name}.</p></div></div>{rows.length === 0 ? <EmptyState description="Chưa có sản phẩm nào được ghi nhận trong kho này." title="Chưa có dữ liệu tồn kho" /> : <DataTable caption={`Tồn kho tại ${warehouse.name}`} columns={columns} getRowKey={(row) => row.id} rows={rows} />}</section>
  </section>
}
