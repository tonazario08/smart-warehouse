import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './dashboard.css'
import { buildDashboardOverview, type DashboardStockRow } from '../shared/lib/dashboard'
import { formatNumber, formatQuantity } from '../shared/lib/formatters'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { PageHeader } from '../shared/ui/PageHeader'

type DashboardOverview = ReturnType<typeof buildDashboardOverview>

const stockColumns: DataTableColumn<DashboardStockRow>[] = [
  { id: 'product', header: 'Sản phẩm', render: (row) => <div className="dashboard-product-cell"><strong>{row.productName}</strong><span>{row.sku}</span></div> },
  { id: 'warehouse', header: 'Kho hàng', render: (row) => row.warehouseName },
  { id: 'quantity', header: 'Tồn kho', render: (row) => <strong>{formatQuantity(row.quantity, row.unit)}</strong> },
  { id: 'reorder', header: 'Mức đặt lại', render: (row) => formatQuantity(row.reorderLevel, row.unit) },
  { id: 'status', header: 'Trạng thái', render: (row) => <Badge variant={row.status === 'low' ? 'warning' : 'success'}>{row.status === 'low' ? 'Sắp hết hàng' : 'Ổn định'}</Badge> },
]

export function DashboardPage() {
  const { logout, token } = useAuth()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    void Promise.all([api.dashboardStats(token), api.productsAll(), api.warehouses(token), api.stock(token), api.transactions(token)])
      .then(([stats, products, warehouses, stock, transactions]) => {
        if (active) setOverview(buildDashboardOverview({ stats, products, warehouses, stock, transactions }))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError('Không thể tải dữ liệu bảng điều khiển. Vui lòng thử lại sau.')
      })
    return () => { active = false }
  }, [logout, token])

  if (error) return <FeedbackMessage variant="error">{error}</FeedbackMessage>
  if (!overview) return <FeedbackMessage>Đang tải dữ liệu bảng điều khiển...</FeedbackMessage>

  const { lowStockRows, recentTransactions, stats, stockRows, warehouseRows } = overview
  return <section className="dashboard-page">
    <PageHeader actions={<Button onClick={() => navigate('/products/new')}><span aria-hidden="true">+</span> Tạo sản phẩm</Button>} description="Theo dõi nhanh hoạt động và tình trạng tồn kho của bạn." title="Bảng điều khiển" />

    <section aria-label="Chỉ số tổng quan" className="dashboard-kpis">
      <article className="dashboard-kpi"><span className="dashboard-kpi__label">Tổng sản phẩm</span><strong>{formatNumber(stats.productCount)}</strong><small>Dữ liệu sản phẩm hiện có</small></article>
      <article className="dashboard-kpi"><span className="dashboard-kpi__label">Số lượng tồn</span><strong>{formatNumber(stats.totalStock)}</strong><small>Tổng đơn vị đang lưu kho</small></article>
      <article className="dashboard-kpi"><span className="dashboard-kpi__label">Số kho hàng</span><strong>{formatNumber(stats.warehouseCount)}</strong><small>Kho đang được quản lý</small></article>
      <article className="dashboard-kpi dashboard-kpi--warning"><span className="dashboard-kpi__label">Sắp hết hàng</span><strong>{formatNumber(stats.lowStockCount)}</strong><small>Cần theo dõi và bổ sung</small></article>
    </section>

    <section className="dashboard-grid dashboard-grid--primary">
      <article className="dashboard-panel dashboard-panel--table">
        <div className="dashboard-panel__header"><div><h2>Tổng quan tồn kho</h2><p>Các mặt hàng cần theo dõi trước được hiển thị đầu tiên.</p></div><Button onClick={() => navigate('/inventory')} size="small" variant="ghost">Xem tồn kho</Button></div>
        <DataTable caption="Tồn kho theo sản phẩm và kho hàng" columns={stockColumns} emptyMessage="Chưa có dữ liệu tồn kho." getRowKey={(row) => row.id} rows={stockRows.slice(0, 6)} />
      </article>
      <article className="dashboard-panel dashboard-panel--alerts">
        <div className="dashboard-panel__header"><div><h2>Cần xử lý</h2><p>Các mặt hàng đạt hoặc thấp hơn mức đặt lại.</p></div></div>
        {lowStockRows.length === 0
          ? <EmptyState description="Chưa có mặt hàng nào cần bổ sung theo mức đặt lại." title="Tồn kho đang ổn định" />
          : <ul className="dashboard-alert-list">{lowStockRows.slice(0, 4).map((item) => <li key={item.id}><div><strong>{item.productName}</strong><span>{item.warehouseName}</span></div><Badge variant="warning">Còn {formatQuantity(item.quantity, item.unit)}</Badge></li>)}</ul>}
      </article>
    </section>

    <section className="dashboard-grid dashboard-grid--secondary">
      <article className="dashboard-panel">
        <div className="dashboard-panel__header"><div><h2>Kho hàng</h2><p>Tổng tồn và số mặt hàng theo từng kho.</p></div><Button onClick={() => navigate('/warehouses')} size="small" variant="ghost">Xem kho hàng</Button></div>
        {warehouseRows.length === 0 ? <EmptyState title="Chưa có kho hàng" /> : <ul className="dashboard-warehouse-list">{warehouseRows.map((warehouse) => <li key={warehouse.id}><div><strong>{warehouse.name}</strong><span>{warehouse.code} · {formatNumber(warehouse.productCount)} sản phẩm</span></div><div><strong>{formatNumber(warehouse.totalStock)}</strong><span>{warehouse.lowStockCount > 0 ? `${formatNumber(warehouse.lowStockCount)} cần theo dõi` : 'Tồn kho ổn định'}</span></div></li>)}</ul>}
        <p className="dashboard-unavailable">Sức chứa kho chưa khả dụng vì API hiện chưa cung cấp dữ liệu công suất.</p>
      </article>
      <article className="dashboard-panel">
        <div className="dashboard-panel__header"><div><h2>Giao dịch gần đây</h2><p>Dữ liệu nhập và xuất kho mới nhất.</p></div></div>
        {recentTransactions.length === 0
          ? <EmptyState description="Giao dịch sẽ xuất hiện tại đây khi phát sinh." title="Chưa có giao dịch" />
          : <ul className="dashboard-transaction-list">{recentTransactions.map((transaction) => <li key={transaction.id}><Badge variant={transaction.kind === 'inbound' ? 'success' : 'primary'}>{transaction.kind === 'inbound' ? 'Nhập kho' : 'Xuất kho'}</Badge><div><strong>{transaction.productName}</strong><span>{transaction.warehouseName}</span></div><strong>{formatQuantity(transaction.quantity, transaction.unit)}</strong></li>)}</ul>}
      </article>
    </section>
  </section>
}
