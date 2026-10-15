import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/useAuth'
import { AsyncState } from '../../shared/ui/AsyncState'
import { Pagination } from '../../shared/ui/Pagination'
import { createAuditApi } from './api'
import type { AuditFilters } from './types'

const pageSize = 20
const visibleFields = ['email', 'role', 'is_active'] as const
const timestamp = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function Facts({ data }: { data: Record<string, unknown> | null }) {
  const facts = visibleFields.filter((field) => data && Object.hasOwn(data, field))
  if (!facts.length) return <span>None</span>
  return <dl className="audit-facts">{facts.map((field) => <div key={field}><dt>{field === 'is_active' ? 'Active' : field === 'email' ? 'Email' : 'Role'}</dt><dd>{String(data?.[field])}</dd></div>)}</dl>
}

export function AuditPage() {
  const { client } = useAuth()
  const [action, setAction] = useState('')
  const [targetType, setTargetType] = useState('')
  const [targetId, setTargetId] = useState('')
  const [filterError, setFilterError] = useState<string | null>(null)
  const [filters, setFilters] = useState<AuditFilters>({ page: 1, pageSize, action: '', targetType: '', targetId: '' })
  const query = useQuery({ queryKey: ['audit', filters], queryFn: () => createAuditApi(client).list(filters) })

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (targetId && !/^[1-9]\d*$/.test(targetId)) { setFilterError('Target ID must be a positive whole number.'); return }
    setFilterError(null)
    setFilters({ page: 1, pageSize, action, targetType: targetType.trim(), targetId })
  }

  return <section className="admin-workspace" aria-labelledby="audit-heading">
    <header className="admin-heading"><div><h2 id="audit-heading">Audit</h2><p>Administrative changes, newest first</p></div><button type="button" className="quiet" onClick={() => void query.refetch()}>Refresh ledger</button></header>
    <form className="audit-filters" onSubmit={applyFilters} aria-label="Filter audit history">
      <label htmlFor="audit-action">Action<select id="audit-action" value={action} onChange={(event) => setAction(event.target.value)}><option value="">All actions</option><option value="user.created">User created</option><option value="user.role_changed">Role changed</option><option value="user.status_changed">Status changed</option></select></label>
      <label htmlFor="audit-target-type">Target type<input id="audit-target-type" value={targetType} onChange={(event) => setTargetType(event.target.value)} placeholder="All types" /></label>
      <label htmlFor="audit-target-id">Target ID<input id="audit-target-id" inputMode="numeric" value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder="All IDs" /></label>
      <button type="submit">Apply filters</button>
    </form>
    {filterError && <p role="alert" className="form-error">{filterError}</p>}
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : query.data?.items.length ? 'success' : 'empty'} loadingMessage="Loading audit history…" emptyMessage="No audit records match these filters."
      error={<>{query.error instanceof Error ? query.error.message : 'Audit history could not be loaded.'} <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      <div className="table-wrap"><table className="admin-table audit-table"><caption>Administrative audit ledger</caption><thead><tr><th scope="col">When</th><th scope="col">Actor</th><th scope="col">Action</th><th scope="col">Target</th><th scope="col">Before</th><th scope="col">After</th></tr></thead><tbody>
        {query.data?.items.map((record) => <tr key={record.id}><td><time dateTime={record.created_at}>{timestamp.format(new Date(record.created_at))}</time></td><td>Actor {record.actor_user_id}</td><td>{record.action}</td><td>{record.target_type} {record.target_id}</td><td><Facts data={record.before_data} /></td><td><Facts data={record.after_data} /></td></tr>)}
      </tbody></table></div>
    </AsyncState>
    {query.data && <Pagination page={filters.page} pageSize={pageSize} total={query.data.total} onPageChange={(page) => setFilters({ ...filters, page })} />}
  </section>
}
