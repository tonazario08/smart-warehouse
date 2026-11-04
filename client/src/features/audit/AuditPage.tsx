import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useManagementSession } from '../../app/ManagementProvider'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { Input } from '../../shared/ui/Input'
import { Select } from '../../shared/ui/Select'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { formatDateTime } from '../../shared/lib/formatters'
import { createAuditApi } from './api'
import type { AuditFilters } from './types'

const pageSize = 20
const actions: Record<string, string> = { 'user.created': 'Tạo người dùng', 'user.role_changed': 'Đổi vai trò', 'user.status_changed': 'Đổi trạng thái' }
const roles: Record<string, string> = { admin: 'Quản trị viên', warehouse: 'Nhân viên kho', client: 'Khách hàng' }
const translated = (labels: Record<string, string>, value: string) => Object.hasOwn(labels, value) ? labels[value] : 'Không xác định'
function Facts({ data }: { data: Record<string, unknown> | null }) {
  const fields = ['email', 'role', 'is_active'].filter(field => data && Object.hasOwn(data, field))
  if (!fields.length) return <span>Không có</span>
  return <dl className="management-facts">{fields.map(field => {
    const value = data?.[field]
    const label = field === 'email' ? 'Email' : field === 'role' ? 'Vai trò' : 'Trạng thái'
    const text = field === 'email' ? typeof value === 'string' ? value : 'Không xác định' : field === 'role' ? typeof value === 'string' ? translated(roles, value) : 'Không xác định' : value === true ? 'Đang hoạt động' : value === false ? 'Đã vô hiệu hóa' : 'Không xác định'
    return <div key={field}><dt>{label}</dt><dd>{text}</dd></div>
  })}</dl>
}
export function AuditPage() {
  const { client } = useManagementSession()
  const [action, setAction] = useState(''), [targetType, setTargetType] = useState(''), [targetId, setTargetId] = useState(''), [error, setError] = useState('')
  const [filters, setFilters] = useState<AuditFilters>({ page: 1, pageSize, action: '', targetType: '', targetId: '' })
  const query = useQuery({ queryKey: ['audit', filters], queryFn: () => createAuditApi(client).list(filters) })
  function apply(event: FormEvent) {
    event.preventDefault()
    if (targetId && (!/^[1-9]\d*$/.test(targetId) || Number(targetId) > 2147483647)) { setError('Mã đối tượng phải là số nguyên dương hợp lệ.'); return }
    setError(''); setFilters({ page: 1, pageSize, action, targetType: targetType.trim(), targetId })
  }
  return <section className="management-workspace">
    <PageHeader title="Nhật ký quản trị" description="Theo dõi thay đổi tài khoản, mới nhất trước. Chỉ hiển thị các trường được phép." actions={<Button variant="secondary" onClick={() => void query.refetch()}>Tải lại nhật ký</Button>} />
    <form className="management-panel management-filters" aria-label="Lọc nhật ký quản trị" onSubmit={apply}>
      <Select label="Hành động" placeholder="Tất cả hành động" value={action} onChange={event => setAction(event.target.value)} options={Object.entries(actions).map(([value, label]) => ({ value, label }))} />
      <Input label="Loại đối tượng" placeholder="Tất cả loại" value={targetType} onChange={event => setTargetType(event.target.value)} />
      <Input label="Mã đối tượng" placeholder="Tất cả mã" inputMode="numeric" value={targetId} onChange={event => setTargetId(event.target.value)} />
      <Button type="submit">Áp dụng bộ lọc</Button>
    </form>
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    <div className="management-panel">
      {query.isPending ? <FeedbackMessage>Đang tải nhật ký…</FeedbackMessage> : query.isError ? <FeedbackMessage variant="error">{query.error instanceof ApiError ? query.error.message : 'Không thể tải nhật ký.'} <Button variant="secondary" onClick={() => void query.refetch()}>Thử lại</Button></FeedbackMessage> : !query.data?.items.length ? <EmptyState title="Không có nhật ký phù hợp." /> :
        <DataTable caption="Nhật ký thay đổi quản trị" rows={query.data.items} getRowKey={row => row.id} columns={[
          { id: 'time', header: 'Thời điểm', render: row => <time dateTime={row.created_at}>{formatDateTime(row.created_at)}</time> },
          { id: 'actor', header: 'Người thực hiện', render: row => 'Tài khoản #' + row.actor_user_id },
          { id: 'action', header: 'Hành động', render: row => translated(actions, row.action) },
          { id: 'target', header: 'Đối tượng', render: row => (row.target_type === 'user' ? 'Người dùng #' : 'Đối tượng #') + row.target_id },
          { id: 'before', header: 'Trước thay đổi', render: row => <Facts data={row.before_data} /> },
          { id: 'after', header: 'Sau thay đổi', render: row => <Facts data={row.after_data} /> },
        ]} />}
      {query.data && <Pagination locale="vi" page={filters.page} pageSize={pageSize} total={query.data.total} onPageChange={page => setFilters(current => ({ ...current, page }))} />}
    </div>
  </section>
}
