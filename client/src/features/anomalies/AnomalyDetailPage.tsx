import { AnomalyOutboundLink } from './AnomalyOutboundPage'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { can } from '../../shared/lib/permissions'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { getAlert, getReviews, submitReview } from './api'
import { featureLabels, partitionLabels, reasons, statusLabels } from './types'
import { attribution, formatVietnamTime, number, readFeatures, readScoreComparison } from './alertReadability'
import type { Detail, Review, ReviewRequest } from './types'
import '../../shared/styles/management.css'
import './anomalies.css'

const signedDecimal = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 8, signDisplay: 'exceptZero' })
const signedScientific = new Intl.NumberFormat('vi-VN', { notation: 'scientific', maximumSignificantDigits: 3, signDisplay: 'exceptZero' })
type Attribution = ReturnType<typeof attribution>

function ShapExplanation({ detail, rows }: { detail: Detail; rows: Attribution }) {
  if (!rows) {
    if (detail.explanation?.state === 'available') {
      return <FeedbackMessage>Dữ liệu SHAP không đầy đủ hoặc không hợp lệ.</FeedbackMessage>
    }
    const reason = detail.explanation?.reason
    const reasonText = typeof reason === 'string' && Object.hasOwn(reasons, reason) ? reasons[reason] : reason ? 'Không thể tính giải thích.' : ''
    return <FeedbackMessage>Chưa có giải thích. {reasonText}</FeedbackMessage>
  }

  const maxMagnitude = Math.max(...rows.map(row => Math.abs(row.amount)))
  return <>
    <p>Dấu + làm tăng mức bất thường theo mô hình; dấu − làm giảm. Đây là đóng góp vào điểm, không phải phần trăm thay đổi lượng hàng.</p>
    <div className="anomaly-shap">
      <div className="anomaly-shap__axis" aria-hidden="true">
        <span><i data-direction="decrease" /> Làm giảm mức bất thường</span>
        <span>0</span>
        <span>Làm tăng mức bất thường <i data-direction="increase" /></span>
      </div>
      <ul className="anomaly-shap__rows" role="list" aria-label="Mức đóng góp SHAP">
        {rows.map(({ key, label, amount, actual }) => {
          const magnitude = Math.abs(amount)
          const formatter = magnitude > 0 && magnitude < 0.00000001 ? signedScientific : signedDecimal
          return <li className="anomaly-shap__row" key={key}>
            <div className="anomaly-shap__label"><span>{label}</span><strong>{formatter.format(amount)}</strong></div>
            {actual !== null && <span className="anomaly-shap__value">{actual}</span>}
            <div className="anomaly-shap__track" aria-hidden="true">
              {amount !== 0 && <span data-direction={amount > 0 ? 'increase' : 'decrease'} style={{ width: `${magnitude / maxMagnitude * 50}%` }} />}
            </div>
          </li>
        })}
      </ul>
    </div>
  </>
}

function CopyId({ label, value }: { label: string; value: string }) {
  const [message, setMessage] = useState('')
  const active = useRef(true), sequence = useRef(0)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  async function copy() {
    const request = ++sequence.current
    setMessage('')
    try {
      await navigator.clipboard.writeText(value)
      if (active.current && request === sequence.current) setMessage('Đã sao chép mã đầy đủ.')
    } catch {
      if (active.current && request === sequence.current) setMessage('Không sao chép được mã.')
    }
  }
  const short = value.length > 25 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value
  return <div>
    <dt>{label}</dt><dd className="anomaly-copy">
      <code>{short}</code>
      <Button type="button" variant="secondary" aria-label={`Sao chép ${label.toLocaleLowerCase('vi-VN')}`} onClick={() => void copy()}>Sao chép</Button>
      <span role="status">{message}</span>
    </dd>
  </div>
}

const checksByFeature: Record<string, string> = {
  log_quantity: 'Đối chiếu số lượng ghi nhận với chứng từ xuất và đơn vị tính.',
  hour_fraction: 'Đối chiếu giờ xuất với giờ ghi nhận, lưu ý hai múi giờ có thể sang ngày khác nhau.',
  weekday_fraction: 'Đối chiếu ngày ghi nhận với lịch làm việc hoặc lịch xuất kho.',
  log_prior_quantity_mean_7d: 'Đối chiếu lượng xuất với các lần xuất trước của cùng sản phẩm và kho.',
  log_prior_event_count_7d: 'Kiểm tra các lần xuất trước có được ghi đầy đủ hay không.',
  log_quantity_to_prior_mean: 'Đối chiếu lượng xuất lần này với các lần xuất trước của cùng sản phẩm và kho.',
}

function AlertReadout({ detail, alertId }: { detail: Detail; alertId: string }) {
  const features = readFeatures(detail)
  const rows = attribution(detail, features)
  const driver = rows?.reduce<(NonNullable<Attribution>)[number] | null>((highest, row) =>
    row.amount > 0 && (!highest || row.amount > highest.amount) ? row : highest, null)
  const comparison = readScoreComparison(detail.score, detail.threshold)
  const exceeds = comparison?.relation === 'above'
  const localTime = formatVietnamTime(detail.occurred_at)
  const history = features.history
  const explanation = detail.explanation
  return <>
    <section className="management-panel anomalies-panel">
      <h2>Thông tin cảnh báo</h2>
      <h3>Vì sao có cảnh báo?</h3>
      <p>Điểm cao hơn ngưỡng thì mô hình gắn cờ. Đây không phải xác suất giao dịch sai.</p>
      <dl className="anomalies-facts">
        <div><dt>Điểm bất thường</dt><dd>{comparison?.scoreText ?? 'Không khả dụng'}</dd></div>
        <div><dt>Ngưỡng cảnh báo</dt><dd>{comparison?.thresholdText ?? 'Không khả dụng'}</dd></div>
        <div><dt>Trạng thái đánh giá</dt><dd>{statusLabels[detail.review_status]}</dd></div>
      </dl>
      {comparison && <p className="anomaly-comparison">{comparison.label}</p>}
      {exceeds
        ? <p>Điểm vượt ngưỡng {number(detail.score - detail.threshold)} điểm.</p>
        : <FeedbackMessage variant="warning">Dữ liệu điểm và ngưỡng không nhất quán. Không thể xác nhận cảnh báo vượt ngưỡng.</FeedbackMessage>}
      {driver
        ? <p>Yếu tố làm tăng điểm nhiều nhất theo mô hình: <strong>{driver.label}</strong>.</p>
        : <p>{rows ? 'Không có yếu tố làm tăng điểm trong phần giải thích.' : 'Chưa có giải thích đáng tin để nêu yếu tố làm tăng điểm.'}</p>}
      <h3>Nên kiểm tra gì?</h3>
      <p>{driver ? checksByFeature[driver.key] : 'Đối chiếu thông tin giao dịch với chứng từ xuất, số lượng và thời điểm ghi nhận.'}</p>
      <p>Cảnh báo giúp kiểm tra giao dịch đã ghi nhận; dự báo ước tính nhu cầu tương lai.</p>
    </section>
    <AnomalyOutboundLink alertId={alertId} />
    <section className="management-panel anomalies-panel">
      <h2>Số liệu để đối chiếu</h2>
      <dl className="anomalies-facts">
        <div><dt>Thời điểm xuất</dt><dd>{localTime ? `${localTime} · Giờ Việt Nam (UTC+07:00)` : 'Không đủ dữ liệu để diễn giải'}</dd></div>
        <div><dt>Giờ và thứ mô hình sử dụng</dt><dd>{features.hour !== null && features.weekday ? `${features.values[1]}, ${features.weekday}` : 'Không đủ dữ liệu để diễn giải'}</dd></div>
        <div><dt>Lượng ghi trong dữ liệu mẫu</dt><dd>{features.quantity === null ? 'Không đủ dữ liệu để diễn giải' : number(features.quantity)}</dd></div>
      </dl>
      <p>Số liệu mẫu chưa phải số trên phiếu xuất đã xác minh.</p>
      <h3>Lịch sử đối chiếu</h3>
      <p>Gồm bảy ngày UTC trọn vẹn trước ngày xuất theo UTC, không kể ngày xảy ra giao dịch. Chỉ tính các lần xuất hợp lệ cùng sản phẩm, kho và đơn vị đã được ghi nhận vào thời điểm dữ liệu của giao dịch này khả dụng.</p>
      {history ? <><p>{history.dates}</p><dl className="anomalies-facts">
        <div><dt>Lượng xuất trung bình mỗi ngày (tổng lượng chia 7)</dt><dd>{number(history.mean)}</dd></div>
        <div><dt>Số giao dịch trong cả kỳ</dt><dd>{number(history.count)}</dd></div>
      </dl></> : <p>Không đủ dữ liệu lịch sử</p>}
    </section>
    <details className="management-panel anomalies-panel anomaly-technical">
      <summary>Thông tin kỹ thuật</summary>
      <h2>Giải thích của mô hình</h2>
      <ShapExplanation detail={detail} rows={rows} />
      <dl className="anomalies-facts">
        <CopyId label="Mã cảnh báo" value={detail.alert_id} />
        <CopyId label="Mã bản ghi nguồn" value={detail.source_record_key} />
        <CopyId label="Mã kết quả" value={detail.run_id} />
        <CopyId label="Phiên bản dữ liệu" value={detail.run.input_version} />
        <div><dt>Phiên bản đặc trưng</dt><dd>{detail.run.feature_version}</dd></div>
        <div><dt>Phiên bản mô hình</dt><dd>{detail.run.model_version}</dd></div>
        <div><dt>Thời điểm tạo</dt><dd>{formatVietnamTime(detail.run.created_at) ?? 'Không khả dụng'}</dd></div>
        <div><dt>Định nghĩa điểm</dt><dd><code>{detail.run.score_definition}</code></dd></div>
        <div><dt>Phiên bản đánh giá</dt><dd>{detail.version}</dd></div>
        {detail.run.partitions.map(p => <div key={p.name}><dt>{partitionLabels[p.name] ?? 'Giai đoạn'}</dt><dd>{p.start} đến trước {p.end} (UTC); giới hạn dữ liệu: {p.information_cutoff}</dd></div>)}
      </dl>
      {rows && explanation?.base_value !== null && explanation.residual !== null && <>
        <p>Giá trị nền: {number(explanation.base_value)}. Sai số đối chiếu: {number(explanation.residual)}. Điểm được giải thích: {comparison?.scoreText ?? number(detail.score)}.</p>
        <p>Phép giải thích giả định các đặc trưng độc lập khi che dữ liệu.</p>
      </>}
      {features.valid && <dl className="anomalies-facts">
        {detail.feature_order.map((name, i) => <div key={name}><dt>{featureLabels[name]} (mô hình)</dt><dd>{number(detail.features[i])}</dd></div>)}
      </dl>}
    </details>
  </>
}

type Attempt = { scope: string; payload: ReviewRequest; key: string }
export function AnomalyDetailPage() {
  const { alertId = '' } = useParams(), { token, user } = useAuth()
  const scope = `${token}:${user?.id}:${user?.role}:${alertId}`, scopeRef = useRef(scope)
  scopeRef.current = scope
  const [loaded, setLoaded] = useState<{ scope: string; detail: Detail; reviews: Review[] } | null>(null)
  const [loadFailure, setLoadFailure] = useState<{ scope: string; text: string } | null>(null), [retry, setRetry] = useState(0)
  const [decision, setDecision] = useState<'confirmed' | 'dismissed'>('confirmed'), [note, setNote] = useState('')
  const [error, setError] = useState(''), [message, setMessage] = useState(''), [pending, setPending] = useState(false)
  const attempt = useRef<Attempt | null>(null), lock = useRef(false), mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { setNote(''); setDecision('confirmed'); setError(''); setMessage(''); attempt.current = null; lock.current = false; setPending(false) }, [scope])
  useEffect(() => {
    if (!token || !user) return
    let active = true
    setLoaded(null); setLoadFailure(null)
    void Promise.all([getAlert(token, alertId), getReviews(token, alertId)]).then(([detail, history]) => {
      if (active && scopeRef.current === scope) setLoaded({ scope, detail, reviews: history.items })
    }).catch((cause: unknown) => { if (active && scopeRef.current === scope && !(cause instanceof ApiError && cause.staleSession)) setLoadFailure({ scope, text: 'Không thể tải cảnh báo. Vui lòng thử lại.' }) })
    return () => { active = false }
  }, [token, user?.id, user?.role, alertId, scope, retry])
  const current = loaded?.scope === scope ? loaded : null
  const loadError = loadFailure?.scope === scope ? loadFailure.text : ''
  async function send() {
    if (!token || !current || lock.current || !note.trim() || note.length > 500) return
    const payload: ReviewRequest = { expected_version: current.detail.version, decision, note }
    const fingerprint = JSON.stringify(payload)
    if (!attempt.current || attempt.current.scope !== scope || JSON.stringify(attempt.current.payload) !== fingerprint) attempt.current = { scope, payload, key: crypto.randomUUID() }
    const captured = attempt.current
    lock.current = true; setPending(true); setError(''); setMessage('')
    try {
      await submitReview(token, alertId, captured.key, captured.payload)
      if (!mounted.current || scopeRef.current !== captured.scope || attempt.current !== captured) return
      attempt.current = null; setMessage('Đã lưu đánh giá.'); setRetry(n => n + 1)
    } catch (cause) {
      if (!mounted.current || scopeRef.current !== captured.scope || attempt.current !== captured || (cause instanceof ApiError && cause.staleSession)) return
      if (cause instanceof ApiError && cause.status === 409) setError('Trạng thái đã thay đổi hoặc yêu cầu xung đột. Hãy tải lại trước khi thử tiếp.')
      else setError('Chưa thể lưu đánh giá. Hãy thử lại cùng nội dung.')
    } finally {
      if (mounted.current && scopeRef.current === captured.scope && attempt.current === captured) { lock.current = false; setPending(false) }
      else if (mounted.current && scopeRef.current === captured.scope) { lock.current = false; setPending(false) }
    }
  }
  const detail = current?.detail
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Chi tiết bất thường" description="Xem lý do mô hình gắn cờ và số liệu để đối chiếu." actions={<Link to="/anomalies">Về danh sách</Link>} />
    <FeedbackMessage variant="warning">Dữ liệu kiểm thử tổng hợp. Hiệu quả trên dữ liệu thực chưa được xác minh. Đóng góp của mô hình không chứng minh quan hệ nhân quả.</FeedbackMessage>
    {loadError ? <><FeedbackMessage variant="error">{loadError}</FeedbackMessage><Button onClick={() => setRetry(n => n + 1)}>Thử lại</Button></> : !detail ? <FeedbackMessage>Đang tải cảnh báo...</FeedbackMessage> : <>
      <AlertReadout key={scope} detail={detail} alertId={alertId} />
      {can(user?.role, 'anomaly:review') && <section className="management-panel anomalies-panel"><h2>Đánh giá cảnh báo</h2><p>Đánh giá chỉ cập nhật hồ sơ cảnh báo, không thay đổi tồn kho hay giao dịch.</p>{error && <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button variant="secondary" onClick={() => setRetry(n => n + 1)}>Tải lại trạng thái</Button></>}{message && <FeedbackMessage variant="success">{message}</FeedbackMessage>}
        <Select label="Quyết định" value={decision} onChange={e => { if (e.target.value) setDecision(e.target.value as 'confirmed' | 'dismissed') }} options={[{ value: 'confirmed', label: 'Xác nhận' }, { value: 'dismissed', label: 'Bác bỏ' }]} />
        <label className="anomalies-note">Ghi chú<textarea value={note} maxLength={500} onChange={e => setNote(e.target.value)} rows={4} /></label>
        <Button disabled={!note.trim() || note.length > 500 || pending} isLoading={pending} onClick={() => void send()}>Lưu đánh giá</Button>
      </section>}
      <section className="management-panel anomalies-panel"><h2>Lịch sử đánh giá</h2>{current.reviews.length ? <ul>{current.reviews.map(review => <li key={review.review_id}>{statusLabels[review.decision]} bởi người dùng {review.actor_user_id} lúc {formatVietnamTime(review.created_at) ? `${formatVietnamTime(review.created_at)} (giờ Việt Nam)` : 'không rõ thời gian'}. Lý do: {review.note}</li>)}</ul> : <p>Chưa có đánh giá.</p>}</section>
    </>}
  </section>
}
