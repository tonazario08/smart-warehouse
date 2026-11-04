import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useManagementSession } from '../../app/ManagementProvider'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { formatDateTime, formatNumber } from '../../shared/lib/formatters'
import { InventoryFiltersForm } from '../inventory/InventoryFilters'
import { InventoryLabelStatus, ProductIdentity, useInventoryLabels, WarehouseIdentity } from '../inventory/InventoryLabels'
import type { TransactionFilters } from '../inventory/types'
import { createTransactionsApi, transactionKeys } from './api'

const pageSize = 20
const freshFilters = (): TransactionFilters => ({ page: 1, pageSize, warehouseId: '', productId: '', createdFrom: '', createdTo: '', type: '' })
export function TransactionsPage() {
  const { client } = useManagementSession(), api = createTransactionsApi(client)
  const [page, setPage] = useState(1), [draft, setDraft] = useState<TransactionFilters>(freshFilters), [filters, setFilters] = useState<TransactionFilters>(freshFilters)
  const [error, setError] = useState('')
  const listFilters = { ...filters, page, pageSize }
  const query = useQuery({ queryKey: transactionKeys.list(listFilters), queryFn: () => api.list(listFilters) })
  const labels = useInventoryLabels(client, query.data?.items.map(row => row.product_id) ?? [], query.data?.items.map(row => row.warehouse_id) ?? [])
  function apply(event: FormEvent) {
    event.preventDefault()
    if ([draft.productId, draft.warehouseId].some(id => id !== '' && (!/^[1-9]\d*$/.test(id) || Number(id) > 2147483647))) { setError('Chọn mã sản phẩm và kho hàng hợp lệ.'); return }
    if ([draft.createdFrom, draft.createdTo].some(value => value && !Number.isFinite(new Date(value).getTime()))) { setError('Chọn thời điểm hợp lệ.'); return }
    if (draft.createdFrom && draft.createdTo && new Date(draft.createdFrom).getTime() > new Date(draft.createdTo).getTime()) { setError('Thời điểm bắt đầu phải trước thời điểm kết thúc.'); return }
    if (!['', 'inbound', 'outbound'].includes(draft.type)) { setError('Chọn loại giao dịch được hỗ trợ.'); return }
    setError(''); setPage(1); setFilters({ ...draft, page: 1, pageSize })
  }
  return <section className="management-workspace">
    <PageHeader title="Giao dịch" description="Lịch sử nhập và xuất kho chỉ đọc, không thể sửa hoặc xóa." />
    <div className="management-panel"><InventoryFiltersForm locale="vi" client={client} filters={draft} onChange={next => { setDraft(next as TransactionFilters); setError('') }} onTypeChange={type => setDraft(current => ({ ...current, type }))} showType onApply={apply} /></div>
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    <InventoryLabelStatus locale="vi" lookup={labels} subject="transaction history" />
    <div className="management-panel">
      {query.isPending ? <FeedbackMessage>Đang tải giao dịch…</FeedbackMessage> : query.isError ? <FeedbackMessage variant="error">{query.error instanceof ApiError ? query.error.message : 'Không thể tải giao dịch.'} <Button variant="secondary" onClick={() => void query.refetch()}>Thử lại giao dịch</Button></FeedbackMessage> : !query.data?.items.length ? <EmptyState title="Không có giao dịch phù hợp." /> :
        <DataTable caption="Lịch sử giao dịch" rows={query.data.items} getRowKey={row => row.id} columns={[
          { id: 'type', header: 'Loại giao dịch', render: row => <span className={'movement-direction movement-direction-' + row.transaction_type}>{row.transaction_type === 'inbound' ? 'Nhập kho' : row.transaction_type === 'outbound' ? 'Xuất kho' : 'Không xác định'}</span> },
          { id: 'product', header: 'Sản phẩm', render: row => <ProductIdentity locale="vi" id={row.product_id} lookup={labels} /> },
          { id: 'warehouse', header: 'Kho hàng', render: row => <WarehouseIdentity locale="vi" id={row.warehouse_id} lookup={labels} /> },
          { id: 'quantity', header: 'Số lượng', render: row => <strong>{formatNumber(row.quantity)}</strong> },
          { id: 'actor', header: 'Người thực hiện', render: row => 'Tài khoản #' + row.created_by_id },
          { id: 'linked', header: 'Phiếu liên quan', render: row => row.inbound_id != null ? 'Phiếu nhập #' + row.inbound_id : row.outbound_id != null ? 'Phiếu xuất #' + row.outbound_id : 'Không có phiếu liên kết' },
          { id: 'time', header: 'Thời điểm', render: row => <time dateTime={row.created_at}>{formatDateTime(row.created_at)}</time> },
        ]} />}
      {query.data && <Pagination locale="vi" page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
    </div>
  </section>
}
