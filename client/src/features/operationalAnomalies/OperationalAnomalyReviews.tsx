import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, request } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { can } from '../../shared/lib/permissions'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Pagination } from '../../shared/ui/Pagination'
import { Select } from '../../shared/ui/Select'
import { formatVietnamTime } from '../anomalies/alertReadability'

const labels = {
  confirmed_business_issue: 'Ghi nhận vấn đề nghiệp vụ',
  legitimate: 'Giao dịch hợp lệ',
  insufficient_evidence: 'Chưa đủ bằng chứng',
} as const
type Decision = keyof typeof labels
type Review = {
  version: number
  decision: Decision
  note: string
  actor_id: number
  reviewed_at: string
}
type History = { items: Review[]; total: number; page: number; page_size: number; current_version: number }
type Payload = { expected_version: number; decision: Decision; note: string }
type Attempt = { key: string; payload: Payload }
type Fault = 'denied' | 'missing' | 'failed'

const pageSize = 20
const isCount = (value: number) => Number.isSafeInteger(value) && value >= 0
const isDecision = (value: string): value is Decision => Object.prototype.hasOwnProperty.call(labels, value)
const options = Object.entries(labels).map(([value, label]) => ({ value, label }))

function validReview(value: Review): boolean {
  return Boolean(value && isCount(value.version) && value.version > 0
    && isCount(value.actor_id) && value.actor_id > 0 && isDecision(value.decision)
    && typeof value.note === 'string' && value.note.trim().length > 0
    && Boolean(formatVietnamTime(value.reviewed_at)))
}

function validHistory(value: History, page: number): boolean {
  return Boolean(value && value.page === page && value.page_size === pageSize
    && isCount(value.total) && isCount(value.current_version) && Array.isArray(value.items)
    && value.items.length <= pageSize && value.items.length <= value.total
    && value.items.every(row => validReview(row) && row.version <= value.current_version)
    && (page !== 1 || (value.total === 0 ? value.current_version === 0 : value.items[0]?.version === value.current_version)))
}

function readFault(cause: unknown): Fault {
  if (cause instanceof ApiError) {
    if (cause.status === 401 || cause.status === 403) return 'denied'
    if (cause.status === 404) return 'missing'
  }
  return 'failed'
}

export function OperationalAnomalyReviews({ transactionId }: { transactionId: number }) {
  const { token, user } = useAuth()
  if (!token || !user || !can(user.role, 'anomaly:read')) return null
  return <ReviewPanel
    key={JSON.stringify([token, user.id, user.role, transactionId])}
    token={token}
    transactionId={transactionId}
    mayReview={can(user.role, 'anomaly:review')}
  />
}

function ReviewPanel({ transactionId, token, mayReview }: { transactionId: number; token: string; mayReview: boolean }) {
  const path = '/operational-anomalies/' + transactionId
  const [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [snapshot, setSnapshot] = useState<{ key: string; history?: History; fault?: Fault }>()
  const [decision, setDecision] = useState<Decision | ''>('')
  const [note, setNote] = useState('')
  const [notice, setNotice] = useState<{ variant: 'success' | 'error' | 'warning'; text: string }>()
  const [pending, setPending] = useState(false)
  const [retryable, setRetryable] = useState(false)
  const [writeBlocked, setWriteBlocked] = useState(false)
  const attempt = useRef<Attempt | null>(null)
  const write = useRef<AbortController | null>(null)
  const key = `${page}:${revision}`

  useEffect(() => () => write.current?.abort(), [])
  useEffect(() => {
    const controller = new AbortController()
    const update = (value: { history?: History; fault?: Fault }) => {
      if (!controller.signal.aborted) setSnapshot({ key, ...value })
    }
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    void request<History>(path + '/reviews?' + params, { cache: 'no-store', signal: controller.signal }, token)
      .then(value => update(validHistory(value, page) ? { history: value } : { fault: 'failed' }))
      .catch((cause: unknown) => {
        if (!(cause instanceof ApiError && cause.staleSession)) update({ fault: readFault(cause) })
      })
    return () => controller.abort()
  }, [path, page, key, token])

  const current = snapshot?.key === key ? snapshot : undefined
  const history = current?.history
  const cleaned = note.trim()
  const validNote = cleaned.length > 0 && Array.from(cleaned).length <= 1000

  function refresh() {
    if (write.current) return
    attempt.current = null
    setRetryable(false)
    setWriteBlocked(false)
    setRevision(value => value + 1)
    setPage(1)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!mayReview || !history || write.current || writeBlocked || !decision || !validNote) return
    const captured = attempt.current ?? {
      key: crypto.randomUUID(),
      payload: { expected_version: history.current_version, decision, note: cleaned },
    }
    const controller = new AbortController()
    attempt.current = captured
    write.current = controller
    setPending(true)
    setNotice(undefined)
    let mustRefresh = false
    try {
      const saved = await request<Review>(path + '/review', {
        method: 'PATCH',
        signal: controller.signal,
        headers: { 'Idempotency-Key': captured.key },
        body: JSON.stringify(captured.payload),
      }, token)
      if (controller.signal.aborted) return
      if (!validReview(saved) || saved.version !== captured.payload.expected_version + 1
        || saved.decision !== captured.payload.decision || saved.note !== captured.payload.note) {
        throw new Error('Unverified review response')
      }
      setDecision('')
      setNote('')
      setNotice({ variant: 'success', text: 'Đã lưu đánh giá của nhân viên.' })
      mustRefresh = true
    } catch (cause) {
      if (controller.signal.aborted || (cause instanceof ApiError && cause.staleSession)) return
      if (cause instanceof ApiError && cause.status === 409) {
        setNotice({ variant: 'warning', text: 'Đánh giá đã thay đổi hoặc yêu cầu bị xung đột. Đang tải lại lịch sử; hãy kiểm tra rồi lưu lại nếu cần.' })
        mustRefresh = true
      } else if (cause instanceof ApiError && [401, 403, 404].includes(cause.status)) {
        setNotice({ variant: 'warning', text: cause.status === 404 ? 'Không còn xác minh được cảnh báo để đánh giá.' : 'Bạn không có quyền ghi đánh giá.' })
        attempt.current = null
        setRetryable(false)
        setWriteBlocked(true)
        setSnapshot({ key, fault: readFault(cause) })
      } else {
        setNotice({ variant: 'error', text: 'Chưa xác minh được kết quả lưu. Hãy thử lại cùng nội dung hoặc tải lại lịch sử trước khi sửa.' })
        setRetryable(true)
      }
    } finally {
      if (!controller.signal.aborted) {
        write.current = null
        setPending(false)
        if (mustRefresh) refresh()
      }
    }
  }

  return <section className="management-panel anomalies-panel">
    <h2>Đánh giá của nhân viên</h2>
    <p>Đánh giá chỉ ghi nhận ý kiến đối chiếu. Không đổi điểm, ngưỡng, phiếu xuất hoặc tồn kho; giải thích SHAP không chứng minh nguyên nhân.</p>
    {notice && <FeedbackMessage variant={notice.variant}>{notice.text}</FeedbackMessage>}
    {!current ? <FeedbackMessage>Đang tải lịch sử đánh giá...</FeedbackMessage> : current.fault ? <>
      <FeedbackMessage variant={current.fault === 'failed' ? 'error' : 'warning'}>
        {current.fault === 'denied' ? 'Bạn không có quyền xem đánh giá.'
          : current.fault === 'missing' ? 'Không xác minh được cảnh báo để xem đánh giá.'
            : 'Không thể tải lịch sử đánh giá.'}
      </FeedbackMessage>
      <Button variant="secondary" onClick={refresh}>Tải lại đánh giá</Button>
    </> : history && <>
      <h3>Lịch sử đánh giá</h3>
      {history.total === 0 ? <p>Chưa có đánh giá.</p> : <>
        <ol>
          {history.items.map(row => {
            const time = formatVietnamTime(row.reviewed_at)
            return <li key={row.version}>
              <strong>{labels[row.decision]}</strong> (phiên bản {row.version})
              {': '}Người dùng #{row.actor_id} lúc <time dateTime={row.reviewed_at}>{time}</time> (giờ Việt Nam).
              <p>Lý do: {row.note}</p>
            </li>
          })}
        </ol>
        <Pagination locale="vi" page={page} pageSize={pageSize} total={history.total} onPageChange={next => {
          if (!write.current && !attempt.current) setPage(next)
        }} />
      </>}
      {mayReview && !writeBlocked && <form onSubmit={submit}>
        <fieldset disabled={pending || retryable}>
          <legend>Ghi nhận đánh giá mới</legend>
          <Select label="Nhận định" value={decision} onChange={event => {
            const value = event.target.value
            setDecision(isDecision(value) ? value : '')
          }} options={options} />
          <label className="anomalies-note">Lý do đối chiếu
            <textarea value={note} onChange={event => setNote(event.target.value)} rows={4} />
          </label>
          <p>Nhập từ 1 đến 1.000 ký tự.</p>
        </fieldset>
        <Button type="submit" disabled={!decision || !validNote || pending} isLoading={pending}>
          {retryable ? 'Thử lưu lại cùng nội dung' : 'Lưu đánh giá'}
        </Button>
        <Button type="button" disabled={pending} variant="secondary" onClick={refresh}>Tải lại đánh giá</Button>
      </form>}
    </>}
  </section>
}
