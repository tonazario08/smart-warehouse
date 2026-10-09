import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './warehouses.css'
import { buildInventoryRows, type InventoryRow } from '../shared/lib/inventory'
import { buildWarehouseSummaries, filterWarehouseSummaries, type WarehouseSummary } from '../shared/lib/warehouses'
import { formatNumber } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'

const errorMessage = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Không thể tải dữ liệu kho hàng. Vui lòng thử lại sau.'

export function WarehousesPage() {
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [warehouses, setWarehouses] = useState<WarehouseSummary[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    void Promise.all([api.warehouses(token), api.stock(token), api.products()])
      .then(([warehouseList, stocks, productPage]) => {
        if (!active) return
        const rows: InventoryRow[] = buildInventoryRows({ warehouses: warehouseList, stocks, products: productPage.items })
        setWarehouses(buildWarehouseSummaries({ warehouses: warehouseList, rows }))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, token])

  const filteredWarehouses = useMemo(() => filterWarehouseSummaries(warehouses, search), [search, warehouses])
  const totalQuantity = warehouses.reduce((total, warehouse) => total + warehouse.totalQuantity, 0)
  const lowStockCount = warehouses.reduce((total, warehouse) => total + warehouse.lowStockCount, 0)
  const canWrite = can(user?.role, 'warehouse:write')
  const columns: DataTableColumn<WarehouseSummary>[] = [
    { id: 'code', header: 'Mã kho', render: (warehouse) => <strong>{warehouse.code}</strong> },
    { id: 'name', header: 'Kho hàng', render: (warehouse) => <div className="warehouse-name-cell"><strong>{warehouse.name}</strong><span>{warehouse.address}</span></div> },
    { id: 'products', header: 'Sản phẩm', render: (warehouse) => `${formatNumber(warehouse.productCount)} mặt hàng` },
    { id: 'quantity', header: 'Tổng tồn', render: (warehouse) => <strong>{formatNumber(warehouse.totalQuantity)}</strong> },
    { id: 'alerts', header: 'Cảnh báo', render: (warehouse) => warehouse.lowStockCount > 0 ? <Badge variant="warning">{formatNumber(warehouse.lowStockCount)} cần theo dõi</Badge> : <Badge variant="success">Ổn định</Badge> },
    { id: 'actions', header: <span className="visually-hidden">Thao tác</span>, render: (warehouse) => <div className="warehouse-table-actions"><Button aria-label={`Xem chi tiết ${warehouse.name}`} onClick={() => navigate(`/warehouses/${warehouse.id}`)} size="small" variant="ghost">Chi tiết</Button>{canWrite && <Button aria-label={`Chỉnh sửa ${warehouse.name}`} onClick={() => navigate(`/warehouses/${warehouse.id}/edit`)} size="small" variant="secondary">Sửa</Button>}</div> },
  ]

  return <section className="warehouses-page">
    <PageHeader actions={canWrite ? <Button onClick={() => navigate('/warehouses/new')}><span aria-hidden="true">+</span> Thêm kho hàng</Button> : undefined} description="Quản lý các kho hàng và theo dõi tình trạng vận hành." title="Kho hàng" />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải danh sách kho hàng...</FeedbackMessage> : <>
      <section aria-label="Chỉ số kho hàng" className="warehouses-kpis"><article className="warehouse-kpi"><span>Tổng số kho</span><strong>{formatNumber(warehouses.length)}</strong><small>Tất cả địa điểm</small></article><article className="warehouse-kpi"><span>Tổng số lượng tồn</span><strong>{formatNumber(totalQuantity)}</strong><small>Tổng đơn vị đang lưu kho</small></article><article className="warehouse-kpi warehouse-kpi--warning"><span>Cần theo dõi</span><strong>{formatNumber(lowStockCount)}</strong><small>Bản ghi đạt hoặc dưới mức tối thiểu</small></article></section>
      <section className="warehouses-list-card"><div className="warehouses-list-card__header"><div><h2>Danh sách kho hàng</h2><p>Thông tin tổng quan và tình trạng tồn kho theo từng kho.</p></div><Input aria-label="Tìm kiếm kho hàng" onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo mã kho, tên kho..." value={search} /></div>{filteredWarehouses.length === 0 ? <EmptyState description={warehouses.length === 0 ? 'Hãy thêm kho hàng đầu tiên để bắt đầu quản lý.' : 'Không tìm thấy kho hàng phù hợp với từ khóa.'} title={warehouses.length === 0 ? 'Chưa có kho hàng' : 'Không có kết quả'} /> : <DataTable caption="Danh sách kho hàng" columns={columns} getRowKey={(warehouse) => warehouse.id} rows={filteredWarehouses} />}</section>
    </>}
  </section>
}
