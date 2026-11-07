import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { formatDateTime } from '../../shared/lib/formatters'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { getAlerts, getStatus } from './api'
import { statusLabels } from './types'
import type { AlertPage, StatusResponse } from './types'
import '../../shared/styles/management.css'
import './anomalies.css'

export function AnomaliesPage() {
  const { token, user } = useAuth()
  const [page, setPage] = useState(1), [filter, setFilter] = useState(''), [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; status: StatusResponse; alerts: AlertPage | null } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const key = `${token}:${user?.id}:${user?.role}:${page}:${filter}:${retry}`
  const keyRef = useRef(key)
  keyRef.current = key
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setFailure(null)
    void getStatus(token).then(async status => {
      if (!active || keyRef.current !== key) return
      const alerts = status.state === 'available' ? await getAlerts(token, page, filter) : null
      if (active && keyRef.current === key) setLoaded({ key, status, alerts })
    }).catch((cause: unknown) => { if (active && keyRef.current === key && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: 'Không thể tải cảnh báo. Vui lòng thử lại.' }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, page, filter, retry, key])
  const current = loaded?.key === key ? loaded : null
  const error = failure?.key === key ? failure.text : ''
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Bất thường" description="Rà soát các bản ghi có đặc trưng khác thường." />
    <FeedbackMessage variant="warning">Dữ liệu kiểm thử tổng hợp. Hiệu quả trên dữ liệu thực chưa được xác minh.</FeedbackMessage>
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(n => n + 1)}>Thử lại</Button></> : !current ? <FeedbackMessage>Đang tải cảnh báo...</FeedbackMessage> : current.status.state === 'unavailable' ? <EmptyState title="Chưa có cảnh báo khả dụng" description="Chưa có kết quả kiểm thử được nhập." /> : <>
      <Select label="Trạng thái đánh giá" value={filter} placeholder="Tất cả trạng thái" onChange={e => { setFilter(e.target.value); setPage(1) }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
      {current.alerts?.items.length ? <><div className="anomalies-scroll" role="region" aria-label="Cuộn danh sách cảnh báo" tabIndex={0}><DataTable caption="Danh sách cảnh báo" rows={current.alerts.items} getRowKey={row => row.alert_id} columns={[
        { id: 'id', header: 'Mã cảnh báo', render: row => <Link to={'/anomalies/' + row.alert_id}>{row.alert_id}</Link> },
        { id: 'date', header: 'Thời điểm xuất', render: row => formatDateTime(row.occurred_at) },
        { id: 'score', header: 'Điểm bất thường', render: row => row.score.toFixed(4) },
        { id: 'status', header: 'Trạng thái', render: row => <Badge>{statusLabels[row.review_status]}</Badge> },
      ]} /></div><Pagination locale="vi" page={page} pageSize={20} total={current.alerts.total} onPageChange={setPage} /></> : <EmptyState title="Không có cảnh báo" description="Không có bản ghi phù hợp với bộ lọc." />}
    </>}
  </section>
}
