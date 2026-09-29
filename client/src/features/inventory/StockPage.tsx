import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { createInventoryApi, stockKeys } from './api'
import { InventoryFiltersForm } from './InventoryFilters'
import { ProductIdentity, useInventoryLabels, WarehouseIdentity } from './InventoryLabels'
import type { InventoryFilters } from './types'

const pageSize = 20
const freshFilters = (): InventoryFilters => ({ page: 1, pageSize, warehouseId: '', productId: '', createdFrom: '', createdTo: '' })
const localTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function StockPage() {
  const { client } = useAuth()
  const api = createInventoryApi(client)
  const [page, setPage] = useState(1)
  const [draft, setDraft] = useState<InventoryFilters>(freshFilters)
  const [filters, setFilters] = useState<InventoryFilters>(freshFilters)
  const [rangeError, setRangeError] = useState<string | null>(null)
  const listFilters = { ...filters, page, pageSize }
  const query = useQuery({ queryKey: stockKeys.list(listFilters), queryFn: () => api.listStock(listFilters) })
  const labels = useInventoryLabels(client, query.data?.items.map((row) => row.product_id) ?? [], query.data?.items.map((row) => row.warehouse_id) ?? [])

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

  return <section className="admin-workspace inventory-workspace" aria-labelledby="stock-heading">
    <header className="admin-heading"><div><h2 id="stock-heading">Stock</h2><p>Current quantity by product and warehouse</p></div></header>
    <InventoryFiltersForm client={client} filters={draft} onChange={(next) => { setDraft(next as InventoryFilters); setRangeError(null) }} onApply={apply} />
    {rangeError && <p className="form-error" role="alert">{rangeError}</p>}
    {labels.loading && <p className="async-state" role="status">Resolving product and warehouse labels…</p>}
    {labels.error && <p className="async-state async-state-error" role="alert">
      {labels.error instanceof Error ? labels.error.message : 'Inventory labels could not be resolved.'}
      {' '}<button type="button" className="quiet" onClick={() => void labels.retry()}>Retry label lookup</button>
    </p>}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading stock…" emptyMessage="No stock records match these filters." error={<>{query.error instanceof Error ? query.error.message : 'Stock could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry stock</button></>}>
      <div className="table-wrap">
        <table className="admin-table resource-table inventory-table">
          <caption>Stock quantity ledger</caption>
          <thead><tr><th scope="col">Product</th><th scope="col">Warehouse</th><th scope="col">Quantity</th><th scope="col">Recorded</th></tr></thead>
          <tbody>{query.data?.items.map((row) => <tr key={row.id}>
            <td data-label="Product"><ProductIdentity id={row.product_id} lookup={labels} /></td>
            <td data-label="Warehouse"><WarehouseIdentity id={row.warehouse_id} lookup={labels} /></td>
            <td data-label="Quantity"><strong className="inventory-quantity">{row.quantity}</strong></td>
            <td data-label="Recorded"><time dateTime={row.created_at}>{localTime.format(new Date(row.created_at))}</time></td>
          </tr>)}</tbody>
        </table>
      </div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
