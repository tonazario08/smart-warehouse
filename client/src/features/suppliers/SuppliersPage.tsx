import { useState, type FormEvent } from 'react'
import { Fragment } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/ApiError'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { createSuppliersApi, supplierKeys } from './api'
import { supplierSchema, type SupplierForm } from './schemas'
import type { Supplier, SupplierInput } from './types'

const pageSize = 20
type Selection = Supplier | 'new' | null

function SupplierEditor({ supplier, pending, save, close }: { supplier: Supplier | null; pending: boolean; save: (id: number | null, input: SupplierInput) => Promise<void>; close: () => void }) {
  const form = useForm<SupplierForm, unknown, SupplierInput>({ resolver: zodResolver(supplierSchema), defaultValues: { name: supplier?.name ?? '', email: supplier?.email ?? '', phone: supplier?.phone ?? '', address: supplier?.address ?? '' } })
  async function submit(values: SupplierInput) {
    form.clearErrors()
    try { await save(supplier?.id ?? null, values) } catch (error) {
      const fields = error instanceof ApiError ? error.fields : null
      for (const field of ['name', 'email', 'phone', 'address'] as const) {
        const value = fields?.[field]
        if (value) form.setError(field, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
      }
      form.setError('root', { type: 'server', message: error instanceof Error ? error.message : 'Supplier could not be saved.' })
    }
  }
  return <form className="admin-inline-form resource-editor" aria-label={supplier ? 'Edit supplier' : 'Create supplier'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h3>{supplier ? `Edit ${supplier.name}` : 'Create supplier'}</h3>
    <div className="admin-form-fields">
      <label>Name<input {...form.register('name')} aria-invalid={Boolean(form.formState.errors.name)} aria-describedby={form.formState.errors.name ? 'supplier-name-error' : undefined} />{form.formState.errors.name?.message && <small id="supplier-name-error" className="form-error">{form.formState.errors.name.message}</small>}</label>
      <label>Email<input type="email" {...form.register('email')} aria-invalid={Boolean(form.formState.errors.email)} aria-describedby={form.formState.errors.email ? 'supplier-email-error' : undefined} />{form.formState.errors.email?.message && <small id="supplier-email-error" className="form-error">{form.formState.errors.email.message}</small>}</label>
      <label>Phone<input {...form.register('phone')} /></label><label>Address<input {...form.register('address')} /></label>
    </div>
    {form.formState.errors.root?.message && <p role="alert" className="form-error">{form.formState.errors.root.message}</p>}
    <div className="resource-actions"><button type="submit" disabled={pending || form.formState.isSubmitting}>{pending ? 'Saving…' : 'Save supplier'}</button><button type="button" className="quiet" onClick={close}>Cancel</button></div>
  </form>
}

export function SuppliersPage() {
  const { client, user } = useAuth()
  const admin = user?.role === 'admin'
  const api = createSuppliersApi(client)
  const cache = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ search: '' })
  const [selection, setSelection] = useState<Selection>(null)
  const [deleting, setDeleting] = useState<Supplier | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const listFilters = { page, pageSize, ...filters }
  const query = useQuery({ queryKey: supplierKeys.list(listFilters), queryFn: () => api.list(listFilters) })
  const invalidate = async () => Promise.all([cache.invalidateQueries({ queryKey: supplierKeys.all }), cache.invalidateQueries({ queryKey: ['products'] })])
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: SupplierInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await invalidate(); setSelection(null); setFailure(null); setMessage(variables.id ? 'Supplier updated.' : 'Supplier created.') } })
  const remove = useMutation({ mutationFn: api.delete, onSuccess: async () => { await invalidate(); setDeleting(null); setFailure(null); setMessage('Supplier deleted.') }, onError: (error) => setFailure(error instanceof Error ? error.message : 'Supplier could not be deleted.') })
  const submit = async (id: number | null, input: SupplierInput) => { setFailure(null); setMessage(null); await save.mutateAsync({ id, input }) }
  function apply(event: FormEvent) { event.preventDefault(); setPage(1); setFilters({ search: search.trim() }) }

  return <section className="admin-workspace" aria-labelledby="suppliers-heading">
    <header className="admin-heading"><div><h2 id="suppliers-heading">Suppliers</h2><p>Approved sources for warehouse inventory</p></div><div className="resource-actions"><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh suppliers</button>{admin && <button type="button" onClick={() => { setSelection('new'); setDeleting(null); setMessage(null) }}>Create supplier</button>}</div></header>
    <form className="resource-filters" aria-label="Filter suppliers" onSubmit={apply}><label htmlFor="supplier-search">Search suppliers<input id="supplier-search" value={search} onChange={(event) => setSearch(event.target.value)} /></label><button type="submit">Apply filters</button></form>
    {message && <p role="status" className="form-success">{message}</p>}{failure && <p role="alert" className="form-error">{failure}</p>}
    {admin && selection === 'new' && <SupplierEditor key="new" supplier={null} pending={save.isPending} save={submit} close={() => setSelection(null)} />}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading suppliers…" emptyMessage="No suppliers match this search." error={<>{query.error instanceof Error ? query.error.message : 'Suppliers could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table resource-table"><caption>Supplier ledger</caption><thead><tr><th scope="col">Supplier</th><th scope="col">Contact</th><th scope="col">Address</th>{admin && <th scope="col">Actions</th>}</tr></thead><tbody>{query.data?.items.map((row) => <Fragment key={row.id}><tr><td data-label="Supplier"><strong>{row.name}</strong></td><td data-label="Contact">{row.email ?? '—'}{row.phone && <small>{row.phone}</small>}</td><td data-label="Address">{row.address ?? '—'}</td>{admin && <td data-label="Actions"><div className="resource-actions"><button type="button" className="quiet" aria-label={`Edit supplier ${row.name}`} onClick={() => { setSelection(row); setDeleting(null) }}>Edit</button><button type="button" className="quiet" aria-label={`Delete supplier ${row.name}`} onClick={() => { setDeleting(row); setSelection(null) }}>Delete</button></div></td>}</tr>{admin && selection !== 'new' && selection?.id === row.id && <tr><td colSpan={4}><SupplierEditor key={row.id} supplier={row} pending={save.isPending} save={submit} close={() => setSelection(null)} /></td></tr>}{admin && deleting?.id === row.id && <tr><td colSpan={4}><p role="alert">Delete supplier {row.name}? This cannot be undone.</p><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>{remove.isPending ? 'Deleting…' : 'Confirm delete supplier'}</button><button type="button" className="quiet" onClick={() => setDeleting(null)}>Cancel</button></td></tr>}</Fragment>)}</tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
