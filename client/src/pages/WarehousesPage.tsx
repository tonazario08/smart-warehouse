import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './warehouses.css'
import './warehouses-list-remediation.css'
import searchIcon from '../shared/assets/figma/search.svg'
import editIcon from '../shared/assets/figma/edit.svg'
import kpiBlue from '../shared/assets/figma/kpi-blue.svg'
import previousIcon from '../shared/assets/figma/product-previous.svg'
import nextIcon from '../shared/assets/figma/product-next.svg'
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
import { Select } from '../shared/ui/Select'

const errorMessage = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Không thể tải dữ liệu kho hàng. Vui lòng thử lại sau.'

export function WarehousesPage() {
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [warehouses, setWarehouses] = useState<(WarehouseSummary & { outStockCount: number })[]>([])
  const [search, setSearch] = useState('')
  const [stockFilter, setStockFilter] = useState('')
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true); setError('')
    void Promise.all([api.warehouses(token), api.stock(token), api.productsAll()])
      .then(([warehouseList, stocks, products]) => {
        if (!active) return
        const rows: InventoryRow[] = buildInventoryRows({ warehouses: warehouseList, stocks, products })
        setWarehouses(buildWarehouseSummaries({ warehouses: warehouseList, rows }).map((warehouse) => ({ ...warehouse, outStockCount: rows.filter((row) => row.warehouseId === warehouse.id && row.status === 'out').length })))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, refresh, token])

  const filteredWarehouses = useMemo(() => filterWarehouseSummaries(warehouses, search).filter((warehouse) => {
    const attention = warehouse.lowStockCount + (warehouse as WarehouseSummary & { outStockCount: number }).outStockCount
    return stockFilter === '' || (stockFilter === 'attention' ? attention > 0 : stockFilter === 'stocked' ? warehouse.totalQuantity > 0 : warehouse.productCount === 0)
  }), [search, stockFilter, warehouses])
  const pageCount = Math.max(1, Math.ceil(filteredWarehouses.length / 10))
  const visiblePage = Math.min(page, pageCount)
  const visibleWarehouses = filteredWarehouses.slice((visiblePage - 1) * 10, visiblePage * 10)
  const totalQuantity = warehouses.reduce((total, warehouse) => total + warehouse.totalQuantity, 0)
  const attentionWarehouses = warehouses.filter((warehouse) => warehouse.lowStockCount + warehouse.outStockCount > 0)
  const stockedWarehouseCount = warehouses.filter((warehouse) => warehouse.totalQuantity > 0).length
  const canWrite = can(user?.role, 'warehouse:write')
  const columns: DataTableColumn<WarehouseSummary>[] = [
    { id: 'code', header: 'Mã kho', render: (warehouse) => <strong>{warehouse.code}</strong> },
    { id: 'name', header: 'Tên kho', render: (warehouse) => <strong>{warehouse.name}</strong> },
    { id: 'address', header: 'Địa chỉ', render: (warehouse) => warehouse.address },
    { id: 'products', header: 'Sản phẩm', render: (warehouse) => `${formatNumber(warehouse.productCount)} mặt hàng` },
    { id: 'quantity', header: 'Tổng tồn', render: (warehouse) => <strong>{formatNumber(warehouse.totalQuantity)}</strong> },
    { id: 'alerts', header: 'Tình trạng tồn kho', render: (warehouse) => {
      const outCount = (warehouse as WarehouseSummary & { outStockCount: number }).outStockCount
      return warehouse.productCount === 0 ? <Badge>Chưa có dữ liệu</Badge> : outCount > 0 ? <Badge variant="danger">{formatNumber(outCount)} hết hàng</Badge> : warehouse.lowStockCount > 0 ? <Badge variant="warning">{formatNumber(warehouse.lowStockCount)} sắp hết hàng</Badge> : <Badge variant="success">Ổn định</Badge>
    } },
    { id: 'actions', header: <span className="visually-hidden">Thao tác</span>, render: (warehouse) => <div className="warehouse-table-actions">
      <Button aria-label={`Xem chi tiết ${warehouse.name}`} className="warehouse-table__icon-action" onClick={() => navigate(`/warehouses/${warehouse.id}`)} size="small" title={`Xem chi tiết ${warehouse.name}`} variant="ghost"><img alt="" src={editIcon} /></Button>
      {canWrite && <Button aria-label={`Chỉnh sửa ${warehouse.name}`} className="warehouse-table__icon-action" onClick={() => navigate(`/warehouses/${warehouse.id}/edit`)} size="small" title={`Chỉnh sửa ${warehouse.name}`} variant="secondary"><img alt="" src={editIcon} /></Button>}
    </div> },
  ]

  return <section className="warehouses-page warehouses-list-remediation">
    <PageHeader actions={canWrite ? <Button onClick={() => navigate('/warehouses/new')}><span aria-hidden="true">+</span> Thêm kho hàng</Button> : undefined} description="Quản lý các kho hàng và theo dõi tồn kho tại từng địa điểm." title="Kho hàng" />
    {loading ? <FeedbackMessage>Đang tải danh sách kho hàng...</FeedbackMessage> : error ? <div className="warehouse-load-error"><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRefresh((value) => value + 1)} variant="secondary">Thử lại</Button></div> : <>
      <section aria-label="Chỉ số kho hàng" className="warehouses-kpis"><article className="warehouse-kpi"><span>Tổng số kho<img alt="" src={kpiBlue} /></span><strong>{formatNumber(warehouses.length)}</strong><small>Tất cả địa điểm</small></article><article className="warehouse-kpi"><span>Kho có tồn kho<img alt="" src={kpiBlue} /></span><strong>{formatNumber(stockedWarehouseCount)}</strong><small>Có số lượng tồn lớn hơn 0</small></article><article className="warehouse-kpi"><span>Tổng lượng tồn<img alt="" src={kpiBlue} /></span><strong>{formatNumber(totalQuantity)}</strong><small>Trên toàn hệ thống</small></article><article className="warehouse-kpi"><span>Kho cần chú ý<img alt="" src={kpiBlue} /></span><strong>{formatNumber(attentionWarehouses.length)}</strong><small>Có sản phẩm sắp hết hoặc hết hàng</small></article></section>
      <div className="warehouse-list-toolbar"><Input aria-label="Tìm kiếm kho hàng" leadingIcon={<img alt="" src={searchIcon} />} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Tìm theo tên, mã kho hoặc địa chỉ..." value={search} /><Select aria-label="Lọc theo tồn kho" onChange={(event) => { setStockFilter(event.target.value); setPage(1) }} options={[{ label: 'Cần chú ý', value: 'attention' }, { label: 'Có tồn kho', value: 'stocked' }, { label: 'Chưa có dữ liệu', value: 'empty' }]} placeholder="Tất cả tình trạng tồn kho" value={stockFilter} /><Button onClick={() => { setSearch(''); setStockFilter(''); setPage(1) }} variant="secondary">Đặt lại bộ lọc</Button></div>
      <section className="warehouses-list-card">{filteredWarehouses.length === 0 ? <EmptyState description={warehouses.length === 0 ? 'Hãy thêm kho hàng đầu tiên để bắt đầu quản lý.' : 'Không tìm thấy kho hàng phù hợp với điều kiện lọc.'} title={warehouses.length === 0 ? 'Chưa có kho hàng' : 'Không có kết quả'} /> : <DataTable caption="Danh sách kho hàng" columns={columns} getRowKey={(warehouse) => warehouse.id} rows={visibleWarehouses} />}<div className="warehouse-pagination"><span aria-live="polite">Hiển thị {filteredWarehouses.length === 0 ? 0 : (visiblePage - 1) * 10 + 1}–{Math.min(visiblePage * 10, filteredWarehouses.length)} trong {formatNumber(filteredWarehouses.length)} kho hàng</span><div><Button aria-label="Trang kho hàng trước" className="ui-pagination-button" disabled={visiblePage <= 1} onClick={() => setPage(visiblePage - 1)} size="small" variant="secondary"><img alt="" src={previousIcon} /></Button><span>Trang {visiblePage}/{pageCount}</span><Button aria-label="Trang kho hàng tiếp theo" className="ui-pagination-button" disabled={visiblePage >= pageCount} onClick={() => setPage(visiblePage + 1)} size="small" variant="secondary"><img alt="" src={nextIcon} /></Button></div></div></section>
      <section className="warehouse-attention-card"><h2>Kho cần chú ý</h2><p>Các kho có sản phẩm sắp hết hoặc hết hàng theo mức tồn tối thiểu.</p>{attentionWarehouses.length === 0 ? <EmptyState description="Chưa ghi nhận cảnh báo từ các bản ghi tồn kho hiện có." title="Không có cảnh báo tồn kho" /> : <ul>{attentionWarehouses.map((warehouse) => <li key={warehouse.id}><div><strong>{warehouse.name}</strong><span>{warehouse.address}</span></div><div><span>{formatNumber(warehouse.lowStockCount)} sắp hết hàng · {formatNumber(warehouse.outStockCount)} hết hàng</span><Button onClick={() => navigate(`/warehouses/${warehouse.id}`)} size="small" variant="secondary">Xem chi tiết</Button></div></li>)}</ul>}</section>
    </>}
  </section>
}
