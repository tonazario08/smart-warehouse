import { useState } from 'react'
import type { ManagedRole, ManagedUser } from './types'

export function UserActions({ user, pending, onRoleChange, onStatusChange }: {
  user: ManagedUser
  pending: boolean
  onRoleChange: (role: ManagedRole) => Promise<void>
  onStatusChange: () => Promise<void>
}) {
  const [confirm, setConfirm] = useState<'role' | 'status' | null>(null)
  const [role, setRole] = useState<ManagedRole>(user.role === 'client' ? 'warehouse' : 'client')
  if (user.role === 'admin') return <span className="admin-protected">Administrator account <button type="button" className="quiet" aria-label={`Change role for ${user.email}`} disabled>Change role</button><button type="button" className="quiet" aria-label={`Change status for ${user.email}`} disabled>Change status</button></span>

  return <div className="user-actions">
    {confirm === 'role' ? <div className="confirm-actions">
      <label htmlFor={`role-${user.id}`}>Confirm role change for {user.email}</label>
      <select id={`role-${user.id}`} value={role} onChange={(event) => setRole(event.target.value as ManagedRole)}><option value="client">Client</option><option value="warehouse">Warehouse</option></select>
      <button type="button" disabled={pending} onClick={() => void onRoleChange(role).then(() => setConfirm(null)).catch(() => undefined)}>Confirm role change</button>
      <button type="button" className="quiet" onClick={() => setConfirm(null)}>Cancel</button>
    </div> : confirm === 'status' ? <div className="confirm-actions">
      <p>Confirm {user.is_active ? 'deactivation' : 'activation'} for {user.email}?</p>
      <button type="button" disabled={pending} onClick={() => void onStatusChange().then(() => setConfirm(null)).catch(() => undefined)}>Confirm {user.is_active ? 'deactivation' : 'activation'}</button>
      <button type="button" className="quiet" onClick={() => setConfirm(null)}>Cancel</button>
    </div> : <>
      <button type="button" className="quiet" disabled={pending} aria-label={`Change role for ${user.email}`} onClick={() => setConfirm('role')}>Change role</button>
      <button type="button" className="quiet" disabled={pending} aria-label={`${user.is_active ? 'Deactivate' : 'Activate'} ${user.email}`} onClick={() => setConfirm('status')}>{user.is_active ? 'Deactivate' : 'Activate'}</button>
    </>}
  </div>
}
