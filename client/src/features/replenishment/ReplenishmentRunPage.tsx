import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { formatDateTime } from '../../shared/lib/formatters'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { DataTable } from '../../shared/ui/DataTable'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import type { Page } from '../../types'
import { getReplenishmentDays, getReplenishmentRun, replenishmentError } from './api'
import type { Algorithm, Policy, ReplenishmentRun, SimulationDay } from './types'
import '../../shared/styles/management.css'
import './replenishment.css'

const algorithms: Record<Algorithm, string> = { persistence: 'Giữ nguyên gần nhất', seasonal_naive: 'Theo tuần trước', xgboost: 'XGBoost' }
const number = (value: string | number | null) => value === null ? 'Không xác định' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(Number(value))
const money = (value: string | null) => value === null ? 'Không xác định' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(Number(value))
const percent = (value: string | null, reason?: string | null) => {
  if (value !== null) return number(Number(value) * 100) + '%'
  if (reason === 'ZERO_DEMAND') return 'Không xác định: nhu cầu bằng 0'
  if (reason === 'NO_POSITIVE_DEMAND_DAYS') return 'Không xác định: không có ngày nhu cầu dương'
  if (reason === 'NO_EVALUATION_WINDOWS') return 'Không xác định: không có cửa sổ đánh giá'
  return 'Không xác định'
}
const moment = (value: string | null) => value ? formatDateTime(value) : 'Không xác định'

export function ReplenishmentRunPage() {
  const { runId = '' } = useParams()
  const { token, user } = useAuth()
  const [algorithm, setAlgorithm] = useState<Algorithm>('persistence')
  const [horizon, setHorizon] = useState(1)
  const [service, setService] = useState('0.90')
  const [policy, setPolicy] = useState<Policy>('proposed')
  const [page, setPage] = useState(1)
  const [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; run: ReplenishmentRun } | null>(null)
  const [trace, setTrace] = useState<{ key: string; days: Page<SimulationDay> } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const [traceFailure, setTraceFailure] = useState<{ key: string; text: string } | null>(null)
  const key = `${token}:${user?.id}:${user?.role}:${runId}:${retry}`
  const traceKey = `${key}:${algorithm}:${horizon}:${service}:${policy}:${page}`
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setFailure(null)
    if (!/^rrv1-[0-9a-f]{64}$/.test(runId)) { setFailure({ key, text: 'Mã kết quả bổ sung hàng không hợp lệ.' }); return () => { active = false } }
    void getReplenishmentRun(token, runId)
      .then(run => { if (active) setLoaded({ key, run }) })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: replenishmentError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, runId, key])
  const current = loaded?.key === key ? loaded : null, error = failure?.key === key ? failure.text : ''
  useEffect(() => {
    if (!token || !user || !current) return
    let active = true
    setTrace(null); setTraceFailure(null)
    void getReplenishmentDays(token, runId, algorithm, horizon, service, policy, page)
      .then(days => { if (active) setTrace({ key: traceKey, days }) })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setTraceFailure({ key: traceKey, text: replenishmentError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, current, runId, algorithm, horizon, service, policy, page, traceKey])
  const currentTrace = trace?.key === traceKey ? trace.days : null
  const traceError = traceFailure?.key === traceKey ? traceFailure.text : ''
  const calibration = current?.run.calibration, manifest = current?.run.manifest
  const metric = calibration?.interval_metrics.find(item => item.algorithm === algorithm && item.horizon === horizon && item.subset === 'all')
  const entry = calibration?.calibration.entries.find(item => item.algorithm === algorithm && item.horizon === horizon)
  const possible = manifest ? Math.max(0, Math.round((Date.parse(manifest.config.calibration_end) - Date.parse(manifest.config.calibration_start)) / 86400000) - horizon + 1) : 0
  return <section className="replenishment-page management-workspace">
    <PageHeader title="Chi tiết bổ sung hàng" description="Kết quả mô phỏng chỉ dùng để tham khảo." actions={<Link to="/replenishment">Quay lại danh sách</Link>} />
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !current || !manifest ? <FeedbackMessage>Đang tải chi tiết bổ sung hàng...</FeedbackMessage> : <>
      <FeedbackMessage variant="warning">{current.run.applicability === 'research_scenario' ? 'Nghiên cứu hồi cứu dựa trên doanh số tổng hợp và giả định, không chứng minh hiệu quả tại kho thực tế.' : 'Kịch bản kiểm thử tổng hợp, không phải đề xuất đặt hàng vận hành.'}</FeedbackMessage>
      {current.run.fixture_label && <Badge>{current.run.fixture_label}</Badge>}
      {current.run.stale && <FeedbackMessage variant="warning">Dự báo không bao phủ khoảng thời gian được yêu cầu.</FeedbackMessage>}
      <section className="replenishment-panel"><h2>Nguồn và giả định</h2><dl className="replenishment-facts">
        <div><dt>Mã kết quả</dt><dd>{manifest.run_id}</dd></div>
        <div><dt>Phiên bản dữ liệu</dt><dd>{manifest.data_version}</dd></div>
        <div><dt>Kết quả dự báo</dt><dd>{manifest.forecast_run_id}</dd></div>
        <div><dt>Chỉ tiêu</dt><dd>{manifest.target === 'reported_daily_unit_sales' ? 'Đơn vị bán được báo cáo' : 'Đơn vị xuất hàng'}</dd></div>
        <div><dt>Phạm vi nguồn</dt><dd>{manifest.reporting_scope === 'company_aggregate' ? 'Tổng hợp toàn công ty' : 'Kho hàng'}</dd></div>
        <div><dt>Thời điểm tạo</dt><dd>{moment(manifest.created_at)}</dd></div>
        <div><dt>Thời điểm nguồn được tiếp nhận</dt><dd>{moment(manifest.admission_cutoff)}</dd></div>
        <div><dt>Giới hạn thông tin huấn luyện</dt><dd>{moment(manifest.training_information_cutoff)}</dd></div>
        <div><dt>Giới hạn thông tin nguồn</dt><dd>{moment(manifest.knowledge_bound)}</dd></div>
        <div><dt>Múi giờ nguồn</dt><dd>{manifest.source_business_timezone ?? 'Không xác định'}</dd></div>
        <div><dt>Đồng hồ kịch bản</dt><dd>{manifest.scenario_clock_timezone}{manifest.scenario_clock_convention === 'ANALYTICAL_SCENARIO_CLOCK_UTC' ? ' (quy ước phân tích)' : ''}</dd></div>
        <div><dt>Đơn vị</dt><dd>{manifest.unit === 'unit' ? 'đơn vị' : manifest.unit}</dd></div>
        <div><dt>Tồn ban đầu giả định</dt><dd>{number(manifest.config.initial_on_hand)}</dd></div>
        <div><dt>Chi phí đặt hàng giả định</dt><dd>{money(manifest.config.costs.ordering_cost)} {manifest.config.costs.currency}/đơn</dd></div>
        <div><dt>Chi phí lưu kho giả định</dt><dd>{money(manifest.config.costs.holding_cost)} {manifest.config.costs.currency}/đơn vị/năm</dd></div>
        <div><dt>Giai đoạn hiệu chỉnh</dt><dd>{manifest.config.calibration_start} đến trước {manifest.config.calibration_end}</dd></div>
        <div><dt>Giai đoạn đánh giá</dt><dd>{manifest.config.evaluation_start} đến trước {manifest.config.evaluation_end}</dd></div>
        <div><dt>Ngày khởi động</dt><dd>{manifest.config.warmup_days}</dd></div>
        <div><dt>Hàng đang đến ban đầu giả định</dt><dd>{manifest.config.initial_pipeline.length === 0 ? 'Không có' : manifest.config.initial_pipeline.map(order => `${order.quantity} ${order.unit}, dự kiến ${order.due_date}`).join('; ')}</dd></div>
        <div><dt>Đã giữ chỗ giả định</dt><dd>{number(manifest.config.reservations)}</dd></div>
        <div><dt>Đơn tồn đọng giả định</dt><dd>{number(manifest.config.backlog)}</dd></div>
        {current.run.entity && <div><dt>Sản phẩm và kho kiểm thử</dt><dd>{current.run.entity.product_name} ({current.run.entity.sku}), {current.run.entity.warehouse_name} ({current.run.entity.warehouse_code})</dd></div>}
      </dl><p>Chi phí mô phỏng chỉ gồm đặt hàng và lưu kho; không phải tổng chi phí kinh doanh. Chưa xác thực tại kho thực tế.</p></section>
      <div className="replenishment-filters">
        <Select label="Phương pháp" value={algorithm} onChange={e => { if (e.target.value) { setAlgorithm(e.target.value as Algorithm); setPage(1) } }} options={Object.entries(algorithms).map(([value, label]) => ({ value, label }))} />
        <Select label="Thời gian cung ứng" value={horizon} onChange={e => { if (e.target.value) { setHorizon(Number(e.target.value)); setPage(1) } }} options={[{ value: 1, label: '1 ngày' }, { value: 7, label: '7 ngày' }]} />
        <Select label="Mức dịch vụ danh nghĩa" value={service} onChange={e => { if (e.target.value) { setService(e.target.value); setPage(1) } }} options={['0.80','0.90','0.95'].map(value => ({ value, label: number(Number(value)*100) + '%' }))} />
        <Select label="Chính sách" value={policy} onChange={e => { if (e.target.value) { setPolicy(e.target.value as Policy); setPage(1) } }} options={[{ value: 'baseline', label: 'Đối chứng' }, { value: 'proposed', label: 'Có tồn an toàn' }]} />
      </div>
      <section className="replenishment-panel"><h2>Độ bất định</h2><p>Khoảng danh nghĩa 90%; kết quả quan sát có thể khác và không bảo đảm mức phục vụ. Các cửa sổ có thể chồng lấp, không được xem là độc lập.</p><dl className="replenishment-facts"><div><dt>Cửa sổ hiệu chỉnh</dt><dd>{entry?.windows.length ?? 0}</dd></div>
        <div><dt>Cửa sổ bị loại</dt><dd>{entry ? Math.max(0, possible - entry.windows.length) : 'Không xác định'}</dd></div>
        <div><dt>Độ bao phủ quan sát</dt><dd>{metric ? percent(metric.coverage, metric.reason_code) : 'Không xác định'}</dd></div>
        <div><dt>Số cửa sổ đánh giá</dt><dd>{metric?.count ?? 0}</dd></div>
        <div><dt>Độ rộng trung bình</dt><dd>{metric ? number(metric.mean_width) : 'Không xác định'}</dd></div>
        <div><dt>Điểm khoảng</dt><dd>{metric ? number(metric.mean_interval_score) : 'Không xác định'}</dd></div></dl></section>
      <section className="replenishment-panel"><h2>So sánh chính sách</h2><div className="replenishment-scroll" role="region" aria-label="Cuộn bảng so sánh chính sách" tabIndex={0}><DataTable caption="So sánh chính sách bổ sung hàng" rows={current.run.summaries ?? []} getRowKey={row => `${row.case.algorithm}:${row.case.horizon}:${row.case.service}:${row.case.policy}`} columns={[
        { id: 'algorithm', header: 'Phương pháp', render: row => algorithms[row.case.algorithm] },
        { id: 'lead', header: 'Cung ứng', render: row => row.case.horizon + ' ngày' },
        { id: 'service', header: 'Danh nghĩa', render: row => number(Number(row.case.service)*100) + '%' },
        { id: 'policy', header: 'Chính sách', render: row => row.case.policy === 'baseline' ? 'Đối chứng' : 'Có tồn an toàn' },
        { id: 'safety', header: 'Tồn an toàn', render: row => { const q = calibration?.calibration.entries.find(item => item.algorithm === row.case.algorithm && item.horizon === row.case.horizon)?.quantiles[row.case.service]; return row.case.policy === 'baseline' ? '0' : q === undefined ? 'Không xác định' : number(Math.max(0, Number(q))) } },
        { id: 'rop', header: 'Điểm đặt hàng', render: row => `${number(row.rop_min)}–${number(row.rop_max)}` },
        { id: 'q', header: 'Lượng đặt EOQ', render: () => calibration?.eoq.quantity ?? 'Không xác định' },
        { id: 'lost', header: 'Thiếu hàng', render: row => number(row.summary.lost) },
        { id: 'fill', header: 'Tỷ lệ đáp ứng', render: row => percent(row.summary.fill_rate, row.summary.fill_reason) },
        { id: 'stock', header: 'Tồn trung bình', render: row => number(row.summary.average_on_hand) },
        { id: 'cost', header: 'Chi phí một phần (VND)', render: row => money(row.summary.partial_cost) },
      ]} /></div></section>
      <section className="replenishment-panel"><h2>Diễn biến theo ngày</h2>
      {traceError ? <><FeedbackMessage variant="error">{traceError}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !currentTrace ? <FeedbackMessage>Đang tải diễn biến theo ngày...</FeedbackMessage> : <><div className="replenishment-scroll" role="region" aria-label="Cuộn bảng diễn biến theo ngày" tabIndex={0}><DataTable caption="Diễn biến tồn và đơn hàng theo ngày" rows={currentTrace.items} getRowKey={row => row.day} columns={[
        { id: 'day', header: 'Ngày', render: row => row.day },
        { id: 'warmup', header: 'Giai đoạn', render: row => row.warmup ? 'Khởi động' : 'Đánh giá' },
        { id: 'forecast', header: 'Dự báo cộng dồn', render: row => number(row.forecast_mean) },
        { id: 'rop', header: 'Điểm đặt', render: row => number(row.reorder_point) },
        { id: 'order', header: 'Đặt hàng', render: row => number(row.ordered) },
        { id: 'due', header: 'Ngày nhận dự kiến', render: row => row.due_date ?? 'Không có' },
        { id: 'received', header: 'Đã nhận', render: row => number(row.received) },
        { id: 'demand', header: 'Nhu cầu mô phỏng', render: row => number(row.demand) },
        { id: 'lost', header: 'Thiếu', render: row => number(row.lost) },
        { id: 'end', header: 'Tồn cuối ngày', render: row => number(row.on_hand_end) },
        { id: 'pending', header: 'Đang đến', render: row => number(row.pipeline_end) },
      ]} /></div><Pagination locale="vi" page={page} pageSize={20} total={currentTrace.total} onPageChange={setPage} /></>}</section>
    </>}
  </section>
}
