import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import type { Page, Product, Warehouse } from '../../types'
import { formatDateTime, formatQuantity } from '../../shared/lib/formatters'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { EmptyState } from '../../shared/ui/EmptyState'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { listPurchaseRequests, purchaseRequestError } from './api'
import type { PurchaseRequest, PurchaseRequestFilters, PurchaseRequestStatus } from './types'
import { statusLabels } from './types'
import '../../shared/styles/management.css'
import './purchase-requests.css'

const blank = { status: '', warehouse: '', product: '', actor: '', from: '', to: '' }
const emptyFilters: PurchaseRequestFilters = {}
export function PurchaseRequestsPage() {
  const { token, user } = useAuth(), location = useLocation()
  const scope = `${token}:${user?.id}:${user?.role}:${location.key}`, scopeRef = useRef(scope)
  scopeRef.current = scope
  const [data, setData] = useState<{ scope: string; page: Page<PurchaseRequest> } | null>(null)
  const [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [draft, setDraft] = useState(blank)
  const [query, setQuery] = useState<{ scope: string; filters: PurchaseRequestFilters; page: number }>({ scope, filters: emptyFilters, page: 1 })
  const filters = query.scope === scope ? query.filters : emptyFilters, page = query.scope === scope ? query.page : 1
  const [retry, setRetry] = useState(0)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [validation, setValidation] = useState('')
  useEffect(() => { setDraft(blank); setValidation('') }, [scope])
  useEffect(() => {
    if (!token) return
    let active = true
    let recoveringPage = false
    const current = () => active && scopeRef.current === scope
    setLoading(true); setError(''); setData(null)
    void Promise.all([listPurchaseRequests(token, { ...filters, page, page_size: 20 }), api.productsAll(token), api.warehouses(token)])
      .then(([result, productRows, warehouseRows]) => {
        if (!current()) return
        const lastPage = Math.max(1, Math.ceil(result.total / 20))
        if (page > lastPage) {
          recoveringPage = true
          setQuery(previous => scopeRef.current === scope && previous.scope === scope && previous.filters === filters && previous.page === page ? { ...previous, page: lastPage } : previous)
          return
        }
        setData({ scope, page: result }); setProducts(productRows); setWarehouses(warehouseRows)
      })
      .catch((cause: unknown) => { if (current() && !(cause instanceof ApiError && cause.staleSession)) setError(purchaseRequestError(cause, 'Không thể tải yêu cầu mua hàng.')) })
      .finally(() => { if (current() && !recoveringPage) setLoading(false) })
    return () => { active = false }
  }, [token, scope, filters, page, retry])
  function apply(event: FormEvent) {
    event.preventDefault()
    if ([draft.warehouse, draft.product, draft.actor].some(value => value && (!/^[1-9]\d*$/.test(value) || value.length > 10 || Number(value) > 2147483647))) { setValidation('Chọn mã kho, sản phẩm và tài khoản nguyên dương hợp lệ.'); return }
    if ([draft.from, draft.to].some(value => value && !Number.isFinite(new Date(value).getTime())) || (draft.from && draft.to && new Date(draft.from) > new Date(draft.to))) { setValidation('Thời điểm bắt đầu phải hợp lệ và không sau thời điểm kết thúc.'); return }
    setValidation('')
    setQuery({ scope, page: 1, filters: { status: draft.status ? draft.status as PurchaseRequestStatus : undefined, warehouse_id: draft.warehouse ? Number(draft.warehouse) : undefined, product_id: draft.product ? Number(draft.product) : undefined, ...(user?.role !== 'client' && draft.actor ? { requested_by_id: Number(draft.actor) } : {}), created_from: draft.from ? new Date(draft.from).toISOString() : undefined, created_to: draft.to ? new Date(draft.to).toISOString() : undefined } })
  }
  const current = data?.scope === scope ? data.page : null
  return <section className="purchase-requests-page management-workspace">
    <PageHeader title="Yêu cầu mua hàng" description={user?.role === 'client' ? 'Theo dõi yêu cầu của bạn từ khi gửi đến khi xuất hàng.' : 'Xem xét yêu cầu của khách hàng và thực hiện xuất hàng đã duyệt.'} actions={user?.role === 'client' && <Link className="ui-button ui-button--primary ui-button--medium" to="/purchase-requests/new">Tạo yêu cầu mua hàng</Link>} />
    <form className="purchase-panel purchase-filters" onSubmit={apply} noValidate>
      <Select label="Lọc trạng thái" placeholder="Tất cả trạng thái" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value })} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
      <Select label="Lọc kho hàng" placeholder="Tất cả kho hàng" value={draft.warehouse} onChange={event => setDraft({ ...draft, warehouse: event.target.value })} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
      <Select label="Lọc sản phẩm" placeholder="Tất cả sản phẩm" value={draft.product} onChange={event => setDraft({ ...draft, product: event.target.value })} options={products.map(row => ({ value: row.id, label: row.sku + ' · ' + row.name }))} />
      {user?.role !== 'client' && <Input label="Lọc mã tài khoản" inputMode="numeric" value={draft.actor} onChange={event => setDraft({ ...draft, actor: event.target.value })} hint="Mã số tài khoản yêu cầu" />}
      <Input label="Từ thời điểm" type="datetime-local" value={draft.from} onChange={event => setDraft({ ...draft, from: event.target.value })} />
      <Input label="Đến thời điểm" type="datetime-local" value={draft.to} onChange={event => setDraft({ ...draft, to: event.target.value })} />
      <div className="purchase-actions"><Button type="submit">Áp dụng bộ lọc</Button><Button variant="secondary" onClick={() => { setDraft(blank); setQuery({ scope, filters: emptyFilters, page: 1 }); setValidation('') }}>Đặt lại</Button></div>
      {validation && <FeedbackMessage variant="error">{validation}</FeedbackMessage>}
    </form>
    <section className="purchase-panel">
      {loading ? <FeedbackMessage>Đang tải yêu cầu mua hàng...</FeedbackMessage> : error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại danh sách</Button></> : !current?.items.length ? <EmptyState title="Chưa có yêu cầu mua hàng phù hợp" description="Thay đổi bộ lọc hoặc gửi yêu cầu đầu tiên của bạn." /> : <>
        <DataTable caption="Danh sách yêu cầu mua hàng" rows={current.items} getRowKey={row => row.id} columns={[
          { id: 'number', header: 'Yêu cầu', render: row => <Link className="purchase-nowrap" to={'/purchase-requests/' + row.id}>{row.request_number}</Link> },
          { id: 'product', header: 'Sản phẩm', render: row => { const product = products.find(item => item.id === row.product_id); return <div className="purchase-identity"><strong>{product?.name ?? 'Sản phẩm #' + row.product_id}</strong><span>{product?.sku ?? '#' + row.product_id}</span></div> } },
          { id: 'warehouse', header: 'Kho hàng', render: row => <span className="purchase-warehouse">{warehouses.find(item => item.id === row.warehouse_id)?.name ?? 'Kho #' + row.warehouse_id}</span> },
          { id: 'quantity', header: 'Số lượng', render: row => <span className="purchase-nowrap">{formatQuantity(row.quantity, products.find(item => item.id === row.product_id)?.unit)}</span> },
          { id: 'status', header: 'Trạng thái', render: row => <Badge className="purchase-nowrap" variant={row.status === 'fulfilled' ? 'success' : row.status === 'rejected' ? 'danger' : row.status === 'approved' ? 'primary' : 'warning'}>{statusLabels[row.status]}</Badge> },
          { id: 'actor', header: 'Người yêu cầu', render: row => <span className="purchase-nowrap">Tài khoản #{row.requested_by_id}</span> },
          { id: 'created', header: 'Thời điểm tạo', render: row => <span className="purchase-nowrap">{formatDateTime(row.created_at)}</span> },
        ]} />
        <Pagination locale="vi" page={page} pageSize={20} total={current.total} onPageChange={value => setQuery({ scope, filters, page: value })} />
      </>}
    </section>
  </section>
}
