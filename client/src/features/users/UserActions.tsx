import { useState } from 'react'
import type { ManagedRole, ManagedUser } from './types'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'

export function UserActions({ user, pending, onRoleChange, onStatusChange }: { user: ManagedUser; pending: boolean; onRoleChange: (role: ManagedRole) => Promise<void>; onStatusChange: () => Promise<void> }) {
  const [confirm, setConfirm] = useState<'role' | 'status' | null>(null)
  const [role, setRole] = useState<ManagedRole>('client')
  const [failure, setFailure] = useState('')
  const [attempt, setAttempt] = useState(0)
  const open = (kind: 'role' | 'status') => { setRole(user.role === 'client' ? 'warehouse' : 'client'); setFailure(''); setConfirm(kind) }
  const title = confirm === 'role' ? 'Xác nhận đổi vai trò' : user.is_active ? 'Xác nhận vô hiệu hóa' : 'Xác nhận kích hoạt'
  async function submit() {
    setFailure('')
    if (confirm === 'role' && role !== 'client' && role !== 'warehouse') { setFailure('Chọn vai trò được hỗ trợ.'); setAttempt(value => value + 1); return }
    try { await (confirm === 'role' ? onRoleChange(role) : onStatusChange()); setConfirm(null) }
    catch (error) { setFailure(error instanceof ApiError ? error.message : 'Không thể cập nhật tài khoản. Vui lòng thử lại.'); setAttempt(value => value + 1) }
  }
  if (user.role === 'admin') return <div className="management-actions"><span>Tài khoản quản trị được bảo vệ</span><Button size="small" variant="secondary" aria-label={'Đổi vai trò cho ' + user.email} disabled>Đổi vai trò</Button><Button size="small" variant="secondary" aria-label={'Đổi trạng thái cho ' + user.email} disabled>Đổi trạng thái</Button></div>
  return <div className="management-actions">
    <Button size="small" variant="secondary" disabled={pending} aria-label={'Đổi vai trò cho ' + user.email} onClick={() => open('role')}>Đổi vai trò</Button>
    <Button size="small" variant="secondary" disabled={pending} aria-label={(user.is_active ? 'Vô hiệu hóa ' : 'Kích hoạt ') + user.email} onClick={() => open('status')}>{user.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'}</Button>
    {confirm && <ConfirmDialog key={attempt} open busy={pending} title={title} description={'Áp dụng thay đổi cho ' + user.email + '?'} confirmLabel={title} onCancel={() => setConfirm(null)} onConfirm={() => void submit()}>
      {confirm === 'role' && <Select label="Vai trò mới" value={role} disabled={pending} onChange={event => setRole(event.target.value as ManagedRole)} options={[{ value: 'client', label: 'Khách hàng' }, { value: 'warehouse', label: 'Nhân viên kho' }]} />}
      {failure && <FeedbackMessage variant="error">{failure}</FeedbackMessage>}
    </ConfirmDialog>}
  </div>
}
