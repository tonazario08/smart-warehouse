import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './inventory.css'
import kpiBlue from '../shared/assets/figma/kpi-blue.svg'
import editIcon from '../shared/assets/figma/edit.svg'
import previousIcon from '../shared/assets/figma/product-previous.svg'
import nextIcon from '../shared/assets/figma/product-next.svg'
import { buildInventoryRows, filterInventoryRows, inventoryStatusLabels, inventoryStatusVariants, type InventoryRow, type InventoryStatus } from '../shared/lib/inventory'
import { formatNumber, formatQuantity } from '../shared/lib/formatters'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import { Select } from '../shared/ui/Select'
import type { Product, Warehouse } from '../types'

const pageSize = 10

export function InventoryPage() {
  const { logout, token } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [categoryNames, setCategoryNames] = useState<Map<number, string>>(new Map())
  const [search, setSearch] = useState('')
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [status, setStatus] = useState<InventoryStatus | ''>('')
  const [showAllAlerts, setShowAllAlerts] = useState(false)
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    setError('')
    void Promise.all([api.stock(token), api.productsAll(token), api.warehouses(token)])
      .then(([stocks, productList, warehouseList]) => {
        if (!active) return
        setRows(buildInventoryRows({ stocks, products: productList, warehouses: warehouseList }))
        setProducts(productList)
        setWarehouses(warehouseList)
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setError('Không thể tải dữ liệu tồn kho. Vui lòng thử lại.')
      })
      .finally(() => { if (active) setLoading(false) })
    // Category names enrich the filter; a failed lookup must not hide stock data.
    void api.categories(token).then(result => { if (active) setCategoryNames(new Map(result.items.map(category => [category.id, category.name]))) }).catch(() => {})
    return () => { active = false }
  }, [logout, reload, token])

  const categoryProductIds = useMemo(() => categoryId === null ? undefined : new Set(products.filter(product => product.category_id === categoryId).map(product => product.id)), [categoryId, products])
  const filteredRows = useMemo(() => filterInventoryRows(rows, { search, warehouseId, status, categoryProductIds }), [rows, search, warehouseId, status, categoryProductIds])
  const alerts = rows.filter(row => row.status !== 'healthy')
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const pageRows = filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const categoryOptions = [...new Set(products.map(product => product.category_id))].map(id => ({ value: id, label: categoryNames.get(id) ?? `Danh mục #${id}` }))
  const resetFilters = () => { setSearch(''); setWarehouseId(null); setCategoryId(null); setStatus(''); setPage(1) }
  const columns: DataTableColumn<InventoryRow>[] = [
    { id: 'sku', header: 'SKU', render: row => <strong>{row.sku}</strong> },
    { id: 'product', header: 'Sản phẩm', render: row => <strong>{row.productName}</strong> },
    { id: 'warehouse', header: 'Kho hàng', render: row => row.warehouseName },
    { id: 'quantity', header: 'Tồn hiện tại', render: row => formatQuantity(row.quantity, row.unit) },
    { id: 'reorder', header: 'Mức tối thiểu', render: row => formatQuantity(row.reorderLevel, row.unit) },
    { id: 'difference', header: 'Chênh lệch', render: row => <strong className={`inventory-difference inventory-difference--${row.status}`}>{row.quantity - row.reorderLevel > 0 ? '+' : ''}{formatNumber(row.quantity - row.reorderLevel)}</strong> },
    { id: 'status', header: 'Tình trạng', render: row => <Badge variant={inventoryStatusVariants[row.status]}>{inventoryStatusLabels[row.status]}</Badge> },
    { id: 'action', header: 'Thao tác', render: row => <Button aria-label={`Xem chi tiết tồn kho ${row.productName} tại ${row.warehouseName}`} className="ui-icon-button" onClick={() => navigate(`/inventory/${row.warehouseId}/${row.productId}`)} size="small" variant="ghost"><img alt="" src={editIcon} /></Button> },
  ]

  return <section className="inventory-page">
    <PageHeader description="Theo dõi số lượng hàng tồn và tình trạng tồn kho theo từng kho." title="Tồn kho" />
    {error ? <FeedbackMessage variant="error">{error} <Button onClick={() => setReload(value => value + 1)} size="small" variant="secondary">Thử lại</Button></FeedbackMessage> : loading ? <FeedbackMessage>Đang tải dữ liệu tồn kho...</FeedbackMessage> : <>
      <section aria-label="Chỉ số tồn kho" className="inventory-kpis">
        <article className="inventory-kpi"><span>Tổng số lượng tồn<img alt="" src={kpiBlue} /></span><strong>{formatNumber(rows.reduce((sum, row) => sum + row.quantity, 0))}</strong><small>Tổng đơn vị đang lưu kho</small></article>
        <article className="inventory-kpi"><span>Sản phẩm sắp hết<img alt="" src={kpiBlue} /></span><strong>{formatNumber(rows.filter(row => row.status === 'low').length)}</strong><small>Cảnh báo tồn kho theo từng kho</small></article>
        <article className="inventory-kpi"><span>Sản phẩm hết hàng<img alt="" src={kpiBlue} /></span><strong>{formatNumber(rows.filter(row => row.status === 'out').length)}</strong><small>Cần nhập ngay</small></article>
        <article className="inventory-kpi"><span>Số kho hàng<img alt="" src={kpiBlue} /></span><strong>{formatNumber(warehouses.length)}</strong><small>Kho hiện có trong hệ thống</small></article>
      </section>
      <div className="inventory-toolbar">
        <Input aria-label="Tìm kiếm tồn kho" onChange={event => { setSearch(event.target.value); setPage(1) }} placeholder="Tìm theo sản phẩm hoặc SKU..." value={search} />
        <Select aria-label="Lọc theo kho hàng" onChange={event => { setWarehouseId(event.target.value === '' ? null : Number(event.target.value)); setPage(1) }} options={warehouses.map(warehouse => ({ label: warehouse.name, value: warehouse.id }))} placeholder="Kho hàng: Tất cả" value={warehouseId ?? ''} />
        <Select aria-label="Lọc theo danh mục" onChange={event => { setCategoryId(event.target.value === '' ? null : Number(event.target.value)); setPage(1) }} options={categoryOptions} placeholder="Danh mục: Tất cả" value={categoryId ?? ''} />
        <Select aria-label="Lọc theo tình trạng tồn" onChange={event => { setStatus(event.target.value as InventoryStatus | ''); setPage(1) }} options={Object.entries(inventoryStatusLabels).map(([value, label]) => ({ value, label }))} placeholder="Tình trạng: Tất cả" value={status} />
        <Button onClick={resetFilters} variant="secondary">Đặt lại bộ lọc</Button>
      </div>
      <section aria-label="Danh sách tồn kho" className="inventory-list-card">
        {filteredRows.length === 0 ? <EmptyState description={rows.length === 0 ? 'Dữ liệu tồn kho sẽ xuất hiện khi hàng hóa được nhập vào kho.' : 'Không tìm thấy tồn kho phù hợp với điều kiện lọc.'} title={rows.length === 0 ? 'Chưa có dữ liệu tồn kho' : 'Không có kết quả'} /> : <DataTable caption="Tồn kho theo sản phẩm và kho hàng" columns={columns} getRowKey={row => row.id} rows={pageRows} />}
        <div className="inventory-pagination"><span>Hiển thị {filteredRows.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredRows.length)} trong {formatNumber(filteredRows.length)} bản ghi tồn kho</span><div><Button aria-label="Trang tồn kho trước" className="ui-pagination-button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)} size="small" variant="secondary"><img alt="" src={previousIcon} /></Button><Button aria-label="Trang tồn kho sau" className="ui-pagination-button" disabled={currentPage === totalPages} onClick={() => setPage(currentPage + 1)} size="small" variant="secondary"><img alt="" src={nextIcon} /></Button></div></div>
      </section>
      <section className="inventory-alert-card">
        <div className="inventory-alert-card__header"><div><h2>Cần nhập thêm</h2><p>Các sản phẩm đã chạm hoặc thấp hơn mức tồn tối thiểu.</p></div>{alerts.length > 3 && <Button onClick={() => setShowAllAlerts(value => !value)} size="small" variant="secondary">{showAllAlerts ? 'Thu gọn cảnh báo' : 'Xem tất cả cảnh báo'}</Button>}</div>
        {alerts.length === 0 ? <EmptyState title="Tồn kho đang ổn định" description="Không có sản phẩm cần bổ sung theo mức tồn tối thiểu." /> : <ul className="inventory-alert-list">{alerts.slice(0, showAllAlerts ? alerts.length : 3).map(row => <li key={row.id}><div><strong>{row.productName}</strong><span>{row.warehouseName}</span></div><div><span>{formatNumber(row.quantity)} / tối thiểu {formatNumber(row.reorderLevel)}</span><strong className={`inventory-difference inventory-difference--${row.status}`}>{row.quantity < row.reorderLevel ? `Thiếu ${formatQuantity(row.reorderLevel - row.quantity, row.unit)}` : 'Đã chạm mức tối thiểu'}</strong></div><Badge variant={inventoryStatusVariants[row.status]}>{inventoryStatusLabels[row.status]}</Badge></li>)}</ul>}
      </section>
    </>}
  </section>
}
