import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { formatDateTime } from '../../shared/lib/formatters'
import { can } from '../../shared/lib/permissions'
import { PageHeader } from '../../shared/ui/PageHeader'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { getAlert, getReviews, submitReview } from './api'
import { featureLabels, partitionLabels, reasons, statusLabels } from './types'
import type { Detail, Review, ReviewRequest } from './types'
import '../../shared/styles/management.css'
import './anomalies.css'

const number = (value: number) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 8 }).format(value)
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
  const detail = current?.detail, explanation = detail?.explanation
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Chi tiết bất thường" description="Điểm cao hơn biểu thị bản ghi khác thường hơn, không phải xác suất." actions={<Link to="/anomalies">Về danh sách</Link>} />
    <FeedbackMessage variant="warning">Dữ liệu kiểm thử tổng hợp. Hiệu quả trên dữ liệu thực chưa được xác minh. Đóng góp của mô hình không chứng minh quan hệ nhân quả.</FeedbackMessage>
    {loadError ? <><FeedbackMessage variant="error">{loadError}</FeedbackMessage><Button onClick={() => setRetry(n => n + 1)}>Thử lại</Button></> : !detail ? <FeedbackMessage>Đang tải cảnh báo...</FeedbackMessage> : <>
      <section className="management-panel anomalies-panel"><h2>Thông tin cảnh báo</h2><dl className="anomalies-facts">
        <div><dt>Mã cảnh báo</dt><dd>{detail.alert_id}</dd></div><div><dt>Mã bản ghi nguồn</dt><dd>{detail.source_record_key}</dd></div><div><dt>Thời điểm xuất</dt><dd>{formatDateTime(detail.occurred_at)}</dd></div><div><dt>Điểm bất thường</dt><dd>{number(detail.score)}</dd></div><div><dt>Ngưỡng cảnh báo</dt><dd>{number(detail.threshold)}</dd></div><div><dt>Trạng thái</dt><dd>{statusLabels[detail.review_status]}</dd></div><div><dt>Phiên bản đánh giá</dt><dd>{detail.version}</dd></div>
      </dl></section>
      <section className="management-panel anomalies-panel"><h2>Giải thích của mô hình</h2><p>Phép giải thích giả định các đặc trưng độc lập khi che dữ liệu.</p>{explanation?.state === 'available' && explanation.contributions && explanation.base_value !== null && explanation.residual !== null ? <><p>Giá trị nền: {number(explanation.base_value)}. Sai số đối chiếu: {(explanation.residual !== 0 && explanation.residual < 0.000001 ? explanation.residual.toExponential(2) : number(explanation.residual))}. Điểm được giải thích: {number(detail.score)}.</p><ul>{detail.feature_order.map((name, index) => <li key={name}>{featureLabels[name] ?? 'Đặc trưng không xác định'}: {explanation.contributions![index] >= 0 ? '+' : ''}{number(explanation.contributions![index])} (giá trị {number(detail.features[index])})</li>)}</ul></> : <FeedbackMessage>Chưa có giải thích. {explanation?.reason ? reasons[explanation.reason] ?? 'Không thể tính giải thích.' : ''}</FeedbackMessage>}</section>
      <section className="management-panel anomalies-panel"><h2>Nguồn và phiên bản</h2><dl className="anomalies-facts"><div><dt>Mã kết quả</dt><dd>{detail.run_id}</dd></div><div><dt>Phiên bản dữ liệu</dt><dd>{detail.run.input_version}</dd></div><div><dt>Phiên bản đặc trưng</dt><dd>{detail.run.feature_version}</dd></div><div><dt>Mô hình</dt><dd>Rừng cô lập, {detail.run.model_version}</dd></div><div><dt>Thời điểm tạo</dt><dd>{formatDateTime(detail.run.created_at)}</dd></div><div><dt>Định nghĩa điểm</dt><dd>Đảo dấu điểm mẫu của rừng cô lập</dd></div>{detail.run.partitions.map(p => <div key={p.name}><dt>{partitionLabels[p.name] ?? 'Giai đoạn'}</dt><dd>{p.start} đến trước {p.end}; giới hạn thông tin {formatDateTime(p.information_cutoff)}</dd></div>)}</dl></section>
      {can(user?.role, 'anomaly:review') && <section className="management-panel anomalies-panel"><h2>Đánh giá cảnh báo</h2><p>Đánh giá chỉ cập nhật hồ sơ cảnh báo, không thay đổi tồn kho hay giao dịch.</p>{error && <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button variant="secondary" onClick={() => setRetry(n => n + 1)}>Tải lại trạng thái</Button></>}{message && <FeedbackMessage variant="success">{message}</FeedbackMessage>}
        <Select label="Quyết định" value={decision} onChange={e => { if (e.target.value) setDecision(e.target.value as 'confirmed' | 'dismissed') }} options={[{ value: 'confirmed', label: 'Xác nhận' }, { value: 'dismissed', label: 'Bác bỏ' }]} />
        <label className="anomalies-note">Ghi chú<textarea value={note} maxLength={500} onChange={e => setNote(e.target.value)} rows={4} /></label>
        <Button disabled={!note.trim() || note.length > 500 || pending} isLoading={pending} onClick={() => void send()}>Lưu đánh giá</Button>
      </section>}
      <section className="management-panel anomalies-panel"><h2>Lịch sử đánh giá</h2>{current.reviews.length ? <ul>{current.reviews.map(review => <li key={review.review_id}>{statusLabels[review.decision]} bởi người dùng {review.actor_user_id} lúc {formatDateTime(review.created_at)}: {review.note}</li>)}</ul> : <p>Chưa có đánh giá.</p>}</section>
    </>}
  </section>
}
