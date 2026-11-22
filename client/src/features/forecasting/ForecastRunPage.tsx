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
import { OpenDemandPanel } from '../orderAnalytics/OrderAnalyticsPanels'
import { analyticsTarget } from '../orderAnalytics/types'
import { ForecastChartWindow } from './ForecastChartWindow'
import { forecastSourceLabel } from './forecastSourceLabel'
import { ForecastIdentifier } from './ForecastIdentifier'
import { forecastError, getForecastPredictions, getForecastRun } from './api'
import type { Algorithm, ForecastRun, Prediction } from './types'
import '../../shared/styles/management.css'
import './forecasting.css'

const algorithms: Record<Algorithm, string> = { persistence: 'Giữ nguyên gần nhất (đối chứng)', seasonal_naive: 'Theo tuần trước', xgboost: 'XGBoost' }
const limitations: Record<string, string> = { AVAILABILITY_UNKNOWN: 'Chưa xác định khả năng cung ứng.', CENSORING_UNKNOWN: 'Chưa xác định ảnh hưởng của dữ liệu bị che khuất.', COMPANY_AGGREGATE: 'Dữ liệu tổng hợp toàn công ty.', CONDITIONAL_NONNEGATIVE_TARGET: 'Chỉ xét giá trị mục tiêu không âm đủ điều kiện.', HISTORICAL_AS_OF_NOT_VERIFIED: 'Chưa xác minh dữ liệu có sẵn tại thời điểm lịch sử.', HOLDOUT_QUALITY_INSPECTED: 'Chất lượng dữ liệu kiểm tra đã được xem trước.', NOT_LATENT_DEMAND: 'Không đo nhu cầu tiềm ẩn.', NO_FULFILLMENT_CLAIM: 'Không khẳng định số lượng đơn hàng đã đáp ứng.', REPORTED_SALES_ONLY: 'Chỉ sử dụng doanh số được báo cáo.', RETROSPECTIVE_FINAL_VINTAGE: 'Sử dụng dữ liệu cuối cùng để nghiên cứu hồi cứu.', SOURCE_TIMEZONE_UNKNOWN: 'Chưa xác định múi giờ nguồn.' }
const number = (value: number | null) => value === null ? 'Không xác định' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(value)
const quantity = (value: number, unit: string) => `${number(value)} ${unit === 'unit' ? 'đơn vị' : unit}`
const verifiedConstantPilot = {
  run: 'frv1-96f99dca2c706b19e144b975e591724c777b096001c537e3288b06320d73c472',
  version: 'ddv1-2357daebb159601338bd97e41362bb21dfe93c3abd72252998e51e87144f8348',
}
function entityLabel(name: string, code: string) {
  const normalize = (value: string) => value.trim().normalize('NFC').toLocaleLowerCase('vi-VN')
  return !name.trim() ? code : !code.trim() || normalize(name) === normalize(code) ? name.trim() : `${name.trim()} (${code.trim()})`
}

export function ForecastRunPage() {
  const { runId = '' } = useParams(), { token, user } = useAuth()
  const [horizon, setHorizon] = useState(1), [algorithm, setAlgorithm] = useState<Algorithm>('persistence'), [page, setPage] = useState(1), [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; run: ForecastRun } | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const [tableLoaded, setTableLoaded] = useState<{ key: string; predictions: Page<Prediction> } | null>(null)
  const [tableFailure, setTableFailure] = useState<{ key: string; text: string } | null>(null)
  const [tableRetry, setTableRetry] = useState(0)
  const key = JSON.stringify([token, user?.id, user?.role, runId, retry])
  const tableKey = JSON.stringify([key, horizon, algorithm, page, tableRetry])
  useEffect(() => {
    if (!token || !user) return
    let active = true
    if (!/^frv1-[0-9a-f]{64}$/.test(runId)) { setFailure({ key, text: 'Mã kết quả dự báo không hợp lệ.' }); return () => { active = false } }
    void getForecastRun(token, runId)
      .then(run => { if (active) setLoaded({ key, run }) })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: forecastError(cause) }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, runId, key])
  const current = loaded?.key === key ? loaded : null, error = failure?.key === key ? failure.text : ''
  useEffect(() => {
    if (!token || !current || error) return
    let active = true
    void getForecastPredictions(token, runId, horizon, algorithm, page)
      .then(predictions => { if (active) setTableLoaded({ key: tableKey, predictions }) })
      .catch((cause: unknown) => {
        if (active && !(cause instanceof ApiError && cause.staleSession)) setTableFailure({ key: tableKey, text: forecastError(cause) })
      })
    return () => { active = false }
  }, [token, current, error, runId, horizon, algorithm, page, tableKey])
  const predictions = tableLoaded?.key === tableKey ? tableLoaded.predictions : null
  const tableError = tableFailure?.key === tableKey ? tableFailure.text : ''
  const metric = current?.run.metrics?.[`${algorithm}:${horizon}`]
  const fixtureZero = current?.run.manifest.dataset_class === 'fixture' && metric?.wape === 0
  const constantPilot = fixtureZero && algorithm === 'persistence' && current?.run.manifest.run_id === verifiedConstantPilot.run
    && current.run.manifest.data_version === verifiedConstantPilot.version
  const target = current?.run.applicability === 'operational' ? analyticsTarget(current.run.binding) : null
  return <section className="forecast-page management-workspace">
    <PageHeader title="Chi tiết dự báo" description="Kiểm tra phạm vi, giới hạn và các giá trị của kết quả." />
    <Link to="/forecasting">Về danh sách dự báo</Link>
    {token && user && /^frv1-[0-9a-f]{64}$/.test(runId) && <div className="forecast-filters"><Select label="Khoảng dự báo" value={horizon} onChange={event => { if (event.target.value) { setHorizon(Number(event.target.value)); setPage(1) } }} options={[{ value: 1, label: '1 ngày' }, { value: 7, label: '7 ngày' }]} /><Select label="Phương pháp" value={algorithm} onChange={event => { if (event.target.value) { setAlgorithm(event.target.value as Algorithm); setPage(1) } }} options={Object.entries(algorithms).map(([value, label]) => ({ value, label }))} /></div>}
    {error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : !current ? <FeedbackMessage>Đang tải kết quả dự báo...</FeedbackMessage> : <>
      {current.run.applicability === 'retrospective' && <FeedbackMessage variant="warning">Kết quả nghiên cứu hồi cứu, không phải dự báo tồn kho vận hành.</FeedbackMessage>}
      {forecastSourceLabel(current.run) === 'Vận hành' && current.run.stale === true && <FeedbackMessage variant="warning">Kết quả vận hành không còn cập nhật cho ngày hiện tại. Ngày gốc: {current.run.manifest.origin_end ?? 'không xác định'}.</FeedbackMessage>}
      <Badge variant={forecastSourceLabel(current.run) === 'Mô phỏng kiểm thử' ? 'warning' : 'neutral'}>{forecastSourceLabel(current.run)}</Badge>
      {current.run.fixture_label && <p>{current.run.fixture_label}</p>}
      {forecastSourceLabel(current.run) === 'Mô phỏng kiểm thử' && <p>Kết quả của kịch bản kiểm thử, không phản ánh dự báo hay độ mới của kho thật.</p>}
      {target && token && <OpenDemandPanel token={token} context={key} target={target} />}
      <section className="forecast-panel"><h2>Thông tin kết quả</h2><dl className="forecast-facts">
        <div><dt>Mã kết quả</dt><dd><ForecastIdentifier value={current.run.manifest.run_id} label="Mã kết quả" /></dd></div>
        <div><dt>Phiên bản dữ liệu</dt><dd><ForecastIdentifier value={current.run.manifest.data_version} label="Phiên bản dữ liệu" /></dd></div>
        <div><dt>Chỉ tiêu</dt><dd>{current.run.manifest.target === 'reported_daily_unit_sales' ? 'Đơn vị bán được báo cáo' : 'Đơn vị xuất hàng'}</dd></div><div><dt>Đơn vị</dt><dd>{current.run.manifest.unit === 'unit' ? 'đơn vị' : current.run.manifest.unit}</dd></div>
        <div><dt>Phạm vi</dt><dd>{current.run.applicability === 'retrospective' ? 'Tổng hợp toàn công ty, hồi cứu' : forecastSourceLabel(current.run) === 'Mô phỏng kiểm thử' ? 'Kịch bản mô phỏng' : 'Kho vận hành'}</dd></div><div><dt>Ngày gốc</dt><dd>{current.run.manifest.origin_start ?? 'Không có'} đến {current.run.manifest.origin_end ?? 'Không có'}</dd></div>
        <div><dt>Ngày huấn luyện cuối</dt><dd>{current.run.manifest.trained_through}</dd></div><div><dt>Giới hạn thông tin</dt><dd>{current.run.manifest.training_information_cutoff ? formatDateTime(current.run.manifest.training_information_cutoff) : 'Không xác định'}</dd></div>
        <div><dt>Thời điểm tạo</dt><dd>{formatDateTime(current.run.manifest.generated_at)}</dd></div>
        {current.run.entity && <>
          <div><dt>Sản phẩm</dt><dd>{entityLabel(current.run.entity.product_name, current.run.entity.sku)}</dd></div>
          <div><dt>Kho</dt><dd>{entityLabel(current.run.entity.warehouse_name, current.run.entity.warehouse_code)}</dd></div>
        </>}
      </dl>
      <details className="forecast-limitations">
        <summary>Lưu ý phạm vi mô hình ({current.run.manifest.limitations.length})</summary>
        {current.run.manifest.limitations.length ? <ul>{current.run.manifest.limitations.map(item => <li key={item}>{limitations[item] ?? 'Có giới hạn dữ liệu chưa được diễn giải.'}</li>)}</ul> : <p>Không có giới hạn bổ sung.</p>}
      </details></section>

      {algorithm === 'persistence' && <p className="forecast-explanation">Đối chứng đơn giản: lấy giá trị thực tế gần nhất đã biết để dự báo.</p>}
      {current.run.metrics && <section className="forecast-panel"><h2>Độ sai lệch</h2>{metric ? <>
        <p className="forecast-explanation">Số điểm là số cặp dự báo và thực tế hợp lệ trong tập đánh giá. Sai lệch tuyệt đối trung bình (MAE) dùng cùng đơn vị với lượng xuất hoặc doanh số. WAPE lấy tổng độ lệch tuyệt đối chia cho tổng thực tế của tập đánh giá; không phải tỷ lệ dự báo đúng và không được tính lại theo cửa sổ biểu đồ.</p>
        {fixtureZero && <p className="forecast-metric-note">{constantPilot
          ? 'Dữ liệu kiểm thử luồng: WAPE = 0% do chuỗi hằng 2 đơn vị mỗi ngày và phương pháp giữ nguyên giá trị gần nhất. Không chứng minh độ chính xác ngoài thực tế.'
          : 'Dữ liệu kiểm thử: WAPE = 0% trên tập đánh giá này không chứng minh độ chính xác ngoài thực tế.'}</p>}
        <DataTable caption="Chỉ số sai lệch" rows={[metric]} getRowKey={() => 'metric'} columns={[
        { id: 'count', header: 'Số điểm', render: row => row.count }, { id: 'origins', header: 'Số ngày gốc', render: row => row.origin_count }, { id: 'mae', header: 'Sai lệch tuyệt đối trung bình', render: row => number(row.mae) }, { id: 'wape', header: 'WAPE', render: row => row.wape === null ? row.reason === 'NO_ELIGIBLE_WINDOWS' ? 'Không xác định: không có cửa sổ hợp lệ' : row.wape_reason === 'ZERO_ACTUAL_TOTAL' ? 'Không xác định: tổng thực tế bằng 0' : 'Không xác định' : number(row.wape * 100) + '%' }, { id: 'total', header: 'Sai lệch tổng theo ngày gốc', render: row => number(row.origin_total_mae) },
      ]} /></> : <p>Không có chỉ số cho lựa chọn này.</p>}</section>}
      <section className="forecast-panel"><h2>Giá trị dự báo</h2>
        {token && <ForecastChartWindow key={key} token={token} context={key} runId={runId}
          horizon={horizon} algorithm={algorithm} algorithmLabel={algorithms[algorithm]} unit={current.run.manifest.unit} />}
        {tableError ? <><FeedbackMessage variant="error">{tableError}</FeedbackMessage>
          <Button variant="secondary" onClick={() => setTableRetry(value => value + 1)}>Thử tải lại bảng chi tiết</Button></>
          : !predictions ? <p role="status">Đang tải bảng chi tiết dự báo…</p> : <>
        <div className="forecast-detail-scroll" role="region" aria-label="Cuộn bảng các giá trị dự báo" tabIndex={0}>
        <DataTable caption="Các giá trị dự báo" rows={predictions.items} getRowKey={row => `${row.series_key}:${row.origin}:${row.lead}`} columns={[
        { id: 'origin', header: 'Ngày gốc', render: row => row.origin }, { id: 'target', header: 'Ngày dự báo', render: row => row.target_date }, { id: 'lead', header: 'Ngày thứ', render: row => row.lead }, { id: 'prediction', header: 'Dự báo', render: row => quantity(row.prediction, row.unit) }, { id: 'actual', header: 'Thực tế', render: row => row.actual === null ? 'Chưa có' : quantity(row.actual, row.unit) },
      ]} /></div><Pagination locale="vi" page={page} pageSize={20} total={predictions.total} onPageChange={setPage} /></>}</section>
    </>}
  </section>
}
