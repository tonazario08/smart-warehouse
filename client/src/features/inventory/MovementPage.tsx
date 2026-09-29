import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { createInventoryApi, inboundKeys, outboundKeys } from './api'
import { InventoryFiltersForm } from './InventoryFilters'
import { InventoryLabelStatus, ProductIdentity, useInventoryLabels, WarehouseIdentity } from './InventoryLabels'
import { MovementForm, type MovementDirection } from './MovementForm'
import type { InventoryFilters } from './types'

const pageSize = 20
const freshFilters = (): InventoryFilters => ({ page: 1, pageSize, warehouseId: '', productId: '', createdFrom: '', createdTo: '' })
const localTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function MovementPage({ direction }: { direction: MovementDirection }) {
  const { client } = useAuth()
  const api = createInventoryApi(client)
  const [page, setPage] = useState(1)
  const [draft, setDraft] = useState<InventoryFilters>(freshFilters)
  const [filters, setFilters] = useState<InventoryFilters>(freshFilters)
  const [rangeError, setRangeError] = useState<string | null>(null)
  const listFilters = { ...filters, page, pageSize }
  const query = useQuery({
    queryKey: direction === 'inbound' ? inboundKeys.list(listFilters) : outboundKeys.list(listFilters),
    queryFn: () => direction === 'inbound' ? api.listInbounds(listFilters) : api.listOutbounds(listFilters),
  })
  const labels = useInventoryLabels(client, query.data?.items.map((row) => row.product_id) ?? [], query.data?.items.map((row) => row.warehouse_id) ?? [])
  const name = direction === 'inbound' ? 'Inbound' : 'Outbound'

  function apply(event: FormEvent) {
    event.preventDefault()
    if (draft.createdFrom && draft.createdTo && new Date(draft.createdFrom).getTime() > new Date(draft.createdTo).getTime()) {
      setRangeError('Start date must be before the end date.')
      return
    }
    setRangeError(null)
    setPage(1)
    setFilters({ ...draft, page: 1, pageSize })
  }

  return <section className="admin-workspace inventory-workspace" aria-labelledby={`${direction}-heading`}>
    <header className="admin-heading"><div><h2 id={`${direction}-heading`}>{name}</h2><p>{direction === 'inbound' ? 'Receiving activity and new stock' : 'Dispatch activity and stock leaving the warehouse'}</p></div></header>
    <MovementForm direction={direction} />
    <InventoryFiltersForm client={client} filters={draft} onChange={(next) => { setDraft(next as InventoryFilters); setRangeError(null) }} onApply={apply} showLookupStatus={false} />
    {rangeError && <p className="form-error" role="alert">{rangeError}</p>}
    <InventoryLabelStatus lookup={labels} subject="movement history" />
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage={`Loading ${direction} history…`} emptyMessage={`No ${direction} records match these filters.`} error={<>{query.error instanceof Error ? query.error.message : `${name} history could not be loaded.`} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry {direction} history</button></>}>
      <div className="table-wrap">
        <table className={`admin-table resource-table inventory-table movement-history movement-history-${direction}`}>
          <caption>{name} movement ledger</caption>
          <thead><tr><th scope="col">Product</th><th scope="col">Warehouse</th><th scope="col">Quantity</th><th scope="col">Actor</th><th scope="col">Reference / note</th><th scope="col">Recorded</th></tr></thead>
          <tbody>{query.data?.items.map((row) => <tr key={row.id}>
            <td data-label="Product"><ProductIdentity id={row.product_id} lookup={labels} /></td>
            <td data-label="Warehouse"><WarehouseIdentity id={row.warehouse_id} lookup={labels} /></td>
            <td data-label="Quantity"><strong className="inventory-quantity">{row.quantity}</strong></td>
            <td data-label="Actor">Actor {row.created_by_id}</td>
            <td data-label="Reference / note"><span>{row.reference || 'No reference'}</span><small>{row.note || 'No note'}</small></td>
            <td data-label="Recorded"><time dateTime={row.created_at}>{localTime.format(new Date(row.created_at))}</time></td>
          </tr>)}</tbody>
        </table>
      </div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
