import { useState, type FormEvent } from 'react'
import { Fragment } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/ApiError'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { createWarehousesApi, warehouseKeys } from './api'
import { warehouseSchema, type WarehouseForm } from './schemas'
import type { Warehouse, WarehouseInput } from './types'

const pageSize = 20
const localTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
type Selection = Warehouse | 'new' | null

function WarehouseEditor({ warehouse, pending, save, close }: { warehouse: Warehouse | null; pending: boolean; save: (id: number | null, input: WarehouseInput) => Promise<void>; close: () => void }) {
  const form = useForm<WarehouseForm, unknown, WarehouseInput>({ resolver: zodResolver(warehouseSchema), defaultValues: {
    code: warehouse?.code ?? '', name: warehouse?.name ?? '', address: warehouse?.address ?? '',
    latitude: warehouse?.latitude == null ? '' : String(warehouse.latitude), longitude: warehouse?.longitude == null ? '' : String(warehouse.longitude),
  } })
  async function submit(values: WarehouseInput) {
    form.clearErrors()
    try { await save(warehouse?.id ?? null, values) } catch (error) {
      const fields = error instanceof ApiError ? error.fields : null
      for (const field of ['code', 'name', 'address', 'latitude', 'longitude'] as const) {
        const value = fields?.[field]
        if (value) form.setError(field, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
      }
      form.setError('root', { type: 'server', message: error instanceof Error ? error.message : 'Warehouse could not be saved.' })
    }
  }
  const latitudeError = form.formState.errors.latitude?.message
  const longitudeError = form.formState.errors.longitude?.message
  return <form className="admin-inline-form resource-editor" aria-label={warehouse ? 'Edit warehouse' : 'Create warehouse'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h3>{warehouse ? `Edit ${warehouse.code}` : 'Create warehouse'}</h3>
    <div className="admin-form-fields">
      <label>Code<input {...form.register('code')} aria-invalid={Boolean(form.formState.errors.code)} onChange={(event) => form.setValue('code', event.target.value.toUpperCase(), { shouldValidate: true })} />{form.formState.errors.code?.message && <small className="form-error">{form.formState.errors.code.message}</small>}</label>
      <label>Name<input {...form.register('name')} />{form.formState.errors.name?.message && <small className="form-error">{form.formState.errors.name.message}</small>}</label>
      <label>Address<input {...form.register('address')} />{form.formState.errors.address?.message && <small className="form-error">{form.formState.errors.address.message}</small>}</label>
      <label>Latitude<input inputMode="decimal" {...form.register('latitude')} aria-invalid={Boolean(latitudeError)} aria-describedby={latitudeError ? 'warehouse-coordinate-error' : undefined} />{latitudeError && <small id="warehouse-coordinate-error" className="form-error">{latitudeError}</small>}</label>
      <label>Longitude<input inputMode="decimal" {...form.register('longitude')} aria-invalid={Boolean(longitudeError)} aria-describedby={longitudeError ? 'warehouse-coordinate-error-longitude' : undefined} />{longitudeError && <small id="warehouse-coordinate-error-longitude" className="form-error">{longitudeError}</small>}</label>
    </div>
    {form.formState.errors.root?.message && <p role="alert" className="form-error">{form.formState.errors.root.message}</p>}
    <div className="resource-actions"><button type="submit" disabled={pending || form.formState.isSubmitting}>{pending ? 'Saving…' : 'Save warehouse'}</button><button type="button" className="quiet" onClick={close}>Cancel</button></div>
  </form>
}

export function WarehousesPage() {
  const { client, user } = useAuth()
  const admin = user?.role === 'admin'
  const api = createWarehousesApi(client)
  const cache = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ search: '' })
  const [selection, setSelection] = useState<Selection>(null)
  const [deleting, setDeleting] = useState<Warehouse | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const listFilters = { page, pageSize, ...filters }
  const query = useQuery({ queryKey: warehouseKeys.list(listFilters), queryFn: () => api.list(listFilters) })
  const invalidate = async () => cache.invalidateQueries({ queryKey: warehouseKeys.all })
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: WarehouseInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await invalidate(); setSelection(null); setFailure(null); setMessage(variables.id ? 'Warehouse updated.' : 'Warehouse created.') } })
  const remove = useMutation({ mutationFn: api.delete, onSuccess: async () => { await invalidate(); setDeleting(null); setFailure(null); setMessage('Warehouse deleted.') }, onError: (error) => setFailure(error instanceof Error ? error.message : 'Warehouse could not be deleted.') })
  const submit = async (id: number | null, input: WarehouseInput) => { setFailure(null); setMessage(null); await save.mutateAsync({ id, input }) }
  function apply(event: FormEvent) { event.preventDefault(); setPage(1); setFilters({ search: search.trim() }) }

  return <section className="admin-workspace" aria-labelledby="warehouses-heading">
    <header className="admin-heading"><div><h2 id="warehouses-heading">Warehouses</h2><p>Sites, addresses, and direct coordinates</p></div><div className="resource-actions"><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh warehouses</button>{admin && <button type="button" onClick={() => { setSelection('new'); setDeleting(null); setMessage(null) }}>Create warehouse</button>}</div></header>
    <form className="resource-filters" aria-label="Filter warehouses" onSubmit={apply}><label>Search warehouses<input value={search} onChange={(event) => setSearch(event.target.value)} /></label><button type="submit">Apply filters</button></form>
    {message && <p role="status" className="form-success">{message}</p>}{failure && <p role="alert" className="form-error">{failure}</p>}
    {admin && selection === 'new' && <WarehouseEditor key="new" warehouse={null} pending={save.isPending} save={submit} close={() => setSelection(null)} />}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading warehouses…" emptyMessage="No warehouses match this search." error={<>{query.error instanceof Error ? query.error.message : 'Warehouses could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table resource-table warehouse-table"><caption>Warehouse ledger</caption><thead><tr><th scope="col">Code / Site</th><th scope="col">Address</th><th scope="col">Coordinates</th><th scope="col">Updated</th>{admin && <th scope="col">Actions</th>}</tr></thead><tbody>{query.data?.items.map((row) => <Fragment key={row.id}><tr><td data-label="Code / Site"><strong className="scan-code">{row.code}</strong><small>{row.name}</small></td><td data-label="Address">{row.address}</td><td data-label="Coordinates">{row.latitude == null || row.longitude == null ? 'Not set' : `${row.latitude}, ${row.longitude}`}</td><td data-label="Updated"><time dateTime={row.updated_at}>{localTime.format(new Date(row.updated_at))}</time></td>{admin && <td data-label="Actions"><div className="resource-actions"><button type="button" className="quiet" aria-label={`Edit warehouse ${row.code}`} onClick={() => { setSelection(row); setDeleting(null) }}>Edit</button><button type="button" className="quiet" aria-label={`Delete warehouse ${row.code}`} onClick={() => { setDeleting(row); setSelection(null) }}>Delete</button></div></td>}</tr>{admin && selection !== 'new' && selection?.id === row.id && <tr><td colSpan={5}><WarehouseEditor key={row.id} warehouse={row} pending={save.isPending} save={submit} close={() => setSelection(null)} /></td></tr>}{admin && deleting?.id === row.id && <tr><td colSpan={5}><p role="alert">Delete warehouse {row.code}? This cannot be undone.</p><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>{remove.isPending ? 'Deleting…' : 'Confirm delete warehouse'}</button><button type="button" className="quiet" onClick={() => setDeleting(null)}>Cancel</button></td></tr>}</Fragment>)}</tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
