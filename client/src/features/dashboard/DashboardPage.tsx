import { useQuery } from '@tanstack/react-query'
import { AsyncState } from '../../shared/ui/AsyncState'
import { createDashboardApi } from './api'
import { useAuth } from '../auth/useAuth'

export function DashboardPage() {
  const { client } = useAuth()
  const query = useQuery({ queryKey: ['dashboard', 'stats'], queryFn: () => createDashboardApi(client).stats() })

  return <section className="admin-workspace" aria-labelledby="dashboard-heading">
    <header className="admin-heading">
      <div><h2 id="dashboard-heading">Overview</h2><p>Current warehouse status</p></div>
      <button type="button" className="quiet" onClick={() => void query.refetch()} disabled={query.isFetching}>Refresh</button>
    </header>
    <AsyncState status={query.isPending ? 'loading' : query.isError ? 'error' : 'success'}
      loadingMessage={<span role="status" aria-label="Loading warehouse status">Loading warehouse status…</span>}
      error={<><span>{query.error instanceof Error ? query.error.message : 'Warehouse status could not be loaded.'}</span> <button type="button" className="quiet" onClick={() => void query.refetch()}>Retry</button></>}>
      {query.data && <div className="status-board" aria-label="Warehouse status">
        <div><span>Products</span><strong>{query.data.product_count}</strong><small>Registered products</small></div>
        <div><span>Total stock</span><strong>{query.data.total_stock}</strong><small>Units in stock</small></div>
        <div><span>Low-stock balances</span><strong>{query.data.low_stock_count}</strong><small>At or below reorder level</small></div>
      </div>}
    </AsyncState>
  </section>
}
