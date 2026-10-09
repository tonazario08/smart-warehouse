import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './inventory.css'
import { buildInventoryRows, filterInventoryRows, type InventoryRow } from '../shared/lib/inventory'
import { formatNumber, formatQuantity } from '../shared/lib/formatters'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import { Select } from '../shared/ui/Select'
import type { Warehouse } from '../types'

const errorMessage = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Không thể tải dữ liệu tồn kho. Vui lòng thử lại sau.'

export function InventoryPage() {
  const { logout, token } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [search, setSearch] = useState('')
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    void Promise.all([api.stock(token), api.products(), api.warehouses(token)])
      .then(([stocks, productPage, warehouseList]) => {
        if (!active) return
        setRows(buildInventoryRows({ stocks, products: productPage.items, warehouses: warehouseList }))
        setWarehouses(warehouseList)
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, token])

  const filteredRows = useMemo(() => filterInventoryRows(rows, { search, warehouseId }), [rows, search, warehouseId])
  const totalQuantity = rows.reduce((sum, row) => sum + row.quantity, 0)
  const lowStockCount = rows.filter((row) => row.status === 'low').length
  const columns: DataTableColumn<InventoryRow>[] = [
    { id: 'product', header: 'Sản phẩm', render: (row) => <div className="inventory-product-cell"><strong>{row.productName}</strong><span>{row.sku}</span></div> },
    { id: 'warehouse', header: 'Kho hàng', render: (row) => row.warehouseName },
    { id: 'quantity', header: 'Tồn kho', render: (row) => <strong>{formatQuantity(row.quantity, row.unit)}</strong> },
    { id: 'reorder', header: 'Tối thiểu', render: (row) => formatQuantity(row.reorderLevel, row.unit) },
    { id: 'status', header: 'Trạng thái', render: (row) => <Badge variant={row.status === 'low' ? 'warning' : 'success'}>{row.status === 'low' ? 'Sắp hết hàng' : 'Ổn định'}</Badge> },
    { id: 'action', header: <span className="visually-hidden">Thao tác</span>, render: (row) => <Button aria-label={`Xem chi tiết tồn kho ${row.productName} tại ${row.warehouseName}`} onClick={() => navigate(`/inventory/${row.warehouseId}/${row.productId}`)} size="small" variant="ghost">Chi tiết</Button> },
  ]

  return <section className="inventory-page">
    <PageHeader description="Theo dõi số lượng tồn theo từng sản phẩm và kho hàng." title="Tồn kho" />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải dữ liệu tồn kho...</FeedbackMessage> : <>
      <section aria-label="Chỉ số tồn kho" className="inventory-kpis">
        <article className="inventory-kpi"><span>Tổng số lượng tồn</span><strong>{formatNumber(totalQuantity)}</strong><small>Tổng đơn vị đang lưu kho</small></article>
        <article className="inventory-kpi inventory-kpi--warning"><span>Sắp hết hàng</span><strong>{formatNumber(lowStockCount)}</strong><small>Đạt hoặc dưới mức tồn tối thiểu</small></article>
        <article className="inventory-kpi"><span>Kho hàng</span><strong>{formatNumber(warehouses.length)}</strong><small>Kho hiện có trong hệ thống</small></article>
      </section>
      <section className="inventory-list-card">
        <div className="inventory-list-card__header"><div><h2>Danh sách tồn kho</h2><p>Dữ liệu tồn kho hiện tại theo từng kho hàng.</p></div></div>
        <div className="inventory-toolbar"><Input aria-label="Tìm kiếm tồn kho" onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo SKU, sản phẩm, kho hàng..." value={search} /><Select aria-label="Lọc theo kho hàng" onChange={(event) => setWarehouseId(event.target.value === '' ? null : Number(event.target.value))} options={warehouses.map((warehouse) => ({ label: warehouse.name, value: warehouse.id }))} placeholder="Tất cả kho hàng" value={warehouseId ?? ''} /></div>
        {filteredRows.length === 0 ? <EmptyState description={rows.length === 0 ? 'Chưa có bản ghi tồn kho để hiển thị.' : 'Không tìm thấy tồn kho phù hợp với điều kiện lọc.'} title={rows.length === 0 ? 'Chưa có dữ liệu tồn kho' : 'Không có kết quả'} /> : <DataTable caption="Tồn kho theo sản phẩm và kho hàng" columns={columns} getRowKey={(row) => row.id} rows={filteredRows} />}
      </section>
    </>}
  </section>
}
