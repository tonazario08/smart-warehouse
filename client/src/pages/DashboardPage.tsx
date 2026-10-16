import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './dashboard.css'
import kpiBlue from '../shared/assets/figma/kpi-blue.svg'
import kpiGreen from '../shared/assets/figma/kpi-green.svg'
import kpiWarning from '../shared/assets/figma/kpi-warning.svg'
import { buildDashboardOverview, type DashboardStockRow, type DashboardTransactionRow } from '../shared/lib/dashboard'
import { inventoryStatusLabels, inventoryStatusVariants } from '../shared/lib/inventory'
import { formatDateTime, formatNumber, formatQuantity } from '../shared/lib/formatters'
import { can } from '../shared/lib/permissions'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'

type DashboardOverview = ReturnType<typeof buildDashboardOverview>

const stockColumns: DataTableColumn<DashboardStockRow>[] = [
  { id: 'product', header: 'Sản phẩm', render: row => <strong>{row.productName}</strong> },
  { id: 'sku', header: 'SKU', render: row => row.sku },
  { id: 'warehouse', header: 'Kho', render: row => row.warehouseName },
  { id: 'quantity', header: 'Tồn kho', render: row => <strong>{formatQuantity(row.quantity, row.unit)}</strong> },
  { id: 'reorder', header: 'Mức tối thiểu', render: row => formatQuantity(row.reorderLevel, row.unit) },
  { id: 'status', header: 'Trạng thái', render: row => <Badge variant={inventoryStatusVariants[row.status]}>{inventoryStatusLabels[row.status]}</Badge> },
]

const transactionColumns: DataTableColumn<DashboardTransactionRow>[] = [
  { id: 'kind', header: 'Loại giao dịch', render: row => <strong>{row.kind === 'inbound' ? 'Nhập kho' : 'Xuất kho'}</strong> },
  { id: 'product', header: 'Sản phẩm', render: row => row.productName },
  { id: 'warehouse', header: 'Kho', render: row => row.warehouseName },
  { id: 'quantity', header: 'Thay đổi', render: row => <strong className={`dashboard-transaction-change dashboard-transaction-change--${row.kind}`}>{row.kind === 'inbound' ? '+' : '−'}{formatQuantity(row.quantity, row.unit)}</strong> },
  { id: 'time', header: 'Thời gian', render: row => formatDateTime(row.createdAt) },
  { id: 'actor', header: 'Người thực hiện', render: row => row.createdById === undefined ? '—' : `Tài khoản #${row.createdById}` },
]

export function DashboardPage() {
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!token) return
    let active = true
    setOverview(null)
    setError('')
    void Promise.all([api.dashboardStats(token), api.productsAll(token), api.warehouses(token), api.stock(token), api.transactions(token)])
      .then(([stats, products, warehouses, stock, transactions]) => {
        if (active) setOverview(buildDashboardOverview({ stats, products, warehouses, stock, transactions }))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setError('Không thể tải dữ liệu bảng điều khiển. Vui lòng thử lại.')
      })
    return () => { active = false }
  }, [logout, reload, token])

  if (error) return <FeedbackMessage variant="error">{error} <Button onClick={() => setReload(value => value + 1)} size="small" variant="secondary">Thử lại</Button></FeedbackMessage>
  if (!overview) return <FeedbackMessage>Đang tải dữ liệu bảng điều khiển...</FeedbackMessage>

  const { lowStockRows, recentTransactions, recentInbound, recentOutbound, stats, stockRows, warehouseRows } = overview
  return <section className="dashboard-page">
    <PageHeader actions={can(user?.role, 'product:write') ? <Button onClick={() => navigate('/products/new')}><span aria-hidden="true">+</span> Tạo sản phẩm</Button> : undefined} description="Theo dõi tình trạng tồn kho và hoạt động kho hàng." title="Bảng điều khiển" />
    <section aria-label="Chỉ số tổng quan" className="dashboard-kpis">
      <article className="dashboard-kpi"><span className="dashboard-kpi__label">Tổng sản phẩm<img alt="" src={kpiBlue} /></span><strong>{formatNumber(stats.productCount)}</strong><small>Dữ liệu sản phẩm hiện có</small></article>
      <article className="dashboard-kpi dashboard-kpi--success"><span className="dashboard-kpi__label">Số lượng tồn kho<img alt="" src={kpiGreen} /></span><strong>{formatNumber(stats.totalStock)}</strong><small>Tổng đơn vị đang lưu kho</small></article>
      <article className="dashboard-kpi dashboard-kpi--success"><span className="dashboard-kpi__label">Số kho hàng<img alt="" src={kpiGreen} /></span><strong>{formatNumber(stats.warehouseCount)}</strong><small>Kho hiện có trong hệ thống</small></article>
      <article className="dashboard-kpi dashboard-kpi--warning"><span className="dashboard-kpi__label">Sản phẩm cần bổ sung<img alt="" src={kpiWarning} /></span><strong>{formatNumber(stats.lowStockCount)}</strong><small>Chạm ngưỡng hoặc hết hàng</small></article>
    </section>
    <section className="dashboard-grid dashboard-grid--primary">
      <article className="dashboard-panel dashboard-panel--stock">
        <div className="dashboard-panel__header"><h2>Tổng quan tồn kho</h2><Button onClick={() => navigate('/inventory')} size="small" variant="ghost">Xem tất cả</Button></div>
        <DataTable caption="Tồn kho theo sản phẩm và kho hàng" columns={stockColumns} emptyMessage="Chưa có dữ liệu tồn kho." getRowKey={row => row.id} rows={stockRows.slice(0, 6)} />
      </article>
      <article className="dashboard-panel dashboard-panel--alerts">
        <div className="dashboard-panel__header"><div><h2>Cảnh báo tồn kho</h2><p>Các sản phẩm cần được xử lý ngay.</p></div></div>
        {lowStockRows.length === 0
          ? <EmptyState description="Chưa có mặt hàng nào cần bổ sung theo mức tồn tối thiểu." title="Tồn kho đang ổn định" />
          : <ul className="dashboard-alert-list">{lowStockRows.slice(0, 4).map(item => <li key={item.id}><div><strong>{item.productName}</strong><span>{item.warehouseName} · Còn {formatQuantity(item.quantity, item.unit)}</span></div><Badge variant={inventoryStatusVariants[item.status]}>{inventoryStatusLabels[item.status]}</Badge></li>)}</ul>}
        <Button onClick={() => navigate('/inventory')} size="small">Xem tồn kho</Button>
      </article>
    </section>
    <section className="dashboard-grid dashboard-grid--secondary">
      <article className="dashboard-panel">
        <div className="dashboard-panel__header"><h2>Tình trạng kho hàng</h2><Button onClick={() => navigate('/warehouses')} size="small" variant="ghost">Xem tất cả</Button></div>
        {warehouseRows.length === 0 ? <EmptyState title="Chưa có kho hàng" /> : <ul className="dashboard-warehouse-list">{warehouseRows.slice(0, 4).map(warehouse => <li key={warehouse.id}><div><strong>{warehouse.name}</strong><span>{warehouse.address ?? warehouse.code}</span></div><strong>{formatNumber(warehouse.totalStock)}</strong><div><span>{formatNumber(warehouse.productCount)} sản phẩm</span><span>{warehouse.lowStockCount > 0 ? `${formatNumber(warehouse.lowStockCount)} cần bổ sung` : 'Tồn kho ổn định'}</span></div></li>)}</ul>}
        <p className="dashboard-unavailable">Chưa có thông tin sức chứa và trạng thái vận hành kho.</p>
      </article>
      <article className="dashboard-panel">
        <div className="dashboard-transaction-list">{(['inbound', 'outbound'] as const).map(kind => {
          const operations = kind === 'inbound' ? recentInbound : recentOutbound
          return <section className="dashboard-operations" key={kind}><div className="dashboard-panel__header"><h2>{kind === 'inbound' ? 'Nhập kho gần đây' : 'Xuất kho gần đây'}</h2><Button onClick={() => navigate(kind === 'inbound' ? '/inbound' : '/outbound')} size="small" variant="ghost">Xem tất cả</Button></div>{operations.length === 0 ? <p className="dashboard-operations__empty">Chưa có giao dịch {kind === 'inbound' ? 'nhập' : 'xuất'} kho.</p> : <ul className="dashboard-operation-list">{operations.map(row => <li key={row.id}><div><strong>{row.productName}</strong><span>{row.warehouseName}</span></div><strong className={`dashboard-transaction-change dashboard-transaction-change--${kind}`}>{kind === 'inbound' ? '+' : '−'}{formatQuantity(row.quantity, row.unit)}</strong></li>)}</ul>}</section>
        })}</div>
      </article>
    </section>
    <article className="dashboard-panel dashboard-panel--transactions"><div className="dashboard-panel__header"><h2>Giao dịch kho gần đây</h2></div><DataTable caption="Giao dịch nhập và xuất kho theo mã giao dịch mới nhất" columns={transactionColumns} emptyMessage="Chưa có giao dịch kho." getRowKey={row => row.id} rows={recentTransactions} /><p className="dashboard-unavailable">Người thực hiện được hiển thị theo mã tài khoản; chưa có tên tài khoản trong dữ liệu giao dịch.</p></article>
  </section>
}
