import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import type { Page, Product, Warehouse } from '../../types'
import { formatDateTime, formatQuantity } from '../../shared/lib/formatters'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { EmptyState } from '../../shared/ui/EmptyState'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { listTransfers } from './api'
import type { Transfer, TransferFilters } from './types'
import '../../shared/styles/management.css'
import './transfers.css'

const emptyFilters = { source: '', destination: '', product: '', from: '', to: '' }
export function TransfersPage() {
  const { token, user } = useAuth(), navigate = useNavigate()
  const [data, setData] = useState<Page<Transfer> | null>(null)
  const [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [draft, setDraft] = useState(emptyFilters), [filters, setFilters] = useState<TransferFilters>({})
  const [page, setPage] = useState(1), [retry, setRetry] = useState(0)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [validation, setValidation] = useState('')
  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true); setError(''); setData(null)
    void Promise.all([listTransfers(token, { ...filters, page, page_size: 20 }), api.productsAll(token), api.warehouses(token)])
      .then(([result, productRows, warehouseRows]) => { if (active) { setData(result); setProducts(productRows); setWarehouses(warehouseRows) } })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setError(cause instanceof ApiError ? cause.message : 'Không thể tải phiếu chuyển kho.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, user?.id, user?.role, filters, page, retry])
  function apply(event: FormEvent) {
    event.preventDefault()
    if ([draft.source, draft.destination, draft.product].some(id => id && (!/^[1-9]\d*$/.test(id) || Number(id) > 2147483647))) { setValidation('Chọn mã kho và sản phẩm hợp lệ.'); return }
    if ([draft.from, draft.to].some(value => value && !Number.isFinite(new Date(value).getTime())) || (draft.from && draft.to && new Date(draft.from) > new Date(draft.to))) { setValidation('Thời điểm bắt đầu phải hợp lệ và không sau thời điểm kết thúc.'); return }
    setValidation(''); setPage(1)
    setFilters({ source_warehouse_id: draft.source ? Number(draft.source) : undefined, destination_warehouse_id: draft.destination ? Number(draft.destination) : undefined, product_id: draft.product ? Number(draft.product) : undefined, created_from: draft.from ? new Date(draft.from).toISOString() : undefined, created_to: draft.to ? new Date(draft.to).toISOString() : undefined })
  }
  const warehouseName = (id: number) => warehouses.find(row => row.id === id)?.name ?? 'Kho #' + id
  return <section className="transfers-page management-workspace">
    <PageHeader title="Chuyển kho" description="Chuyển một sản phẩm giữa hai kho, ghi nhận đồng thời tại cả hai kho." actions={<Button onClick={() => navigate('/transfers/new')}>Tạo phiếu chuyển kho</Button>} />
    <form className="transfer-panel transfer-filters" onSubmit={apply}>
      <Select label="Lọc kho nguồn" placeholder="Tất cả kho nguồn" value={draft.source} onChange={event => setDraft({ ...draft, source: event.target.value })} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
      <Select label="Lọc kho đích" placeholder="Tất cả kho đích" value={draft.destination} onChange={event => setDraft({ ...draft, destination: event.target.value })} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
      <Select label="Lọc sản phẩm" placeholder="Tất cả sản phẩm" value={draft.product} onChange={event => setDraft({ ...draft, product: event.target.value })} options={products.map(row => ({ value: row.id, label: row.sku + ' · ' + row.name }))} />
      <Input type="datetime-local" label="Từ thời điểm" value={draft.from} onChange={event => setDraft({ ...draft, from: event.target.value })} />
      <Input type="datetime-local" label="Đến thời điểm" value={draft.to} onChange={event => setDraft({ ...draft, to: event.target.value })} />
      <div className="transfer-actions"><Button type="submit">Áp dụng bộ lọc</Button><Button variant="secondary" onClick={() => { setDraft(emptyFilters); setFilters({}); setPage(1); setValidation('') }}>Đặt lại</Button></div>
      {validation && <FeedbackMessage variant="error">{validation}</FeedbackMessage>}
    </form>
    <section className="transfer-panel">
      {loading ? <FeedbackMessage>Đang tải phiếu chuyển kho...</FeedbackMessage> : error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại danh sách</Button></> : !data?.items.length ? <EmptyState title="Chưa có phiếu chuyển kho phù hợp" description="Thay đổi bộ lọc hoặc tạo phiếu chuyển kho đầu tiên." /> : <>
        <DataTable caption="Danh sách phiếu chuyển kho" rows={data.items} getRowKey={row => row.id} columns={[
          { id: 'id', header: 'Phiếu chuyển', render: row => <Link to={'/transfers/' + row.id}>Phiếu chuyển #{row.id}</Link> },
          { id: 'product', header: 'Sản phẩm', render: row => { const product = products.find(item => item.id === row.product_id); return <div className="transfer-identity"><strong>{product?.name ?? 'Sản phẩm #' + row.product_id}</strong><span>{product?.sku ?? '#' + row.product_id}{product && !product.is_active ? ' · Ngừng hoạt động' : ''}</span></div> } },
          { id: 'source', header: 'Kho nguồn', render: row => warehouseName(row.source_warehouse_id) },
          { id: 'destination', header: 'Kho đích', render: row => warehouseName(row.destination_warehouse_id) },
          { id: 'quantity', header: 'Số lượng', render: row => formatQuantity(row.quantity, products.find(item => item.id === row.product_id)?.unit) },
          { id: 'actor', header: 'Người thực hiện', render: row => 'Tài khoản #' + row.created_by_id },
          { id: 'created', header: 'Thời điểm', render: row => formatDateTime(row.created_at) },
        ]} />
        <Pagination locale="vi" page={page} pageSize={20} total={data.total} onPageChange={setPage} />
      </>}
    </section>
  </section>
}
