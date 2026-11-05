import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { can } from '../../shared/lib/permissions'
import { formatDateTime, formatNumber } from '../../shared/lib/formatters'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { EmptyState } from '../../shared/ui/EmptyState'
import { DataTable } from '../../shared/ui/DataTable'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { coldStartError, getColdStartRun, getColdStartStatus } from './coldStartApi'
import type { ColdStartRun, ColdStartStatus } from './coldStartApi'
import '../../shared/styles/management.css'
import './forecasting.css'

type Loaded = { key: string; status: ColdStartStatus; run: ColdStartRun | null }
const number = (value: number | null) => value === null ? 'Không đủ dữ liệu' : formatNumber(value, 2)
const percent = (value: number | null) => value === null ? 'Không đủ dữ liệu' : `${number(value * 100)}%`
const sources = { cluster: 'Cùng cụm', category: 'Cùng danh mục', all_train: 'Toàn bộ tập tham chiếu', unavailable: 'Không đủ dữ liệu' } as const

export function ColdStartPage() {
  const { token, user } = useAuth()
  const allowed = can(user?.role, 'forecast:read')
  const [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [failure, setFailure] = useState<{ key: string; text: string } | null>(null)
  const key = `${token}:${user?.id}:${user?.role}:${retry}`
  const currentKey = useRef(key)
  useLayoutEffect(() => { currentKey.current = key }, [key])
  useEffect(() => {
    if (!token || !user || !allowed) return
    let active = true
    setLoaded(null); setFailure(null)
    void (async () => {
      try {
        const status = await getColdStartStatus(token)
        if (!active || currentKey.current !== key) return
        const run = status.state === 'ready' && status.latest_run_id ? await getColdStartRun(token, status.latest_run_id) : null
        if (active && currentKey.current === key) setLoaded({ key, status, run })
      } catch (cause: unknown) {
        if (active && currentKey.current === key && !(cause instanceof ApiError && cause.staleSession)) setFailure({ key, text: coldStartError(cause) })
      }
    })()
    return () => { active = false }
  }, [token, user?.id, user?.role, allowed, retry, key])
  const current = allowed && loaded?.key === key ? loaded : null
  const error = allowed && failure?.key === key ? failure.text : ''
  const report = current?.run && !current.run.stale ? current.run.report : null
  return <section className="forecast-page management-workspace">
    <PageHeader title="Dự báo cho sản phẩm mới" description="Tham khảo kết quả thử nghiệm khi sản phẩm chưa có đủ lịch sử." />
    {allowed && <FeedbackMessage variant="warning">Chưa sẵn sàng cho vận hành.</FeedbackMessage>}
    {!allowed ? <FeedbackMessage variant="error">Bạn không có quyền xem báo cáo này.</FeedbackMessage> : error ? <>
      <FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button>
    </> : !current ? <FeedbackMessage>Đang tải báo cáo...</FeedbackMessage> : <>
      {current.status.state === 'unavailable' && <EmptyState title="Chưa có báo cáo" description={current.status.reason_code === 'NO_ELIGIBLE_PREDICTIONS' || current.status.reason_code === 'NO_ELIGIBLE_TRAINING_SNAPSHOTS' ? 'Chưa đủ dữ liệu tham chiếu để tạo dự báo thử nghiệm.' : 'Chưa có báo cáo thử nghiệm khả dụng.'} />}
      {current.status.state === 'failed' && <FeedbackMessage variant="error">Lần tạo báo cáo gần nhất không thành công. Vui lòng thử lại sau.</FeedbackMessage>}
      {(current.status.state === 'stale' || current.run?.stale) && <FeedbackMessage variant="warning">Báo cáo đã quá hạn hoặc có thời điểm tạo chưa hợp lệ. Vui lòng chờ báo cáo mới.</FeedbackMessage>}
      {current.status.state === 'ready' && !current.run && <FeedbackMessage variant="error">Không tìm thấy báo cáo mới nhất. Vui lòng thử lại.</FeedbackMessage>}
      {report && <>
        <section className="forecast-panel">
          <Badge>{report.fixture_label}</Badge>
          <h2>Kết quả thử nghiệm hồi cứu</h2>
          <p>Kết quả chưa được xác minh trên nguồn nhiều sản phẩm thực tế.</p>
          <dl className="forecast-facts">
            <div><dt>Chỉ tiêu</dt><dd>Đơn vị xuất hàng ({report.unit})</dd></div>
            <div><dt>Phạm vi</dt><dd>Dữ liệu kiểm thử tại một kho</dd></div>
            <div><dt>Tham chiếu</dt><dd>{number(report.reference_population)} sản phẩm trong tập huấn luyện</dd></div>
            <div><dt>Thông tin huấn luyện đến</dt><dd>{formatDateTime(report.train_cutoff)}</dd></div>
            <div><dt>Thông tin chọn mô hình đến</dt><dd>{formatDateTime(report.validation_cutoff)}</dd></div>
            <div><dt>Số cụm đã chọn</dt><dd>{number(report.selected_k)}</dd></div>
            <div><dt>Ngày cuối tập giữ lại</dt><dd>{report.holdout_end}</dd></div>
            <div><dt>Thời điểm tạo</dt><dd>{formatDateTime(report.created_at)}</dd></div>
          </dl>
          <p>Độ tin cậy là nhãn định tính theo nhóm tham chiếu, không phải khoảng xác suất.</p>
        </section>
        <section className="forecast-panel"><h2>So sánh trên tập giữ lại</h2>
          <p>MAE và WAPE được tính trên các mẫu có đủ dự báo, mốc so sánh và giá trị thực. WAPE không có khi tổng giá trị thực bằng 0.</p>
          <DataTable caption="Kết quả theo khoảng dự báo" rows={(['1', '7'] as const).map(horizon => ({ horizon, ...report.metrics[horizon] }))} getRowKey={row => row.horizon} columns={[
            { id: 'h', header: 'Khoảng dự báo', render: row => `${row.horizon} ngày` },
            { id: 'samples', header: 'Tổng mẫu', render: row => number(row.samples) },
            { id: 'predicted', header: 'Có dự báo', render: row => number(row.predicted) },
            { id: 'baseline', header: 'Có mốc so sánh', render: row => number(row.baseline_predicted) },
            { id: 'actual', header: 'Có giá trị thực', render: row => number(row.actual) },
            { id: 'compared', header: 'Mẫu so sánh', render: row => number(row.compared) },
            { id: 'categories', header: 'Số danh mục', render: row => number(row.category_count) },
            { id: 'mae', header: 'MAE', render: row => number(row.mae) },
            { id: 'baseline-mae', header: 'MAE mốc so sánh', render: row => number(row.baseline_mae) },
            { id: 'wape', header: 'WAPE', render: row => percent(row.wape) },
            { id: 'baseline-wape', header: 'WAPE mốc so sánh', render: row => percent(row.baseline_wape) },
          ]} />
        </section>
        <section className="forecast-panel"><h2>Mẫu dự báo</h2>
          <p>Mẫu minh họa từ dữ liệu kiểm thử, không dùng làm dự báo vận hành.</p>
          <DataTable caption="Mẫu dự báo sản phẩm mới" rows={report.samples.map((sample, index) => ({ ...sample, index }))} getRowKey={row => row.index} columns={[
            { id: 'origin', header: 'Ngày gốc', render: row => row.origin },
            { id: 'h', header: 'Khoảng dự báo', render: row => `${row.horizon} ngày` },
            { id: 'prediction', header: 'Dự báo', render: row => number(row.prediction) },
            { id: 'baseline', header: 'Mốc so sánh', render: row => number(row.baseline) },
            { id: 'count', header: 'Số tham chiếu', render: row => number(row.reference_count) },
            { id: 'source', header: 'Nhóm tham chiếu', render: row => sources[row.confidence] },
          ]} />
        </section>
      </>}
    </>}
  </section>
}
