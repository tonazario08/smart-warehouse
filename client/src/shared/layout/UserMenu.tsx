import type { User } from '../../types'
import { Button } from '../ui/Button'

const roleLabel: Record<User['role'], string> = { admin: 'Quản trị viên', warehouse: 'Nhân viên kho', client: 'Khách hàng' }

export function UserMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  const initials = user.email.slice(0, 2).toUpperCase()
  const accountLabel = `Tài khoản ${roleLabel[user.role]}, ${user.email}`

  return <details className="user-menu">
    <summary aria-label={accountLabel} className="user-menu__trigger" title={accountLabel}>
      <span className="user-menu__avatar">{initials}</span>
      <span><strong>{roleLabel[user.role]}</strong><small>{user.email}</small></span>
    </summary>
    <div className="user-menu__panel" role="menu">
      <Button size="small" variant="ghost" onClick={onLogout}>Đăng xuất</Button>
    </div>
  </details>
}
