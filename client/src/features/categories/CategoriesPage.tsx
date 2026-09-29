import { useState } from 'react'
import { Fragment } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/ApiError'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { categoryKeys, createCategoriesApi } from './api'
import { categorySchema, type CategoryForm } from './schemas'
import type { Category, CategoryInput } from './types'

const pageSize = 20
type Selection = Category | 'new' | null

function CategoryEditor({ category, rows, pending, save, close }: {
  category: Category | null
  rows: Category[]
  pending: boolean
  save: (id: number | null, values: CategoryInput) => Promise<void>
  close: () => void
}) {
  const form = useForm<CategoryForm, unknown, CategoryInput>({ resolver: zodResolver(categorySchema), defaultValues: { name: category?.name ?? '', parent_id: category?.parent_id ? String(category.parent_id) : '' } })
  async function submit(values: CategoryInput) {
    form.clearErrors()
    try { await save(category?.id ?? null, values) } catch (error) {
      const fields = error instanceof ApiError ? error.fields : null
      for (const field of ['name', 'parent_id'] as const) {
        const value = fields?.[field]
        if (value) form.setError(field, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
      }
      form.setError('root', { type: 'server', message: error instanceof Error ? error.message : 'Category could not be saved.' })
    }
  }
  return <form className="admin-inline-form resource-editor" aria-label={category ? 'Edit category' : 'Create category'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h3>{category ? `Edit ${category.name}` : 'Create category'}</h3>
    <div className="admin-form-fields">
      <label>Name<input aria-invalid={Boolean(form.formState.errors.name)} aria-describedby={form.formState.errors.name ? 'category-name-error' : undefined} {...form.register('name')} />{form.formState.errors.name?.message && <small id="category-name-error" className="form-error">{form.formState.errors.name.message}</small>}</label>
      <label>Parent category<select {...form.register('parent_id')}><option value="">No parent</option>{rows.filter((row) => row.id !== category?.id).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
    </div>
    {form.formState.errors.root?.message && <p role="alert" className="form-error">{form.formState.errors.root.message}</p>}
    <div className="resource-actions"><button type="submit" disabled={pending || form.formState.isSubmitting}>{pending ? 'Saving…' : 'Save category'}</button><button type="button" className="quiet" onClick={close}>Cancel</button></div>
  </form>
}

export function CategoriesPage() {
  const { client, user } = useAuth()
  const admin = user?.role === 'admin'
  const api = createCategoriesApi(client)
  const cache = useQueryClient()
  const [page, setPage] = useState(1)
  const [selection, setSelection] = useState<Selection>(null)
  const [deleting, setDeleting] = useState<Category | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const filters = { page, pageSize }
  const query = useQuery({ queryKey: categoryKeys.list(filters), queryFn: () => api.list(filters) })
  const lookupFilters = { page: 1, pageSize: 100 }
  const lookup = useQuery({ queryKey: categoryKeys.list(lookupFilters), queryFn: () => api.list(lookupFilters), enabled: admin })
  const categoryRows = lookup.data?.items ?? query.data?.items ?? []
  const refresh = async () => Promise.all([cache.invalidateQueries({ queryKey: categoryKeys.all }), cache.invalidateQueries({ queryKey: ['products'] })])
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: CategoryInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await refresh(); setSelection(null); setFailure(null); setMessage(variables.id ? 'Category updated.' : 'Category created.') } })
  const remove = useMutation({ mutationFn: (id: number) => api.delete(id), onSuccess: async () => { await refresh(); setDeleting(null); setFailure(null); setMessage('Category deleted.') }, onError: (error) => setFailure(error instanceof Error ? error.message : 'Category could not be deleted.') })
  const submit = async (id: number | null, input: CategoryInput) => { setFailure(null); setMessage(null); await save.mutateAsync({ id, input }) }

  return <section className="admin-workspace" aria-labelledby="categories-heading">
    <header className="admin-heading"><div><h2 id="categories-heading">Categories</h2><p>Reference hierarchy for products</p></div><div className="resource-actions"><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh categories</button>{admin && <button type="button" onClick={() => { setSelection('new'); setDeleting(null); setMessage(null) }}>Create category</button>}</div></header>
    {message && <p className="form-success" role="status">{message}</p>}{failure && <p className="form-error" role="alert">{failure}</p>}
    {admin && selection === 'new' && <CategoryEditor key="new" category={null} rows={categoryRows} pending={save.isPending} save={submit} close={() => setSelection(null)} />}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading categories…" emptyMessage="No categories found." error={<>{query.error instanceof Error ? query.error.message : 'Categories could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table resource-table"><caption>Category ledger</caption><thead><tr><th scope="col">Category</th><th scope="col">Parent</th>{admin && <th scope="col">Actions</th>}</tr></thead><tbody>{query.data?.items.map((row) => <Fragment key={row.id}><tr><td data-label="Category"><strong>{row.name}</strong></td><td data-label="Parent">{categoryRows.find((parent) => parent.id === row.parent_id)?.name ?? '—'}</td>{admin && <td data-label="Actions"><div className="resource-actions"><button type="button" className="quiet" aria-label={`Edit category ${row.name}`} onClick={() => { setSelection(row); setDeleting(null) }}>Edit</button><button type="button" className="quiet" aria-label={`Delete category ${row.name}`} onClick={() => { setDeleting(row); setSelection(null) }}>Delete</button></div></td>}</tr>{admin && selection !== 'new' && selection?.id === row.id && <tr><td colSpan={3}><CategoryEditor key={row.id} category={row} rows={categoryRows} pending={save.isPending} save={submit} close={() => setSelection(null)} /></td></tr>}{admin && deleting?.id === row.id && <tr><td colSpan={3}><p role="alert">Delete category {row.name}? This cannot be undone.</p><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>{remove.isPending ? 'Deleting…' : 'Confirm delete category'}</button><button type="button" className="quiet" onClick={() => setDeleting(null)}>Cancel</button></td></tr>}</Fragment>)}</tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
