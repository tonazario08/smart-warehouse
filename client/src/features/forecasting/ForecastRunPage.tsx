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
import { forecastError, getForecastPredictions, getForecastRun } from './api'
import type { Algorithm, ForecastRun, Prediction } from './types'
import '../../shared/styles/management.css'
import './forecasting.css'

const algorithms: Record<Algorithm, string> = { persistence: 'Giữ nguyên gần nhất', seasonal_naive: 'Theo tuần trước', xgboost: 'XGBoost' }
const limitations: Record<string, string> = { AVAILABILITY_UNKNOWN: 'Chưa xác định khả năng cung ứng.', CENSORING_UNKNOWN: 'Chưa xác định ảnh hưởng của dữ liệu bị che khuất.', COMPANY_AGGREGATE: 'Dữ liệu tổng hợp toàn công ty.', CONDITIONAL_NONNEGATIVE_TARGET: 'Chỉ xét giá trị mục tiêu không âm đủ điều kiện.', HISTORICAL_AS_OF_NOT_VERIFIED: 'Chưa xác minh dữ liệu có sẵn tại thời điểm lịch sử.', HOLDOUT_QUALITY_INSPECTED: 'Chất lượng dữ liệu kiểm tra đã được xem trước.', NOT_LATENT_DEMAND: 'Không đo nhu cầu tiềm ẩn.', NO_FULFILLMENT_CLAIM: 'Không khẳng định số lượng đơn hàng đã đáp ứng.', REPORTED_SALES_ONLY: 'Chỉ sử dụng doanh số được báo cáo.', RETROSPECTIVE_FINAL_VINTAGE: 'Sử dụng dữ liệu cuối cùng để nghiên cứu hồi cứu.', SOURCE_TIMEZONE_UNKNOWN: 'Chưa xác định múi giờ nguồn.' }
const number = (value: number | null) => value === null ? 'Không xác định' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(value)
const quantity = (value: number, unit: string) => `${number(value)} ${unit === 'unit' ? 'đơn vị' : unit}`
export function ForecastRunPage() {
  const { runId = '' } = useParams(), { token, user } = useAuth()
  const [horizon, setHorizon] = useState(1), [algorithm, setAlgorithm] = useState<Algorithm>('persistence'), [page, setPage] = useState(1), [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; run: ForecastRun; predictions: Page<Prediction> } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const key = `${token}:${user?.id}:${user?.role}:${runId}:${horizon}:${algorithm}:${page}:${retry}`
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setFailure(null)
    if (!/^frv1-[0-9a-f]{64}$/.test(runId)) { setFailure({ key, text: 'Mã kết quả dự báo không hợp lệ.' }); return () => { active = false } }
    void Promise.all([getForecastRun(token, runId), getForecastPredictions(token, runId, horizon, algorithm, page)])
      .then(([run, predictions]) => { if (active) setLoaded({ key, run, predictions }) })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: forecastError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, runId, horizon, algorithm, page, retry, key])
  const current = loaded?.key === key ? loaded : null, error = failure?.key === key ? failure.text : ''
  const metric = current?.run.metrics?.[`${algorithm}:${horizon}`]
  return <section className="forecast-page management-workspace">
    <PageHeader title="Chi tiết dự báo" description="Kiểm tra phạm vi, giới hạn và các giá trị của kết quả." />
    <Link to="/forecasting">Về danh sách dự báo</Link>
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !current ? <FeedbackMessage>Đang tải kết quả dự báo...</FeedbackMessage> : <>
      {current.run.applicability === 'retrospective' && <FeedbackMessage variant="warning">Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.</FeedbackMessage>}
      {current.run.stale === true && <FeedbackMessage variant="warning">Kết quả vận hành không còn cập nhật cho ngày hiện tại. Ngày gốc: {current.run.manifest.origin_end ?? 'không xác định'}.</FeedbackMessage>}
      {current.run.fixture_label && <Badge>{current.run.fixture_label}</Badge>}
      <section className="forecast-panel"><h2>Thông tin kết quả</h2><dl className="forecast-facts">
        <div><dt>Mã kết quả</dt><dd>{current.run.manifest.run_id}</dd></div><div><dt>Phiên bản dữ liệu</dt><dd>{current.run.manifest.data_version}</dd></div>
        <div><dt>Chỉ tiêu</dt><dd>{current.run.manifest.target === 'reported_daily_unit_sales' ? 'Đơn vị bán được báo cáo' : 'Đơn vị xuất hàng'}</dd></div><div><dt>Đơn vị</dt><dd>{current.run.manifest.unit === 'unit' ? 'đơn vị' : current.run.manifest.unit}</dd></div>
        <div><dt>Phạm vi</dt><dd>{current.run.applicability === 'retrospective' ? 'Tổng hợp toàn công ty, hồi cứu' : 'Kho vận hành'}</dd></div><div><dt>Ngày gốc</dt><dd>{current.run.manifest.origin_start ?? 'Không có'} đến {current.run.manifest.origin_end ?? 'Không có'}</dd></div>
        <div><dt>Ngày huấn luyện cuối</dt><dd>{current.run.manifest.trained_through}</dd></div><div><dt>Giới hạn thông tin</dt><dd>{current.run.manifest.training_information_cutoff ? formatDateTime(current.run.manifest.training_information_cutoff) : 'Không xác định'}</dd></div>
        <div><dt>Thời điểm tạo</dt><dd>{formatDateTime(current.run.manifest.generated_at)}</dd></div>
        {current.run.entity && <div><dt>Sản phẩm và kho</dt><dd>{current.run.entity.product_name} ({current.run.entity.sku}), {current.run.entity.warehouse_name} ({current.run.entity.warehouse_code})</dd></div>}
      </dl><h3>Giới hạn</h3>{current.run.manifest.limitations.length ? <ul>{current.run.manifest.limitations.map(item => <li key={item}>{limitations[item] ?? 'Có giới hạn dữ liệu chưa được diễn giải.'}</li>)}</ul> : <p>Không có giới hạn bổ sung.</p>}</section>
      <div className="forecast-filters"><Select label="Khoảng dự báo" value={horizon} onChange={event => { if (event.target.value) { setHorizon(Number(event.target.value)); setPage(1) } }} options={[{ value: 1, label: '1 ngày' }, { value: 7, label: '7 ngày' }]} /><Select label="Phương pháp" value={algorithm} onChange={event => { if (event.target.value) { setAlgorithm(event.target.value as Algorithm); setPage(1) } }} options={Object.entries(algorithms).map(([value, label]) => ({ value, label }))} /></div>
      {current.run.metrics && <section className="forecast-panel"><h2>Độ sai lệch</h2>{metric ? <DataTable caption="Chỉ số sai lệch" rows={[metric]} getRowKey={() => 'metric'} columns={[
        { id: 'count', header: 'Số điểm', render: row => row.count }, { id: 'origins', header: 'Số ngày gốc', render: row => row.origin_count }, { id: 'mae', header: 'Sai lệch tuyệt đối trung bình', render: row => number(row.mae) }, { id: 'wape', header: 'WAPE', render: row => row.wape === null ? row.reason === 'NO_ELIGIBLE_WINDOWS' ? 'Không xác định: không có cửa sổ hợp lệ' : row.wape_reason === 'ZERO_ACTUAL_TOTAL' ? 'Không xác định: tổng thực tế bằng 0' : 'Không xác định' : number(row.wape * 100) + '%' }, { id: 'total', header: 'Sai lệch tổng theo ngày gốc', render: row => number(row.origin_total_mae) },
      ]} /> : <p>Không có chỉ số cho lựa chọn này.</p>}</section>}
      <section className="forecast-panel"><h2>Giá trị dự báo</h2><DataTable caption="Các giá trị dự báo" rows={current.predictions.items} getRowKey={row => `${row.series_key}:${row.origin}:${row.lead}`} columns={[
        { id: 'origin', header: 'Ngày gốc', render: row => row.origin }, { id: 'target', header: 'Ngày dự báo', render: row => row.target_date }, { id: 'lead', header: 'Ngày thứ', render: row => row.lead }, { id: 'prediction', header: 'Dự báo', render: row => quantity(row.prediction, row.unit) }, { id: 'actual', header: 'Thực tế', render: row => row.actual === null ? 'Chưa có' : quantity(row.actual, row.unit) },
      ]} /><Pagination locale="vi" page={page} pageSize={20} total={current.predictions.total} onPageChange={setPage} /></section>
    </>}
  </section>
}
