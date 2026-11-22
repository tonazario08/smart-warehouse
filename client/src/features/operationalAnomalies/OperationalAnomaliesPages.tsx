import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, request } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { can } from '../../shared/lib/permissions'
import { formatQuantity } from '../../shared/lib/formatters'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { EmptyState } from '../../shared/ui/EmptyState'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { PageHeader } from '../../shared/ui/PageHeader'
import { Pagination } from '../../shared/ui/Pagination'
import { formatVietnamTime, number, probability } from '../anomalies/alertReadability'
import type { AlertOutbound } from '../anomalies/types'
import '../../shared/styles/management.css'
import '../anomalies/anomalies.css'

export const operationalPath = '/anomalies/operational'
const apiPath = '/operational-anomalies'
const pageSize = 20
const labels = {
  pending: 'Chờ chấm',
  unavailable: 'Không thể chấm',
  normal: 'Không vượt ngưỡng',
  flagged: 'Vượt ngưỡng',
  failed: 'Chấm không thành công',
} as const
const reasonLabels: Record<string, string> = {
  NO_APPROVED_MODEL: 'Chưa có mô hình để chấm.',
  MODEL_ARTIFACT_INVALID: 'Không xác minh được mô hình vận hành.',
  INSUFFICIENT_DATA: 'Không đủ dữ liệu trước thời điểm xuất kho.',
  LINEAGE_INVALID: 'Không xác minh được giao dịch nguồn.',
  EXPLANATION_UNAVAILABLE: 'Không xác minh được giải thích về điểm.',
  PROCESSING_FAILED: 'Không thể hoàn thành việc chấm giao dịch.',
}
const features = [
  'Lượng hàng xuất',
  'Giờ xuất (UTC)',
  'Thứ trong tuần (UTC)',
  'Lượng xuất trung bình trong 7 ngày trước',
  'Số giao dịch trong 7 ngày trước',
  'Tỷ lệ lượng xuất so với lịch sử',
]
type DatasetClass = 'operational' | 'synthetic_test'
type Result = {
  transaction_id: number
  state: keyof typeof labels
  dataset_class?: DatasetClass | null
  reason_code: string | null
  evaluated_at: string | null
  score: number | null
  threshold: number | null
  model_version: string | null
  feature_version: string | null
  base_value: number | null
  contributions: number[] | null
}
type ResultPage = { items: Result[]; total: number; page: number; page_size: number }
type Load<T> =
  | { kind: 'loading' | 'denied' | 'missing' | 'failed' }
  | { kind: 'ready'; value: T }

function useRead<T>(path: string | null, source = false) {
  const { token, user } = useAuth()
  const allowed = Boolean(token && can(user?.role, 'anomaly:read') && (!source || can(user?.role, 'inventory:history:read')))
  const [attempt, setAttempt] = useState(0)
  const scope = JSON.stringify([token, user?.id, user?.role, path, attempt])
  const [result, setResult] = useState<{ scope: string; state: Load<T> }>()
  useEffect(() => {
    if (!allowed || !path || !token) return
    const controller = new AbortController()
    const update = (state: Load<T>) => {
      if (!controller.signal.aborted) setResult({ scope, state })
    }
    void request<T>(path, { cache: 'no-store', signal: controller.signal }, token)
      .then(value => update({ kind: 'ready', value }))
      .catch((error: unknown) => {
        if (error instanceof ApiError) {
          if (error.staleSession) return
          if (error.status === 401 || error.status === 403) return update({ kind: 'denied' })
          if (error.status === 404) return update({ kind: 'missing' })
        }
        update({ kind: 'failed' })
      })
    return () => controller.abort()
  }, [allowed, path, scope, token])
  const state: Load<T> = !allowed ? { kind: 'denied' }
    : !path ? { kind: 'missing' }
      : result?.scope === scope ? result.state : { kind: 'loading' }
  return { state, retry: () => setAttempt(value => value + 1) }
}

function ReadStatus({ kind, retry, source = false }: { kind: Load<unknown>['kind']; retry: () => void; source?: boolean }) {
  if (kind === 'loading') return <FeedbackMessage>Đang tải kết quả...</FeedbackMessage>
  if (kind === 'denied') return <FeedbackMessage variant="warning">{source ? 'Bạn không có quyền xem phiếu xuất.' : 'Bạn không có quyền xem kết quả chấm.'}</FeedbackMessage>
  if (kind === 'missing') return <FeedbackMessage>{source ? 'Chưa liên kết được phiếu xuất đối chiếu.' : 'Không tìm thấy kết quả chấm cho giao dịch này.'}</FeedbackMessage>
  if (kind === 'failed') return <>
    <FeedbackMessage variant="error">Không thể tải dữ liệu lúc này.</FeedbackMessage>
    <Button variant="secondary" onClick={retry}>Thử tải lại</Button>
  </>
  return null
}

function validId(id: unknown): id is number {
  return typeof id === 'number' && Number.isSafeInteger(id) && id > 0
}
function validResult(row: Result) {
  return Boolean(row && validId(row.transaction_id) && Object.prototype.hasOwnProperty.call(labels, row.state))
}
function resultPath(transactionId: number) {
  return operationalPath + '/' + transactionId
}
function useTransactionId() {
  const { transactionId = '' } = useParams()
  const id = Number(transactionId)
  return /^[1-9][0-9]*$/.test(transactionId) && validId(id) ? id : null
}
function date(timestamp: string | null) {
  return timestamp ? formatVietnamTime(timestamp) ?? '—' : '—'
}
function StateBadge({ state }: { state: Result['state'] }) {
  return <Badge variant={state === 'flagged' || state === 'unavailable' ? 'warning'
    : state === 'failed' ? 'danger' : state === 'normal' ? 'success' : 'neutral'}>{labels[state]}</Badge>
}
function DatasetBadge({ datasetClass }: { datasetClass?: DatasetClass | null }) {
  return datasetClass === 'synthetic_test' ? <Badge variant="warning">Dữ liệu tổng hợp kiểm thử</Badge> : null
}
function reason(row: Result) {
  if (row.reason_code && Object.prototype.hasOwnProperty.call(reasonLabels, row.reason_code)) {
    return reasonLabels[row.reason_code]
  }
  return row.state === 'pending' ? 'Giao dịch đã xuất kho và đang chờ xử lý.'
    : row.state === 'failed' ? 'Không thể hoàn thành việc chấm giao dịch.'
      : row.state === 'unavailable' ? 'Không đủ điều kiện để chấm giao dịch.' : null
}

export function OperationalAnomaliesPage() {
  const [page, setPage] = useState(1)
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  const { state, retry } = useRead<ResultPage>(apiPath + '?' + query)
  const value = state.kind === 'ready' ? state.value : null
  const valid = value && Array.isArray(value.items) && value.items.every(validResult)
    && Number.isSafeInteger(value.total) && value.total >= 0
    && validId(value.page_size) && value.page === page
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Chấm bất thường sau xuất B2B" description="Kết quả của giao dịch đã xuất kho. Kết quả này tách biệt với cảnh báo demo và kiểm tra tạm tính khi tạo đơn."
      actions={<Link to="/anomalies">Về Bất thường</Link>} />
    {valid ? <>
      <Button variant="secondary" onClick={retry}>Tải lại kết quả</Button>
      {value.items.length ? <>
        <div className="anomalies-scroll" role="region" tabIndex={0} aria-label="Cuộn danh sách giao dịch đã xuất">
          <DataTable caption="Kết quả chấm giao dịch xuất B2B" getRowKey={row => row.transaction_id} rows={value.items} columns={[
            { id: 'transaction', header: 'Giao dịch xuất', render: row => <Link to={resultPath(row.transaction_id)}>Giao dịch #{row.transaction_id}</Link> },
            { id: 'state', header: 'Trạng thái chấm', render: row => <><StateBadge state={row.state} />{' '}<DatasetBadge datasetClass={row.dataset_class} /></> },
            { id: 'reason', header: 'Ghi chú', render: row => reason(row) ?? '—' },
            { id: 'date', header: 'Lần chấm (giờ Việt Nam)', render: row => date(row.evaluated_at) },
          ]} />
        </div>
        <Pagination locale="vi" page={page} pageSize={value.page_size} total={value.total} onPageChange={setPage} />
      </> : <EmptyState title="Chưa có giao dịch để hiển thị" description="Chỉ các lần xuất B2B mới sau khi bật tính năng mới được đưa vào luồng chấm." />}
    </> : <ReadStatus kind={state.kind === 'ready' ? 'failed' : state.kind} retry={retry} />}
  </section>
}

function Scoring({ row }: { row: Result }) {
  if (row.state !== 'normal' && row.state !== 'flagged') return null
  const { score, threshold, base_value: base, contributions } = row
  if (!probability(score) || !probability(threshold) || (score > threshold) !== (row.state === 'flagged')) {
    return <FeedbackMessage variant="warning">Không thể xác minh điểm và ngưỡng đã ghi.</FeedbackMessage>
  }
  const explain = typeof base === 'number' && Number.isFinite(base) && Array.isArray(contributions)
    && contributions.length === features.length && contributions.every(Number.isFinite)
  return <div>
    <dl className="anomalies-facts">
      <div><dt>Điểm bất thường</dt><dd>{number(score)}</dd></div>
      <div><dt>Ngưỡng của mô hình</dt><dd>{number(threshold)}</dd></div>
      <div><dt>Phiên bản mô hình</dt><dd>{row.model_version ?? '—'}</dd></div>
      <div><dt>Phiên bản đặc trưng</dt><dd>{row.feature_version ?? '—'}</dd></div>
    </dl>
    <p>Chỉ gắn cờ khi điểm lớn hơn ngưỡng. Điểm không phải xác suất giao dịch sai.</p>
    {explain && <>
      <h3>Giải thích đóng góp SHAP</h3>
      <p>Điểm nền: {number(base)}. Mỗi giá trị cho biết yếu tố đó làm tăng hay giảm điểm của mô hình, không phải phần trăm thay đổi lượng hàng hay bằng chứng nguyên nhân.</p>
      <dl className="anomalies-facts">
        {features.map((name, i) => <div key={name}><dt>{name}</dt><dd>{contributions[i] > 0 ? '+' : ''}{number(contributions[i])}</dd></div>)}
      </dl>
    </>}
  </div>
}

type OperationalVoucher = AlertOutbound & { dataset_class?: DatasetClass | null }

function validVoucher(value: OperationalVoucher) {
  return value && validId(value.outbound_id) && validId(value.performed_by_id) && validId(value.quantity)
    && [value.product_name, value.product_sku, value.warehouse_code, value.warehouse_name, value.unit]
      .every(field => typeof field === 'string' && Boolean(field.trim()))
    && Boolean(formatVietnamTime(value.occurred_at))
}
function useVoucher(id: number | null) {
  return useRead<OperationalVoucher>(id === null ? null : apiPath + '/' + id + '/outbound', true)
}
function OperationalVoucherLink({ id }: { id: number }) {
  const { state, retry } = useVoucher(id)
  return <section className="management-panel anomalies-panel">
    <h2>Phiếu xuất đối chiếu</h2>
    {state.kind === 'ready' && validVoucher(state.value)
      ? <Link to={resultPath(id) + '/outbound'}>Mở phiếu xuất #{state.value.outbound_id}</Link>
      : <ReadStatus kind={state.kind === 'ready' ? 'failed' : state.kind} retry={retry} source />}
  </section>
}

export function OperationalAnomalyDetailPage() {
  const id = useTransactionId()
  const { state, retry } = useRead<Result>(id === null ? null : apiPath + '/' + id)
  const row = state.kind === 'ready' && validResult(state.value) && state.value.transaction_id === id ? state.value : null
  return <section className="anomalies-page management-workspace">
    <PageHeader title={id === null ? 'Chi tiết chấm bất thường' : 'Giao dịch xuất #' + id} description="Điểm hỗ trợ nhân viên kiểm tra, không kết luận giao dịch sai."
      actions={<Link to={operationalPath}>Về danh sách kết quả</Link>} />
    {row ? <>
      <section className="management-panel anomalies-panel">
        <h2>Kết quả chấm</h2>
        <StateBadge state={row.state} />{' '}<DatasetBadge datasetClass={row.dataset_class} />
        {reason(row) && <FeedbackMessage>{reason(row)}</FeedbackMessage>}
        <Scoring row={row} />
        <Button variant="secondary" onClick={retry}>Tải lại kết quả</Button>
      </section>
      {row.state === 'flagged' && <OperationalVoucherLink id={row.transaction_id} />}
    </> : <ReadStatus kind={state.kind === 'ready' ? 'failed' : state.kind} retry={retry} />}
  </section>
}

export function OperationalAnomalyOutboundPage() {
  const id = useTransactionId()
  const { state, retry } = useVoucher(id)
  const voucher = state.kind === 'ready' && validVoucher(state.value) ? state.value : null
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Phiếu xuất đối chiếu" description="Thông tin trích từ giao dịch xuất đã được đối chiếu. Nếu kết quả chấm có nhãn kiểm thử, phiếu thuộc ca kiểm thử đó."
      actions={<Link to={id === null ? operationalPath : resultPath(id)}>Về chi tiết giao dịch</Link>} />
    {voucher ? <section className="management-panel anomalies-panel">
      <h2>Phiếu xuất #{voucher.outbound_id}</h2>
      <DatasetBadge datasetClass={voucher.dataset_class} />
      <dl className="anomalies-facts">
        <div><dt>Sản phẩm</dt><dd>{voucher.product_name} ({voucher.product_sku})</dd></div>
        <div><dt>Kho xuất</dt><dd>{voucher.warehouse_name} ({voucher.warehouse_code})</dd></div>
        <div><dt>Số lượng xuất</dt><dd>{formatQuantity(voucher.quantity, voucher.unit)}</dd></div>
        <div><dt>Thời điểm xuất</dt><dd>{date(voucher.occurred_at)} (giờ Việt Nam)</dd></div>
        <div><dt>Người thực xuất</dt><dd>Người dùng #{voucher.performed_by_id}</dd></div>
      </dl>
    </section> : <ReadStatus kind={state.kind === 'ready' ? 'failed' : state.kind} retry={retry} source />}
  </section>
}
