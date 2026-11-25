import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useManagementSession } from '../../app/ManagementProvider'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { createUsersApi } from './api'
import { UserActions } from './UserActions'
import { UserCreateForm } from './UserCreateForm'
import type { UserCreateInput } from './schemas'
import type { ManagedRole } from './types'

const pageSize = 20
const roleLabels = { admin: 'Quản trị viên', warehouse: 'Nhân viên kho', client: 'Khách hàng' }
export function UsersPage() {
  const { client } = useManagementSession(), api = createUsersApi(client), cache = useQueryClient()
  const [page, setPage] = useState(1), [message, setMessage] = useState('')
  const query = useQuery({ queryKey: ['users', { page, pageSize }], queryFn: () => api.list(page, pageSize) })
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: ['users'] }), cache.invalidateQueries({ queryKey: ['audit'] })]) }
  const create = useMutation({ mutationFn: (input: UserCreateInput) => api.create(input), onSuccess: async () => { await refresh(); setMessage('Đã tạo người dùng.') } })
  const changeRole = useMutation({ mutationFn: ({ id, role }: { id: number; role: ManagedRole }) => api.changeRole(id, role), onSuccess: async () => { await refresh(); setMessage('Đã cập nhật vai trò.') } })
  const changeStatus = useMutation({ mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => api.changeStatus(id, is_active), onSuccess: async () => { await refresh(); setMessage('Đã cập nhật trạng thái.') } })
  return <section className="management-workspace">
    <PageHeader title="Người dùng" description="Quản lý vai trò và trạng thái tài khoản." actions={<Button variant="secondary" onClick={() => void query.refetch()}>Tải lại người dùng</Button>} />
    <UserCreateForm create={input => { setMessage(''); return create.mutateAsync(input) }} pending={create.isPending} onCreated={() => setPage(1)} />
    {message && <FeedbackMessage variant="success">{message}</FeedbackMessage>}
    <div className="management-panel">
      {query.isPending ? <FeedbackMessage>Đang tải người dùng…</FeedbackMessage> : query.isError ? <FeedbackMessage variant="error">{query.error instanceof ApiError ? query.error.message : 'Không thể tải người dùng.'} <Button variant="secondary" onClick={() => void query.refetch()}>Thử lại</Button></FeedbackMessage> : !query.data?.items.length ? <EmptyState title="Chưa có người dùng." /> :
        <DataTable caption="Danh sách người dùng" rows={query.data.items} getRowKey={row => row.id} columns={[
          { id: 'email', header: 'Tài khoản', render: row => <><strong>{row.email}</strong><small>Mã tài khoản #{row.id}</small></> },
          { id: 'status', header: 'Trạng thái', render: row => row.is_active ? 'Đang hoạt động' : 'Đã vô hiệu hóa' },
          { id: 'role', header: 'Vai trò', render: row => roleLabels[row.role] },
          { id: 'actions', header: 'Thao tác', render: row => <UserActions user={row} pending={changeRole.isPending || changeStatus.isPending} onRoleChange={async role => { await changeRole.mutateAsync({ id: row.id, role }) }} onStatusChange={async () => { await changeStatus.mutateAsync({ id: row.id, is_active: !row.is_active }) }} /> },
        ]} />}
      {query.data && <Pagination locale="vi" page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
    </div>
  </section>
}
