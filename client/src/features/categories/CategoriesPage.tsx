import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useManagementSession } from '../../app/ManagementProvider'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { Input } from '../../shared/ui/Input'
import { Select } from '../../shared/ui/Select'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Pagination } from '../../shared/ui/Pagination'
import { categoryKeys, createCategoriesApi } from './api'
import { categorySchema, type CategoryForm } from './schemas'
import type { Category, CategoryInput } from './types'

const pageSize = 20
function CategoryEditor({ category, rows, blocked, pending, save, close }: { category: Category | null; rows: Category[]; blocked: boolean; pending: boolean; save: (id: number | null, input: CategoryInput) => Promise<void>; close: () => void }) {
  const form = useForm<CategoryForm, unknown, CategoryInput>({ resolver: zodResolver(categorySchema), defaultValues: { name: category?.name ?? '', parent_id: category?.parent_id ? String(category.parent_id) : '' } })
  useEffect(() => { form.setFocus('name') }, [form])
  const busy = pending || form.formState.isSubmitting
  async function submit(input: CategoryInput) {
    form.clearErrors()
    if (blocked) return
    if (category && input.parent_id === category.id) { form.setError('parent_id', { message: 'Không thể chọn chính danh mục làm danh mục cha.' }); return }
    try { await save(category?.id ?? null, input) } catch (error) {
      if (error instanceof ApiError) for (const field of ['name', 'parent_id'] as const) if (error.fields?.[field]) form.setError(field, { message: 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.' })
      form.setError('root', { message: error instanceof ApiError ? error.message : 'Không thể lưu danh mục. Vui lòng thử lại.' })
    }
  }
  return <form className="management-panel management-form" aria-label={category ? 'Sửa danh mục' : 'Tạo danh mục'} noValidate onSubmit={form.handleSubmit(submit)}>
    <h2>{category ? 'Sửa danh mục ' + category.name : 'Tạo danh mục'}</h2>
    <div className="management-fields">
      <Input label="Tên danh mục" {...form.register('name')} error={form.formState.errors.name?.message} disabled={busy} />
      <Select label="Danh mục cha" placeholder="Không có danh mục cha" {...form.register('parent_id')} options={rows.filter(row => row.id !== category?.id).map(row => ({ value: row.id, label: row.name }))} error={form.formState.errors.parent_id?.message} disabled={busy || blocked} />
    </div>
    {form.formState.errors.root?.message && <FeedbackMessage variant="error">{form.formState.errors.root.message}</FeedbackMessage>}
    <div className="management-actions"><Button type="submit" disabled={blocked} isLoading={busy}>Lưu danh mục</Button><Button variant="secondary" disabled={busy} onClick={close}>Hủy</Button></div>
  </form>
}

export function CategoriesPage() {
  const { client, user } = useManagementSession(), api = createCategoriesApi(client), cache = useQueryClient()
  const admin = user?.role === 'admin'
  const [page, setPage] = useState(1), [selection, setSelection] = useState<Category | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Category | null>(null), [message, setMessage] = useState(''), [failure, setFailure] = useState(''), [attempt, setAttempt] = useState(0)
  const query = useQuery({ queryKey: categoryKeys.list({ page, pageSize }), queryFn: () => api.list({ page, pageSize }) })
  const lookup = useQuery({ queryKey: ['categories', 'lookup', 'all'], queryFn: api.listAll })
  useEffect(() => { if (query.isSuccess && !query.data.items.length && page > 1) setPage(Math.max(1, Math.ceil(query.data.total / pageSize))) }, [query.isSuccess, query.data, page])
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: categoryKeys.all }), cache.invalidateQueries({ queryKey: ['products'] })]) }
  const save = useMutation({ mutationFn: ({ id, input }: { id: number | null; input: CategoryInput }) => id ? api.update(id, input) : api.create(input), onSuccess: async (_, variables) => { await refresh(); setSelection(null); setMessage(variables.id ? 'Đã cập nhật danh mục.' : 'Đã tạo danh mục.') } })
  const remove = useMutation({ mutationFn: api.delete, onSuccess: async () => { await refresh(); setDeleting(null); setMessage('Đã xóa danh mục.') } })
  async function confirmDelete() {
    if (!deleting) return
    setFailure('')
    try { await remove.mutateAsync(deleting.id) } catch (error) { setFailure(error instanceof ApiError ? error.message : 'Không thể xóa danh mục. Vui lòng thử lại.'); setAttempt(value => value + 1) }
  }
  return <section className="management-workspace">
    <PageHeader title="Danh mục" description="Phân loại và tổ chức danh mục sản phẩm." actions={<><Button variant="secondary" onClick={() => void query.refetch()}>Tải lại danh mục</Button>{admin && <Button disabled={save.isPending} onClick={() => { setSelection('new'); setMessage('') }}>Tạo danh mục</Button>}</>} />
    {message && <FeedbackMessage variant="success">{message}</FeedbackMessage>}
    {lookup.isPending && <FeedbackMessage>Đang tải danh mục cha…</FeedbackMessage>}
    {lookup.isError && <FeedbackMessage variant="error" aria-label="Lỗi danh mục cha">Không thể tải đầy đủ danh mục cha. <Button variant="secondary" onClick={() => void lookup.refetch()}>Thử lại danh mục cha</Button></FeedbackMessage>}
    {admin && selection && <CategoryEditor key={selection === 'new' ? 'new' : selection.id} category={selection === 'new' ? null : selection} rows={lookup.data ?? []} blocked={!lookup.isSuccess} pending={save.isPending} save={async (id, input) => { setMessage(''); await save.mutateAsync({ id, input }) }} close={() => setSelection(null)} />}
    <div className="management-panel">
      {query.isPending ? <FeedbackMessage>Đang tải danh mục…</FeedbackMessage> : query.isError ? <FeedbackMessage variant="error" aria-label="Lỗi danh sách">{query.error instanceof ApiError ? query.error.message : 'Không thể tải danh mục.'} <Button variant="secondary" onClick={() => void query.refetch()}>Thử lại</Button></FeedbackMessage> : !query.data?.items.length ? <EmptyState title="Chưa có danh mục." /> :
        <DataTable caption="Danh sách danh mục" rows={query.data.items} getRowKey={row => row.id} columns={[
          { id: 'name', header: 'Danh mục', render: row => <strong>{row.name}</strong> },
          { id: 'parent', header: 'Danh mục cha', render: row => row.parent_id ? lookup.data?.find(parent => parent.id === row.parent_id)?.name ?? 'Danh mục #' + row.parent_id : 'Không có' },
          ...(admin ? [{ id: 'actions', header: 'Thao tác', render: (row: Category) => <div className="management-actions"><Button size="small" variant="secondary" disabled={save.isPending} aria-label={'Sửa danh mục ' + row.name} onClick={() => { setSelection(row); setMessage('') }}>Sửa</Button><Button size="small" variant="secondary" disabled={save.isPending} aria-label={'Xóa danh mục ' + row.name} onClick={() => { setDeleting(row); setFailure(''); setMessage('') }}>Xóa</Button></div> }] : []),
        ]} />}
      {query.data && <Pagination locale="vi" page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
    </div>
    {deleting && <ConfirmDialog key={attempt} open busy={remove.isPending} title="Xóa danh mục" description={'Xóa danh mục ' + deleting.name + '? Thao tác này không thể hoàn tác.'} confirmVariant="danger" confirmLabel="Xác nhận xóa danh mục" onCancel={() => setDeleting(null)} onConfirm={() => void confirmDelete()}>{failure && <FeedbackMessage variant="error">{failure}</FeedbackMessage>}</ConfirmDialog>}
  </section>
}
