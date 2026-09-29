import { useState, type FormEvent } from 'react'
import { Fragment } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/ApiError'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { useAuth } from '../auth/useAuth'
import { categoryKeys, createCategoriesApi } from '../categories/api'
import { createSuppliersApi, supplierKeys } from '../suppliers/api'
import type { Category } from '../categories/types'
import type { Supplier } from '../suppliers/types'
import { createProductsApi, productKeys } from './api'
import { productSchema, type ProductForm } from './schemas'
import type { Product, ProductInput, ProductFilters } from './types'

const pageSize = 20
type Selection = Product | 'new' | null
const blankFilters: ProductFilters = { page: 1, pageSize, search: '', categoryId: '', supplierId: '', isActive: '' }

function ProductEditor({ product, categories, suppliers, pending, save, close }: {
  product: Product | null; categories: Category[]; suppliers: Supplier[]; pending: boolean
  save: (id: number | null, input: ProductInput) => Promise<void>; close: () => void
}) {
  const form = useForm<ProductForm, unknown, ProductInput>({ resolver: zodResolver(productSchema), defaultValues: {
    sku: product?.sku ?? '', name: product?.name ?? '', description: product?.description ?? '',
    category_id: product ? String(product.category_id) : '', supplier_id: product?.supplier_id ? String(product.supplier_id) : '',
    unit: product?.unit ?? '', reorder_level: String(product?.reorder_level ?? 0), is_active: product?.is_active ?? true,
  } })
  async function submit(values: ProductInput) {
    form.clearErrors()
    try { await save(product?.id ?? null, values) } catch (error) {
      const fields = error instanceof ApiError ? error.fields : null
      for (const field of ['sku', 'name', 'description', 'category_id', 'supplier_id', 'unit', 'reorder_level', 'is_active'] as const) {
        const value = fields?.[field]
        if (value) form.setError(field, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
      }
      form.setError('root', { type: 'server', message: error instanceof Error ? error.message : 'Product could not be saved.' })
    }
  }
  return <form className="admin-inline-form resource-editor" aria-label={product ? 'Edit product' : 'Create product'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h3>{product ? `Edit ${product.sku}` : 'Create product'}</h3>
    <div className="admin-form-fields">
      <label>SKU<input {...form.register('sku')} aria-invalid={Boolean(form.formState.errors.sku)} onChange={(event) => form.setValue('sku', event.target.value.toUpperCase(), { shouldValidate: true })} />{form.formState.errors.sku?.message && <small className="form-error">{form.formState.errors.sku.message}</small>}</label>
      <label>Name<input {...form.register('name')} />{form.formState.errors.name?.message && <small className="form-error">{form.formState.errors.name.message}</small>}</label>
      <label>Description<input {...form.register('description')} /></label>
      <label>Category<select {...form.register('category_id')}><option value="">Choose category</option>{categories.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>{form.formState.errors.category_id?.message && <small className="form-error">{form.formState.errors.category_id.message}</small>}</label>
      <label>Supplier<select {...form.register('supplier_id')}><option value="">No supplier</option>{suppliers.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label>Unit<input {...form.register('unit')} /></label>
      <label>Reorder level<input type="number" min="0" step="1" {...form.register('reorder_level')} /></label>
      <label className="resource-checkbox"><input type="checkbox" {...form.register('is_active')} />Active</label>
    </div>
    {form.formState.errors.root?.message && <p role="alert" className="form-error">{form.formState.errors.root.message}</p>}
    <div className="resource-actions"><button type="submit" disabled={pending || form.formState.isSubmitting}>{pending ? 'Saving…' : 'Save product'}</button><button type="button" className="quiet" onClick={close}>Cancel</button></div>
  </form>
}

export function ProductsPage() {
  const { client, user } = useAuth()
  const admin = user?.role === 'admin'
  const canReadSuppliers = user?.role === 'admin' || user?.role === 'warehouse'
  const api = createProductsApi(client)
  const cache = useQueryClient()
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [supplierId, setSupplierId] = useState('')
  const [isActive, setIsActive] = useState('')
  const [filters, setFilters] = useState(blankFilters)
  const [selection, setSelection] = useState<Selection>(null)
  const [deleting, setDeleting] = useState<Product | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const query = useQuery({ queryKey: productKeys.list(filters), queryFn: () => api.list(filters) })
  const lookupPage = { page: 1, pageSize: 100 }
  const categories = useQuery({ queryKey: categoryKeys.list(lookupPage), queryFn: () => createCategoriesApi(client).list(lookupPage) })
  const suppliers = useQuery({ queryKey: supplierKeys.list({ ...lookupPage, search: '' }), queryFn: () => createSuppliersApi(client).list({ ...lookupPage, search: '' }), enabled: canReadSuppliers })
  const invalidate = async () => cache.invalidateQueries({ queryKey: productKeys.all })
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: ProductInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await invalidate(); setSelection(null); setFailure(null); setMessage(variables.id ? 'Product updated.' : 'Product created.') } })
  const remove = useMutation({ mutationFn: api.delete, onSuccess: async () => { await invalidate(); setDeleting(null); setFailure(null); setMessage('Product deleted.') }, onError: (error) => setFailure(error instanceof Error ? error.message : 'Product could not be deleted.') })
  const submit = async (id: number | null, input: ProductInput) => { setFailure(null); setMessage(null); await save.mutateAsync({ id, input }) }
  function apply(event: FormEvent) { event.preventDefault(); setFilters({ page: 1, pageSize, search: search.trim(), categoryId, supplierId, isActive }) }
  const categoryRows = categories.data?.items ?? []
  const supplierRows = suppliers.data?.items ?? []

  return <section className="admin-workspace" aria-labelledby="products-heading">
    <header className="admin-heading"><div><h2 id="products-heading">Products</h2><p>Catalogue and replenishment thresholds</p></div><div className="resource-actions"><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh products</button>{admin && <button type="button" onClick={() => { setSelection('new'); setDeleting(null); setMessage(null) }}>Create product</button>}</div></header>
    <form className="resource-filters product-filters" aria-label="Filter products" onSubmit={apply}>
      <label>Search products<input value={search} onChange={(event) => setSearch(event.target.value)} /></label>
      <label>Category filter<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">All categories</option>{categoryRows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      {canReadSuppliers && <label>Supplier filter<select value={supplierId} onChange={(event) => setSupplierId(event.target.value)}><option value="">All suppliers</option>{supplierRows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
      <label>Active status filter<select value={isActive} onChange={(event) => setIsActive(event.target.value)}><option value="">All status</option><option value="true">Active</option><option value="false">Inactive</option></select></label>
      <button type="submit">Apply filters</button>
    </form>
    {message && <p role="status" className="form-success">{message}</p>}{failure && <p role="alert" className="form-error">{failure}</p>}
    {admin && selection === 'new' && <ProductEditor key="new" product={null} categories={categoryRows} suppliers={supplierRows} pending={save.isPending} save={submit} close={() => setSelection(null)} />}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading products…" emptyMessage="No products match these filters." error={<>{query.error instanceof Error ? query.error.message : 'Products could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table resource-table"><caption>Product ledger</caption><thead><tr><th scope="col">SKU / Product</th><th scope="col">Category / Supplier</th><th scope="col">Unit / Reorder</th><th scope="col">Status</th>{admin && <th scope="col">Actions</th>}</tr></thead><tbody>{query.data?.items.map((row) => <Fragment key={row.id}><tr><td data-label="SKU / Product"><strong className="scan-code">{row.sku}</strong><small>{row.name}</small>{row.description && <small>{row.description}</small>}</td><td data-label="Category / Supplier">{categoryRows.find((value) => value.id === row.category_id)?.name ?? `Category ${row.category_id}`}<small>{row.supplier_id ? supplierRows.find((value) => value.id === row.supplier_id)?.name ?? `Supplier ${row.supplier_id}` : 'No supplier'}</small></td><td data-label="Unit / Reorder">{row.unit}<small>Reorder at {row.reorder_level}</small></td><td data-label="Status">{row.is_active ? 'Active' : 'Inactive'}</td>{admin && <td data-label="Actions"><div className="resource-actions"><button type="button" className="quiet" aria-label={`Edit product ${row.sku}`} onClick={() => { setSelection(row); setDeleting(null) }}>Edit</button><button type="button" className="quiet" aria-label={`Delete product ${row.sku}`} onClick={() => { setDeleting(row); setSelection(null) }}>Delete</button></div></td>}</tr>{admin && selection !== 'new' && selection?.id === row.id && <tr><td colSpan={5}><ProductEditor key={row.id} product={row} categories={categoryRows} suppliers={supplierRows} pending={save.isPending} save={submit} close={() => setSelection(null)} /></td></tr>}{admin && deleting?.id === row.id && <tr><td colSpan={5}><p role="alert">Delete product {row.sku}? This cannot be undone.</p><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>{remove.isPending ? 'Deleting…' : 'Confirm delete product'}</button><button type="button" className="quiet" onClick={() => setDeleting(null)}>Cancel</button></td></tr>}</Fragment>)}</tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={filters.page} pageSize={pageSize} total={query.data.total} onPageChange={(page) => setFilters({ ...filters, page })} />}
  </section>
}
