import { useEffect, useState, type FormEvent } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useManagementSession } from '../../app/ManagementProvider'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Pagination } from '../../shared/ui/Pagination'
import { createSuppliersApi, supplierKeys } from './api'
import { supplierSchema, type SupplierForm } from './schemas'
import type { Supplier, SupplierInput } from './types'

const pageSize = 20
function SupplierEditor({ supplier, pending, save, close }: { supplier: Supplier | null; pending: boolean; save: (id: number | null, input: SupplierInput) => Promise<void>; close: () => void }) {
  const form = useForm<SupplierForm, unknown, SupplierInput>({ resolver: zodResolver(supplierSchema), defaultValues: { name: supplier?.name ?? '', email: supplier?.email ?? '', phone: supplier?.phone ?? '', address: supplier?.address ?? '' } })
  useEffect(() => { form.setFocus('name') }, [form])
  const busy = pending || form.formState.isSubmitting
  async function submit(input: SupplierInput) {
    form.clearErrors()
    try { await save(supplier?.id ?? null, input) } catch (error) {
      if (error instanceof ApiError) for (const field of ['name', 'email', 'phone', 'address'] as const) if (error.fields?.[field]) form.setError(field, { message: 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.' })
      form.setError('root', { message: error instanceof ApiError ? error.message : 'Không thể lưu nhà cung cấp. Vui lòng thử lại.' })
    }
  }
  return <form className="management-panel management-form" aria-label={supplier ? 'Sửa nhà cung cấp' : 'Tạo nhà cung cấp'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h2>{supplier ? 'Sửa nhà cung cấp ' + supplier.name : 'Tạo nhà cung cấp'}</h2>
    <div className="management-fields">
      <Input label="Tên nhà cung cấp" {...form.register('name')} error={form.formState.errors.name?.message} disabled={busy} />
      <Input label="Email" type="email" {...form.register('email')} error={form.formState.errors.email?.message} disabled={busy} />
      <Input label="Số điện thoại" type="tel" {...form.register('phone')} error={form.formState.errors.phone?.message} disabled={busy} />
      <Input label="Địa chỉ" {...form.register('address')} error={form.formState.errors.address?.message} disabled={busy} />
    </div>
    {form.formState.errors.root?.message && <FeedbackMessage variant="error">{form.formState.errors.root.message}</FeedbackMessage>}
    <div className="management-actions"><Button type="submit" isLoading={busy}>Lưu nhà cung cấp</Button><Button variant="secondary" disabled={busy} onClick={close}>Hủy</Button></div>
  </form>
}

export function SuppliersPage() {
  const { client, user } = useManagementSession(), api = createSuppliersApi(client), cache = useQueryClient(), admin = user?.role === 'admin'
  const [page, setPage] = useState(1), [search, setSearch] = useState(''), [filter, setFilter] = useState('')
  const [selection, setSelection] = useState<Supplier | 'new' | null>(null), [deleting, setDeleting] = useState<Supplier | null>(null)
  const [message, setMessage] = useState(''), [failure, setFailure] = useState(''), [attempt, setAttempt] = useState(0)
  const listFilters = { page, pageSize, search: filter }
  const query = useQuery({ queryKey: supplierKeys.list(listFilters), queryFn: () => api.list(listFilters) })
  useEffect(() => { if (query.isSuccess && !query.data.items.length && page > 1) setPage(Math.max(1, Math.ceil(query.data.total / pageSize))) }, [query.isSuccess, query.data, page])
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: supplierKeys.all }), cache.invalidateQueries({ queryKey: ['products'] })]) }
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: SupplierInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await refresh(); setSelection(null); setMessage(variables.id ? 'Đã cập nhật nhà cung cấp.' : 'Đã tạo nhà cung cấp.') } })
  const remove = useMutation({ mutationFn: api.delete, onSuccess: async () => { await refresh(); setDeleting(null); setMessage('Đã xóa nhà cung cấp.') } })
  function apply(event: FormEvent) { event.preventDefault(); if (save.isPending) return; setPage(1); setFilter(search.trim()); setSelection(null) }
  async function confirmDelete() {
    if (!deleting) return
    setFailure('')
    try { await remove.mutateAsync(deleting.id) } catch (error) { setFailure(error instanceof ApiError ? error.message : 'Không thể xóa nhà cung cấp. Vui lòng thử lại.'); setAttempt(value => value + 1) }
  }
  return <section className="management-workspace">
    <PageHeader title="Nhà cung cấp" description="Thông tin đối tác cung ứng hàng hóa." actions={<><Button variant="secondary" onClick={() => void query.refetch()}>Tải lại nhà cung cấp</Button>{admin && <Button disabled={save.isPending} onClick={() => { setSelection('new'); setMessage('') }}>Tạo nhà cung cấp</Button>}</>} />
    <form className="management-panel management-filters" aria-label="Lọc nhà cung cấp" onSubmit={apply}><Input label="Tìm nhà cung cấp" disabled={save.isPending} value={search} onChange={event => setSearch(event.target.value)} /><Button type="submit" disabled={save.isPending}>Áp dụng bộ lọc</Button></form>
    {message && <FeedbackMessage variant="success">{message}</FeedbackMessage>}
    {admin && selection && <SupplierEditor key={selection === 'new' ? 'new' : selection.id} supplier={selection === 'new' ? null : selection} pending={save.isPending} save={async (id, input) => { setMessage(''); await save.mutateAsync({ id, input }) }} close={() => setSelection(null)} />}
    <div className="management-panel">
      {query.isPending ? <FeedbackMessage>Đang tải nhà cung cấp…</FeedbackMessage> : query.isError ? <FeedbackMessage variant="error">{query.error instanceof ApiError ? query.error.message : 'Không thể tải nhà cung cấp.'} <Button variant="secondary" onClick={() => void query.refetch()}>Thử lại</Button></FeedbackMessage> : !query.data?.items.length ? <EmptyState title="Không có nhà cung cấp phù hợp." /> :
        <DataTable caption="Danh sách nhà cung cấp" rows={query.data.items} getRowKey={row => row.id} columns={[
          { id: 'name', header: 'Nhà cung cấp', render: row => <strong>{row.name}</strong> },
          { id: 'contact', header: 'Liên hệ', render: row => <>{row.email ?? '—'}{row.phone && <small>{row.phone}</small>}</> },
          { id: 'address', header: 'Địa chỉ', render: row => row.address ?? '—' },
          ...(admin ? [{ id: 'actions', header: 'Thao tác', render: (row: Supplier) => <div className="management-actions"><Button size="small" variant="secondary" disabled={save.isPending} aria-label={'Sửa nhà cung cấp ' + row.name} onClick={() => { setSelection(row); setMessage('') }}>Sửa</Button><Button size="small" variant="secondary" disabled={save.isPending} aria-label={'Xóa nhà cung cấp ' + row.name} onClick={() => { setDeleting(row); setFailure(''); setMessage('') }}>Xóa</Button></div> }] : []),
        ]} />}
      {query.data && <Pagination locale="vi" page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
    </div>
    {deleting && <ConfirmDialog key={attempt} open busy={remove.isPending} title="Xóa nhà cung cấp" description={'Xóa nhà cung cấp ' + deleting.name + '? Thao tác này không thể hoàn tác.'} confirmVariant="danger" confirmLabel="Xác nhận xóa nhà cung cấp" onCancel={() => setDeleting(null)} onConfirm={() => void confirmDelete()}>{failure && <FeedbackMessage variant="error">{failure}</FeedbackMessage>}</ConfirmDialog>}
  </section>
}
