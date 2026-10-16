import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './warehouses.css'
import './warehouses-list-remediation.css'
import searchIcon from '../shared/assets/figma/search.svg'
import kpiBlue from '../shared/assets/figma/kpi-blue.svg'
import { buildInventoryRows, filterInventoryRows, inventoryStatusLabels, inventoryStatusVariants, type InventoryRow, type InventoryStatus } from '../shared/lib/inventory'
import { formatNumber, formatQuantity } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'
import { Input } from '../shared/ui/Input'
import { Select } from '../shared/ui/Select'
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
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<InventoryStatus | ''>('')
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    if (!token) return
    if (!Number.isInteger(warehouseId) || warehouseId <= 0) {
      setWarehouse(null)
      setRows([])
      setError('')
      setLoading(false)
      return
    }
    let active = true
    setLoading(true); setError('')
    void Promise.all([api.warehouse(token, warehouseId), api.stock(token), api.productsAll(token)])
      .then(([nextWarehouse, stocks, products]) => {
        if (!active) return
        setWarehouse(nextWarehouse)
        setRows(buildInventoryRows({ warehouses: [nextWarehouse], stocks, products }).filter((row) => row.warehouseId === warehouseId))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, refresh, token, warehouseId])

  const totalQuantity = rows.reduce((total, row) => total + row.quantity, 0)
  const productCount = new Set(rows.map((row) => row.productId)).size
  const lowCount = rows.filter((row) => row.status === 'low').length
  const outCount = rows.filter((row) => row.status === 'out').length
  const filteredRows = filterInventoryRows(rows, { search, status, warehouseId })
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / 10))
  const visiblePage = Math.min(page, pageCount)
  const canWrite = can(user?.role, 'warehouse:write')
  const columns: DataTableColumn<InventoryRow>[] = [
    { id: 'sku', header: 'SKU', render: (row) => <strong>{row.sku}</strong> },
    { id: 'product', header: 'Sản phẩm', render: (row) => <Button className="warehouse-product-link" onClick={() => navigate(`/inventory/${row.warehouseId}/${row.productId}`)} size="small" variant="ghost">{row.productName}</Button> },
    { id: 'quantity', header: 'Tồn kho', render: (row) => <strong>{formatQuantity(row.quantity, row.unit)}</strong> },
    { id: 'reorder', header: 'Tối thiểu', render: (row) => formatQuantity(row.reorderLevel, row.unit) },
    { id: 'status', header: 'Trạng thái', render: (row) => <Badge variant={inventoryStatusVariants[row.status]}>{inventoryStatusLabels[row.status]}</Badge> },
    { id: 'action', header: <span className="visually-hidden">Thao tác</span>, render: (row) => <Button onClick={() => navigate(`/inventory/${row.warehouseId}/${row.productId}`)} size="small" variant="ghost">Chi tiết</Button> },
  ]

  if (error) return <div className="warehouse-load-error"><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRefresh((value) => value + 1)} variant="secondary">Thử lại</Button><Button onClick={() => navigate('/warehouses')} variant="ghost">Quay lại kho hàng</Button></div>
  if (loading) return <FeedbackMessage>Đang tải chi tiết kho hàng...</FeedbackMessage>
  if (!warehouse) return <EmptyState action={<Button onClick={() => navigate('/warehouses')} variant="secondary">Quay lại kho hàng</Button>} description="Kho hàng này không còn tồn tại hoặc bạn không có quyền truy cập." title="Không tìm thấy kho hàng" />
  const hasCoordinates = warehouse.latitude !== null && warehouse.longitude !== null

  return <section className="warehouse-detail-page warehouse-detail-remediation">
    <PageHeader actions={<div className="warehouse-page-actions"><Button onClick={() => navigate('/warehouses')} variant="ghost">Quay lại</Button>{canWrite && <Button onClick={() => navigate(`/warehouses/${warehouse.id}/edit`)} variant="secondary">Chỉnh sửa kho</Button>}</div>} description={`${warehouse.code} · ${warehouse.address}`} title={warehouse.name} />
    <section className="warehouse-detail-card">
      <section className="warehouse-detail-section"><h2>Thông tin kho</h2><dl className="warehouse-info-rows"><div><dt>Mã kho</dt><dd>{warehouse.code}</dd></div><div><dt>Tên kho</dt><dd>{warehouse.name}</dd></div><div><dt>Địa chỉ</dt><dd>{warehouse.address}</dd></div><div><dt>Tổng sản phẩm</dt><dd>{formatNumber(productCount)}</dd></div><div><dt>Tổng tồn kho</dt><dd>{formatNumber(totalQuantity)}</dd></div></dl></section>
      <section className="warehouse-detail-section"><h2>Vị trí kho</h2><dl className="warehouse-location-rows"><div><dt>Địa chỉ</dt><dd>{warehouse.address}</dd></div><div><dt>Vĩ độ</dt><dd>{warehouse.latitude === null ? 'Chưa cập nhật' : warehouse.latitude}</dd></div><div><dt>Kinh độ</dt><dd>{warehouse.longitude === null ? 'Chưa cập nhật' : warehouse.longitude}</dd></div></dl>{hasCoordinates ? <a className="warehouse-map-link" href={`https://www.openstreetmap.org/?mlat=${warehouse.latitude}&mlon=${warehouse.longitude}#map=16/${warehouse.latitude}/${warehouse.longitude}`} rel="noopener noreferrer" target="_blank">Xem vị trí trên bản đồ</a> : <p className="warehouse-coordinate-note">Cập nhật đủ vĩ độ và kinh độ để xem vị trí trên bản đồ.</p>}</section>
      <section className="warehouse-detail-section"><h2>Sản phẩm trong kho</h2><div className="warehouse-list-toolbar"><Input aria-label="Tìm sản phẩm trong kho" leadingIcon={<img alt="" src={searchIcon} />} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Tìm theo SKU hoặc tên sản phẩm..." value={search} /><Select aria-label="Lọc tình trạng sản phẩm trong kho" onChange={(event) => { setStatus(event.target.value as InventoryStatus | ''); setPage(1) }} options={Object.entries(inventoryStatusLabels).map(([value, label]) => ({ value, label }))} placeholder="Tất cả tình trạng tồn kho" value={status} /><Button onClick={() => { setSearch(''); setStatus(''); setPage(1) }} variant="secondary">Đặt lại bộ lọc</Button></div>{filteredRows.length === 0 ? <EmptyState description={rows.length === 0 ? 'Chưa có sản phẩm nào được ghi nhận trong kho này.' : 'Không tìm thấy sản phẩm phù hợp với điều kiện lọc.'} title={rows.length === 0 ? 'Chưa có dữ liệu tồn kho' : 'Không có kết quả'} /> : <DataTable caption={`Tồn kho tại ${warehouse.name}`} columns={columns} getRowKey={(row) => row.id} rows={filteredRows.slice((visiblePage - 1) * 10, visiblePage * 10)} />}<div className="warehouse-pagination"><span aria-live="polite">Hiển thị {filteredRows.length === 0 ? 0 : (visiblePage - 1) * 10 + 1}–{Math.min(visiblePage * 10, filteredRows.length)} trong {formatNumber(filteredRows.length)} sản phẩm</span><div><Button aria-label="Trang tồn kho trước" disabled={visiblePage <= 1} onClick={() => setPage(visiblePage - 1)} size="small" variant="secondary">Trước</Button><span>Trang {visiblePage}/{pageCount}</span><Button aria-label="Trang tồn kho tiếp theo" disabled={visiblePage >= pageCount} onClick={() => setPage(visiblePage + 1)} size="small" variant="secondary">Sau</Button></div></div></section>
      <section className="warehouse-detail-totals"><h2>Tồn kho tại kho này</h2><div className="warehouses-kpis"><article className="warehouse-kpi"><span>Sản phẩm<img alt="" src={kpiBlue} /></span><strong>{formatNumber(productCount)}</strong><small>Đã ghi nhận trong kho</small></article><article className="warehouse-kpi"><span>Tổng tồn<img alt="" src={kpiBlue} /></span><strong>{formatNumber(totalQuantity)}</strong><small>Tổng số lượng hiện tại</small></article><article className="warehouse-kpi"><span>Sắp hết hàng<img alt="" src={kpiBlue} /></span><strong>{formatNumber(lowCount)}</strong><small>Đạt hoặc dưới mức tối thiểu</small></article><article className="warehouse-kpi"><span>Hết hàng<img alt="" src={kpiBlue} /></span><strong>{formatNumber(outCount)}</strong><small>Số lượng tồn bằng 0</small></article></div></section>
    </section>
  </section>
}
