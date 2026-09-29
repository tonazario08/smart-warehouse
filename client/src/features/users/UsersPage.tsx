import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/useAuth'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { createUsersApi } from './api'
import { UserActions } from './UserActions'
import { UserCreateForm } from './UserCreateForm'
import type { UserCreateInput } from './schemas'
import type { ManagedRole } from './types'

const pageSize = 20

export function UsersPage() {
  const { client } = useAuth()
  const api = createUsersApi(client)
  const cache = useQueryClient()
  const [page, setPage] = useState(1)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const filters = { page, pageSize }
  const query = useQuery({ queryKey: ['users', filters], queryFn: () => api.list(page, pageSize) })
  const refresh = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ['users'] }),
      cache.invalidateQueries({ queryKey: ['audit'] }),
    ])
  }
  const create = useMutation({ mutationFn: (input: UserCreateInput) => api.create(input), onSuccess: async () => { await refresh(); setError(null); setMessage('User created.') } })
  const changeRole = useMutation({ mutationFn: ({ id, role }: { id: number; role: ManagedRole }) => api.changeRole(id, role), onSuccess: async () => { await refresh(); setError(null); setMessage('Role updated.') } })
  const changeStatus = useMutation({ mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => api.changeStatus(id, is_active), onSuccess: async () => { await refresh(); setError(null); setMessage('Status updated.') } })
  const mutate = async (action: () => Promise<unknown>) => {
    setError(null)
    setMessage(null)
    try { await action() } catch (failure) { setError(failure instanceof Error ? failure.message : 'User could not be updated.'); throw failure }
  }

  return <section className="admin-workspace" aria-labelledby="users-heading">
    <header className="admin-heading"><div><h2 id="users-heading">Users</h2><p>Account access and status</p></div><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh roster</button></header>
    <UserCreateForm create={(input) => create.mutateAsync(input)} pending={create.isPending} onCreated={() => setPage(1)} />
    {message && <p className="form-success" role="status">{message}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'}
      loadingMessage="Loading users…" emptyMessage="No users found."
      error={<>{query.error instanceof Error ? query.error.message : 'Users could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table users-table"><caption>User roster</caption><thead><tr><th scope="col">Account</th><th scope="col">Status</th><th scope="col">Role</th><th scope="col">Actions</th></tr></thead><tbody>
        {query.data?.items.map((row) => <tr key={row.id}><td data-label="Account"><strong>{row.email}</strong><small>ID {row.id}</small></td><td data-label="Status">{row.is_active ? 'Active' : 'Inactive'}</td><td data-label="Role">{row.role}</td><td data-label="Actions"><UserActions user={row} pending={changeRole.isPending || changeStatus.isPending} onRoleChange={(role) => mutate(() => changeRole.mutateAsync({ id: row.id, role }))} onStatusChange={() => mutate(() => changeStatus.mutateAsync({ id: row.id, is_active: !row.is_active }))} /></td></tr>)}
      </tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
  </section>
}
