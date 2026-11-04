import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { can } from '../../shared/lib/permissions'
import { formatDateTime } from '../../shared/lib/formatters'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import type { Page } from '../../types'
import { getReplenishmentStatus, listReplenishmentRuns, replenishmentError, replenishmentReason } from './api'
import type { ReplenishmentMode, ReplenishmentRun, ReplenishmentStatus } from './types'
import '../../shared/styles/management.css'
import './replenishment.css'

export function ReplenishmentPage() {
  const { token, user } = useAuth()
  const [mode, setMode] = useState<ReplenishmentMode>('operational')
  const [page, setPage] = useState(1)
  const [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; status: ReplenishmentStatus; runs: Page<ReplenishmentRun> | null } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const allowedMode = mode === 'research' && !can(user?.role, 'replenishment:research:read') ? 'operational' : mode
  const key = `${token}:${user?.id}:${user?.role}:${allowedMode}:${page}:${retry}`
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setFailure(null)
    void getReplenishmentStatus(token, allowedMode).then(async status => {
      if (!active) return
      const runs = status.state === 'ready' ? await listReplenishmentRuns(token, allowedMode, page) : null
      if (active) setLoaded({ key, status, runs })
    }).catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: replenishmentError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, allowedMode, page, retry, key])
  const current = loaded?.key === key ? loaded : null
  const error = failure?.key === key ? failure.text : ''
  const choose = (next: ReplenishmentMode) => { setMode(next); setPage(1) }
  return <section className="replenishment-page management-workspace">
    <PageHeader title="Bổ sung hàng" description="Xem chính sách và kết quả mô phỏng đã được kiểm tra." />
    <div className="replenishment-tabs" aria-label="Phạm vi bổ sung hàng">
      <Button variant={allowedMode === 'operational' ? 'primary' : 'secondary'} aria-pressed={allowedMode === 'operational'} onClick={() => choose('operational')}>Vận hành</Button>
      {can(user?.role, 'replenishment:research:read') && <Button variant={allowedMode === 'research' ? 'primary' : 'secondary'} aria-pressed={allowedMode === 'research'} onClick={() => choose('research')}>Nghiên cứu</Button>}
    </div>
    <FeedbackMessage variant="warning">{allowedMode === 'research' ? 'Kết quả nghiên cứu hồi cứu dùng giả định, không phải khuyến nghị vận hành.' : 'Kết quả kiểm thử chỉ là kịch bản giả định, không tự đặt hàng.'}</FeedbackMessage>
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !current ? <FeedbackMessage>Đang tải kết quả bổ sung hàng...</FeedbackMessage> : <>
      {current.status.state === 'unavailable' && <EmptyState title="Chưa có kết quả khả dụng" description={replenishmentReason(current.status.reason_code)} />}
      {current.status.state === 'failed' && <><FeedbackMessage variant="error">{replenishmentReason(current.status.reason_code)}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></>}
      {current.runs && current.runs.items.length === 0 && <EmptyState title="Chưa có kết quả" description="Chưa có kết quả trong phạm vi này." />}
      {current.runs && current.runs.items.length > 0 && <><div className="replenishment-scroll" role="region" aria-label="Cuộn danh sách kết quả bổ sung hàng" tabIndex={0}><DataTable caption="Danh sách kết quả bổ sung hàng" rows={current.runs.items} getRowKey={row => row.manifest.run_id} columns={[
        { id: 'run', header: 'Mã kết quả', render: row => <Link to={'/replenishment/runs/' + row.manifest.run_id}>{row.manifest.run_id}</Link> },
        { id: 'scope', header: 'Nguồn và phạm vi', render: row => <>{row.applicability === 'research_scenario' ? 'Nghiên cứu hồi cứu' : 'Kịch bản kiểm thử'} {row.fixture_label && <Badge>{row.fixture_label}</Badge>}</> },
        { id: 'source', header: 'Phiên bản dữ liệu', render: row => row.manifest.data_version },
        { id: 'created', header: 'Thời điểm tạo', render: row => formatDateTime(row.manifest.created_at) },
        { id: 'view', header: 'Chi tiết', render: row => <Link aria-label={'Xem chi tiết ' + row.manifest.run_id} to={'/replenishment/runs/' + row.manifest.run_id}>Xem chi tiết</Link> },
      ]} /></div><Pagination locale="vi" page={page} pageSize={20} total={current.runs.total} onPageChange={setPage} /></>}
    </>}
  </section>
}
