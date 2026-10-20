import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import type { Product, Warehouse } from '../../types'
import { formatDateTime, formatQuantity } from '../../shared/lib/formatters'
import { can } from '../../shared/lib/permissions'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { approvePurchaseRequest, fulfillPurchaseRequest, getPurchaseRequest, purchaseRequestError, rejectPurchaseRequest } from './api'
import { validateRejectionReason } from './schemas'
import type { PurchaseRequest } from './types'
import { statusLabels } from './types'
import './purchase-requests.css'

type Action = 'approve' | 'reject' | 'fulfill'
type Attempt = { action: Action; reason?: string; id: number; scope: string; token: string }
const actionLabels = { approve: 'Xác nhận duyệt', reject: 'Xác nhận từ chối', fulfill: 'Xác nhận xuất hàng' }
export function PurchaseRequestDetailPage() {
  const { id = '' } = useParams(), { token, user } = useAuth(), location = useLocation()
  const scope = `${token}:${user?.id}:${user?.role}:${location.key}:${id}`, scopeRef = useRef(scope), mounted = useRef(true)
  scopeRef.current = scope
  const [data, setData] = useState<{ scope: string; value: PurchaseRequest } | null>(null)
  const [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const [reason, setReason] = useState(''), [review, setReview] = useState<Attempt | null>(null)
  const [attempt, setAttempt] = useState<Attempt | null>(null), attemptRef = useRef<Attempt | null>(null)
  const [pending, setPending] = useState(false), lock = useRef(false), [uncertain, setUncertain] = useState(false), [recoveryMessage, setRecoveryMessage] = useState('')
  const [stock, setStock] = useState<{ context: string; quantity: number } | null>(null), [stockError, setStockError] = useState(false), [stockRetry, setStockRetry] = useState(0)
  const current = data?.scope === scope ? data.value : null, busy = pending || attempt !== null
  const context = `${scope}:${current?.warehouse_id}:${current?.product_id}:${current?.status}`
  const currentStock = stock?.context === context ? stock.quantity : null
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { setReview(null); setAttempt(null); attemptRef.current = null; setPending(false); lock.current = false; setUncertain(false); setReason(''); setRecoveryMessage('') }, [scope])
  useEffect(() => {
    if (!token) return
    let active = true
    const valid = () => active && scopeRef.current === scope
    setData(null); setError(''); setLoading(true)
    if (!/^[1-9]\d*$/.test(id) || id.length > 10 || Number(id) > 2147483647) { setError('Mã yêu cầu không hợp lệ.'); setLoading(false); return }
    void Promise.all([getPurchaseRequest(token, Number(id)), api.productsAll(token).catch(() => [] as Product[]), api.warehouses(token).catch(() => [] as Warehouse[])])
      .then(([result, productRows, warehouseRows]) => { if (valid()) { setData({ scope, value: result }); setProducts(productRows); setWarehouses(warehouseRows) } })
      .catch((cause: unknown) => { if (valid() && !(cause instanceof ApiError && cause.staleSession)) setError(purchaseRequestError(cause, 'Không thể tải yêu cầu mua hàng.')) })
      .finally(() => { if (valid()) setLoading(false) })
    return () => { active = false }
  }, [token, scope, id, retry])
  useEffect(() => {
    setStock(null); setStockError(false)
    if (!token || !current?.workflow_managed || current.status !== 'approved' || !can(user?.role, 'purchase_request:fulfill')) return
    let active = true
    const captured = current
    void api.stock(token).then(rows => { if (active && scopeRef.current === scope) setStock({ context, quantity: rows.find(row => row.warehouse_id === captured.warehouse_id && row.product_id === captured.product_id)?.quantity ?? 0 }) })
      .catch((cause: unknown) => { if (active && scopeRef.current === scope && !(cause instanceof ApiError && cause.staleSession)) setStockError(true) })
    return () => { active = false }
  }, [token, scope, context, current?.workflow_managed, current?.status, user?.role, stockRetry])
  const stillCurrent = (value: Attempt) => mounted.current && scopeRef.current === value.scope && attemptRef.current === value
  function begin(action: Action) {
    if (!current || !token || busy || lock.current) return
    const validation = action === 'reject' ? validateRejectionReason(reason) : null
    if (validation && !validation.reason) { setError(validation.error ?? 'Nhập lý do từ chối.'); return }
    setError(''); setReview({ action, reason: validation?.reason, id: current.id, scope, token })
  }
  async function send(value: Attempt) {
    if (!stillCurrent(value) || lock.current) return
    lock.current = true; setPending(true); setError(''); setRecoveryMessage('')
    let finished = false
    try {
      const result = await (value.action === 'approve' ? approvePurchaseRequest(value.token, value.id) : value.action === 'reject' ? rejectPurchaseRequest(value.token, value.id, value.reason!) : fulfillPurchaseRequest(value.token, value.id))
      if (stillCurrent(value)) { setData({ scope: value.scope, value: result }); setReview(null); setUncertain(false); finished = true }
    } catch (cause) {
      if (!stillCurrent(value) || (cause instanceof ApiError && cause.staleSession)) return
      setReview(null)
      if (!(cause instanceof ApiError) || cause.status >= 500 || cause.status === 408) setUncertain(true)
      else { setError(purchaseRequestError(cause, 'Không thể thực hiện thao tác yêu cầu mua hàng.')); setUncertain(false); finished = true; setStockRetry(count => count + 1) }
    } finally {
      if (stillCurrent(value)) { lock.current = false; setPending(false); if (finished) { attemptRef.current = null; setAttempt(null) } }
    }
  }
  function confirm() {
    if (!review || lock.current || attemptRef.current || review.scope !== scopeRef.current) return
    attemptRef.current = review; setAttempt(review); void send(review)
  }
  async function lookup() {
    const value = attemptRef.current
    if (!value || !stillCurrent(value) || lock.current) return
    lock.current = true; setPending(true); setRecoveryMessage('')
    let recovered = false
    try {
      const result = await getPurchaseRequest(value.token, value.id)
      if (!stillCurrent(value)) return
      setData({ scope: value.scope, value: result })
      recovered = value.action === 'fulfill' ? result.status === 'fulfilled' && result.fulfillment !== null : value.action === 'approve' ? result.decision?.kind === 'approved' : result.decision?.kind === 'rejected' && result.decision.rejection_reason === value.reason
      if (recovered) setUncertain(false)
      else setRecoveryMessage('Trạng thái hiện tại không chứng minh thao tác trước đã thất bại. Hãy tra cứu tiếp hoặc thử lại cùng thao tác trên yêu cầu này.')
    } catch (cause) {
      if (stillCurrent(value) && !(cause instanceof ApiError && cause.staleSession)) setRecoveryMessage(purchaseRequestError(cause, 'Chưa thể tra cứu trạng thái; giữ nguyên thao tác để khôi phục.'))
    } finally {
      if (stillCurrent(value)) { lock.current = false; setPending(false); if (recovered) { attemptRef.current = null; setAttempt(null) } }
    }
  }
  const product = products.find(row => row.id === current?.product_id)
  return <section className="purchase-requests-page">
    <PageHeader title="Chi tiết yêu cầu mua hàng" description="Theo dõi trạng thái và thông tin đã được ghi nhận của yêu cầu." />
    {busy || review ? <span>Về danh sách khi thao tác đã được xử lý.</span> : <Link to="/purchase-requests">Về danh sách yêu cầu</Link>}
    {loading ? <FeedbackMessage>Đang tải yêu cầu mua hàng...</FeedbackMessage> : !current ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại chi tiết</Button></> : <>
      {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
      <section className="purchase-panel"><h2>{current.request_number}</h2><div><Badge variant={current.status === 'fulfilled' ? 'success' : current.status === 'rejected' ? 'danger' : current.status === 'approved' ? 'primary' : 'warning'}>{statusLabels[current.status]}</Badge></div>
        {!current.workflow_managed && <FeedbackMessage variant="warning">Yêu cầu cũ chỉ có thể xem. Thông tin quyết định và xuất hàng không được suy diễn từ trạng thái cũ.</FeedbackMessage>}
        <dl className="purchase-facts">
          <div><dt>Sản phẩm</dt><dd>{product ? product.sku + ' · ' + product.name : 'Sản phẩm #' + current.product_id}{product && !product.is_active ? ' · Ngừng hoạt động' : ''}</dd></div>
          <div><dt>Kho hàng</dt><dd>{warehouses.find(row => row.id === current.warehouse_id)?.name ?? 'Kho #' + current.warehouse_id}</dd></div>
          <div><dt>Số lượng yêu cầu</dt><dd>{formatQuantity(current.quantity, product?.unit)}</dd></div>
          <div><dt>Người yêu cầu</dt><dd>Tài khoản #{current.requested_by_id}</dd></div>
          <div><dt>Thời điểm tạo</dt><dd>{formatDateTime(current.created_at)}</dd></div><div><dt>Cập nhật lần cuối</dt><dd>{formatDateTime(current.updated_at)}</dd></div>
          <div><dt>Ghi chú</dt><dd>{current.note ?? (current.workflow_managed ? 'Không có' : 'Chưa có thông tin được ghi nhận')}</dd></div>
        </dl>
      </section>
      <section className="purchase-panel"><h2>Quyết định</h2>{current.decision ? <dl className="purchase-facts"><div><dt>Người quyết định</dt><dd>Tài khoản #{current.decision.actor_id}</dd></div><div><dt>Thời điểm quyết định</dt><dd>{formatDateTime(current.decision.decided_at)}</dd></div>{current.decision.rejection_reason && <div><dt>Lý do từ chối</dt><dd>{current.decision.rejection_reason}</dd></div>}</dl> : <p>{current.workflow_managed ? 'Chưa có quyết định' : 'Chưa có thông tin quyết định được ghi nhận'}</p>}<p>Tạo và duyệt yêu cầu không giữ chỗ hoặc trừ tồn kho.</p></section>
      {current.fulfillment ? <section className="purchase-panel"><h2>Tồn kho tại thời điểm xuất</h2><p>Đây là lịch sử đã ghi nhận, không phải tồn kho hiện tại.</p><dl className="purchase-facts"><div><dt>Trước khi xuất</dt><dd>{formatQuantity(current.fulfillment.quantity_before, product?.unit)}</dd></div><div><dt>Sau khi xuất</dt><dd>{formatQuantity(current.fulfillment.quantity_after, product?.unit)}</dd></div><div><dt>Người xuất hàng</dt><dd>Tài khoản #{current.fulfillment.actor_id}</dd></div><div><dt>Thời điểm xuất</dt><dd>{formatDateTime(current.fulfillment.fulfilled_at)}</dd></div></dl><p>Phiếu xuất #{current.fulfillment.outbound_id} · Giao dịch #{current.fulfillment.transaction_id}</p></section> : <section className="purchase-panel"><h2>Xuất hàng</h2><p>Chưa có thông tin xuất hàng được ghi nhận</p></section>}
      {current.workflow_managed && current.status === 'pending' && can(user?.role, 'purchase_request:review') && <section className="purchase-panel"><h2>Xem xét yêu cầu</h2><Input label="Lý do từ chối" hint="Bắt buộc khi từ chối, tối đa 1000 ký tự" value={reason} disabled={busy || review !== null} onChange={event => setReason(event.target.value)} /><div className="purchase-actions"><Button disabled={busy || review !== null} onClick={() => begin('approve')}>Duyệt yêu cầu</Button><Button variant="danger" disabled={busy || review !== null} onClick={() => begin('reject')}>Từ chối yêu cầu</Button></div></section>}
      {current.workflow_managed && current.status === 'approved' && can(user?.role, 'purchase_request:fulfill') && <section className="purchase-panel" aria-live="polite"><h2>Tồn kho hiện tại</h2>{currentStock === null ? <><p>Chưa xác định tồn kho</p>{stockError ? <><FeedbackMessage variant="error">Không thể kiểm tra tồn kho.</FeedbackMessage><Button variant="secondary" disabled={busy || review !== null} onClick={() => setStockRetry(value => value + 1)}>Kiểm tra lại tồn kho</Button></> : <p>Đang kiểm tra tồn kho...</p>}</> : <><p>{formatQuantity(currentStock, product?.unit)}</p>{currentStock < current.quantity && <FeedbackMessage variant="warning">Tồn kho hiện tại chưa đủ số lượng yêu cầu.</FeedbackMessage>}</>}<p>Tồn kho có thể thay đổi; máy chủ kiểm tra lại khi xác nhận xuất hàng.</p><Button disabled={busy || review !== null} onClick={() => begin('fulfill')}>Xuất hàng</Button></section>}
    </>}
    {uncertain && <section className="purchase-panel purchase-recovery" aria-live="polite"><h2>Chưa xác định kết quả</h2><p>Thao tác có thể đã hoàn tất. Tra cứu trạng thái hoặc thử lại đúng thao tác trên yêu cầu này. Sau khi tải lại, mở chi tiết theo mã yêu cầu để kiểm tra trạng thái đã lưu.</p>{recoveryMessage && <p>{recoveryMessage}</p>}<div className="purchase-actions"><Button variant="secondary" disabled={pending} onClick={() => void lookup()}>Tra cứu trạng thái</Button><Button disabled={pending} onClick={() => { if (attemptRef.current) void send(attemptRef.current) }}>Thử lại cùng thao tác</Button></div></section>}
    <ConfirmDialog open={review !== null} busy={pending} title={review ? actionLabels[review.action] : 'Xác nhận thao tác'} confirmLabel={review ? actionLabels[review.action] : 'Xác nhận'} confirmVariant={review?.action === 'reject' ? 'danger' : 'primary'} description={review?.action === 'fulfill' ? 'Xuất toàn bộ số lượng yêu cầu. Máy chủ kiểm tra lại tồn kho và trạng thái trước khi ghi nhận.' : review?.action === 'approve' ? 'Duyệt yêu cầu không giữ chỗ hoặc trừ tồn kho.' : 'Lưu quyết định từ chối cùng lý do đã nhập.'} onCancel={() => { if (!lock.current) setReview(null) }} onConfirm={confirm}>
      {review && <div className="purchase-confirmation-copy"><p>{current?.request_number}</p><p>{product ? product.sku + ' · ' + product.name : 'Sản phẩm #' + current?.product_id}</p><p>{review.reason ?? (current ? 'Số lượng: ' + formatQuantity(current.quantity, product?.unit) : '')}</p></div>}
    </ConfirmDialog>
  </section>
}
