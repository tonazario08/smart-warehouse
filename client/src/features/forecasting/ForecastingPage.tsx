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
import { forecastError, getForecastStatus, listForecastRuns } from './api'
import type { ForecastMode, ForecastRun, ForecastStatus } from './types'
import '../../shared/styles/management.css'
import './forecasting.css'

export function ForecastingPage() {
  const { token, user } = useAuth()
  const [mode, setMode] = useState<ForecastMode>('operational'), [page, setPage] = useState(1), [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; status: ForecastStatus; runs: Page<ForecastRun> } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const allowedMode = mode === 'research' && !can(user?.role, 'forecast:research:read') ? 'operational' : mode
  const key = `${token}:${user?.id}:${user?.role}:${allowedMode}:${page}:${retry}`
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setFailure(null)
    void Promise.all([getForecastStatus(token, allowedMode), listForecastRuns(token, allowedMode, page)])
      .then(([status, runs]) => { if (active) setLoaded({ key, status, runs }) })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: forecastError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, allowedMode, page, retry, key])
  const current = loaded?.key === key ? loaded : null, error = failure?.key === key ? failure.text : ''
  const choose = (next: ForecastMode) => { setMode(next); setPage(1) }
  return <section className="forecast-page management-workspace">
    <PageHeader title="Dự báo" description="Xem các kết quả dự báo đã được kiểm tra và phạm vi áp dụng." />
    <p><Link to="/forecasting/cold-start">Xem dự báo cho sản phẩm mới</Link></p>
    <div className="forecast-tabs" aria-label="Phạm vi dự báo">
      <Button variant={allowedMode === 'operational' ? 'primary' : 'secondary'} aria-pressed={allowedMode === 'operational'} onClick={() => choose('operational')}>Vận hành</Button>
      {can(user?.role, 'forecast:research:read') && <Button variant={allowedMode === 'research' ? 'primary' : 'secondary'} aria-pressed={allowedMode === 'research'} onClick={() => choose('research')}>Nghiên cứu</Button>}
    </div>
    {allowedMode === 'research' && <FeedbackMessage variant="warning">Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.</FeedbackMessage>}
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !current ? <FeedbackMessage>Đang tải kết quả dự báo...</FeedbackMessage> : <>
      {current.status.state === 'unavailable' && (current.status.reason_code === 'CATALOG_UNAVAILABLE' ? <><FeedbackMessage variant="error">Danh mục dự báo hiện không khả dụng.</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : <EmptyState title="Chưa có kết quả" description={allowedMode === 'operational' && current.status.reason_code === 'NO_ADMITTED_OPERATIONAL_SERIES' ? 'Chưa có dữ liệu vận hành đủ điều kiện để dự báo.' : 'Chưa có kết quả dự báo trong phạm vi này.'} />)}
      {current.status.state === 'failed' && <FeedbackMessage variant="error">Lần tạo kết quả gần nhất không thành công. Vui lòng thử lại sau.</FeedbackMessage>}
      {current.status.latest_failure_code && current.status.state === 'ready' && <FeedbackMessage variant="warning">Một lần tạo kết quả gần đây không thành công; kết quả đã kiểm tra vẫn được hiển thị.</FeedbackMessage>}
      {current.status.latest && <section className="forecast-panel"><h2>Kết quả mới nhất</h2>
        <dl className="forecast-facts"><div><dt>Phiên bản dữ liệu</dt><dd>{current.status.latest.manifest.data_version}</dd></div><div><dt>Chỉ tiêu và đơn vị</dt><dd>{current.status.latest.manifest.target === 'reported_daily_unit_sales' ? 'Đơn vị bán được báo cáo' : 'Đơn vị xuất hàng'} ({current.status.latest.manifest.unit === 'unit' ? 'đơn vị' : current.status.latest.manifest.unit})</dd></div><div><dt>Phạm vi và thời điểm thông tin</dt><dd>{current.status.latest.applicability === 'retrospective' ? 'Tổng hợp toàn công ty, hồi cứu' : 'Kho vận hành'}; {current.status.latest.manifest.training_information_cutoff ? formatDateTime(current.status.latest.manifest.training_information_cutoff) : 'chưa xác định'}</dd></div><div><dt>Ngày gốc</dt><dd>{current.status.latest.manifest.origin_start ?? 'Không có'} đến {current.status.latest.manifest.origin_end ?? 'Không có'}</dd></div></dl>
        {current.status.latest.fixture_label && <Badge>{current.status.latest.fixture_label}</Badge>}
        {current.status.latest.stale === false && <Badge variant="success">Cập nhật cho ngày hiện tại</Badge>}
        {current.status.latest.stale === true && <FeedbackMessage variant="warning">Kết quả không còn cập nhật cho ngày hiện tại. Ngày gốc: {current.status.latest.manifest.origin_end ?? 'không xác định'}.</FeedbackMessage>}
        {current.status.latest.manifest.limitations.length > 0 && <p>Kết quả có giới hạn dữ liệu; xem chi tiết trước khi sử dụng.</p>}
      </section>}
      {current.runs.items.length > 0 && <><DataTable caption="Danh sách kết quả dự báo" rows={current.runs.items} getRowKey={row => row.manifest.run_id} columns={[
        { id: 'run', header: 'Kết quả', render: row => <Link to={'/forecasting/runs/' + row.manifest.run_id}>{row.manifest.run_id}</Link> },
        { id: 'scope', header: 'Phạm vi', render: row => <>{row.applicability === 'retrospective' ? 'Nghiên cứu hồi cứu' : 'Vận hành'} {row.fixture_label && <Badge>{row.fixture_label}</Badge>}</> },
        { id: 'version', header: 'Phiên bản dữ liệu', render: row => row.manifest.data_version },
        { id: 'target', header: 'Chỉ tiêu', render: row => row.manifest.target === 'reported_daily_unit_sales' ? 'Đơn vị bán được báo cáo' : 'Đơn vị xuất hàng' },
        { id: 'cutoff', header: 'Giới hạn thông tin', render: row => row.manifest.training_information_cutoff ? formatDateTime(row.manifest.training_information_cutoff) : 'Không xác định' },
        { id: 'horizons', header: 'Khoảng dự báo', render: row => row.manifest.horizons.map(horizon => `${horizon} ngày`).join(', ') },
        { id: 'time', header: 'Thời điểm tạo', render: row => formatDateTime(row.manifest.generated_at) },
      ]} /><Pagination locale="vi" page={page} pageSize={20} total={current.runs.total} onPageChange={setPage} /></>}
    </>}
  </section>
}
