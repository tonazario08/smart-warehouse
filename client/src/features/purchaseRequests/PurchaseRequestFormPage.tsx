import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import type { Product, Warehouse } from '../../types'
import { formatQuantity } from '../../shared/lib/formatters'
import { Button } from '../../shared/ui/Button'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { Select } from '../../shared/ui/Select'
import { createPurchaseRequest, getPurchaseRequestByKey, purchaseRequestError } from './api'
import { validatePurchaseRequest } from './schemas'
import type { PurchaseRequestDraft, PurchaseRequestInput } from './types'
import './purchase-requests.css'

const blank: PurchaseRequestDraft = { warehouse: '', product: '', quantity: '', note: '' }
type Attempt = { key: string; input: PurchaseRequestInput; scope: string; token: string }
export function PurchaseRequestFormPage() {
  const { token, user } = useAuth(), navigate = useNavigate(), location = useLocation()
  const scope = `${token}:${user?.id}:${user?.role}:${location.key}`, scopeRef = useRef(scope), mounted = useRef(true)
  scopeRef.current = scope
  const [draft, setDraft] = useState(blank), [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [loaded, setLoaded] = useState(false), [loading, setLoading] = useState(true), [retry, setRetry] = useState(0)
  const [error, setError] = useState(''), [review, setReview] = useState<PurchaseRequestInput | null>(null)
  const [attempt, setAttempt] = useState<Attempt | null>(null), attemptRef = useRef<Attempt | null>(null)
  const [pending, setPending] = useState(false), lock = useRef(false)
  const [uncertain, setUncertain] = useState(false), [recoveryMessage, setRecoveryMessage] = useState('')
  const busy = pending || attempt !== null
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    setDraft(blank); setReview(null); setAttempt(null); attemptRef.current = null; setPending(false); lock.current = false
    setUncertain(false); setError(''); setRecoveryMessage('')
  }, [scope])
  useEffect(() => {
    if (!token) return
    let active = true
    const current = () => active && scopeRef.current === scope
    setLoading(true); setLoaded(false); setError('')
    void Promise.all([api.productsAll(token), api.warehouses(token)])
      .then(([productRows, warehouseRows]) => { if (current()) { setProducts(productRows.filter(row => row.is_active)); setWarehouses(warehouseRows); setLoaded(true) } })
      .catch((cause: unknown) => { if (current() && !(cause instanceof ApiError && cause.staleSession)) setError(purchaseRequestError(cause, 'Không thể tải dữ liệu biểu mẫu.')) })
      .finally(() => { if (current()) setLoading(false) })
    return () => { active = false }
  }, [token, scope, retry])
  const stillCurrent = (value: Attempt) => mounted.current && value.scope === scopeRef.current && attemptRef.current === value
  function beginReview(event: FormEvent) {
    event.preventDefault()
    if (busy || lock.current || !loaded) return
    const validation = validatePurchaseRequest(draft)
    if (!validation.input) { setError(validation.error ?? 'Dữ liệu chưa hợp lệ.'); return }
    if (!products.some(row => row.id === validation.input!.product_id) || !warehouses.some(row => row.id === validation.input!.warehouse_id)) { setError('Chọn kho và sản phẩm đang hoạt động trong danh sách.'); return }
    setError(''); setReview(validation.input)
  }
  async function send(value: Attempt) {
    if (!stillCurrent(value) || lock.current) return
    lock.current = true; setPending(true); setError(''); setRecoveryMessage('')
    let definitive = false
    try {
      const result = await createPurchaseRequest(value.token, value.key, value.input)
      if (stillCurrent(value)) navigate('/purchase-requests/' + result.id)
    } catch (cause) {
      if (!stillCurrent(value) || (cause instanceof ApiError && cause.staleSession)) return
      setReview(null)
      if (!(cause instanceof ApiError) || cause.status >= 500 || cause.status === 408) setUncertain(true)
      else { setError(purchaseRequestError(cause, 'Không thể gửi yêu cầu mua hàng.')); setUncertain(false); definitive = true }
    } finally {
      if (stillCurrent(value)) {
        lock.current = false; setPending(false)
        if (definitive) { attemptRef.current = null; setAttempt(null) }
      }
    }
  }
  function confirm() {
    if (!review || !token || lock.current || attemptRef.current) return
    const value: Attempt = { key: crypto.randomUUID(), input: review, scope, token }
    attemptRef.current = value; setAttempt(value); void send(value)
  }
  async function lookup() {
    const value = attemptRef.current
    if (!value || !stillCurrent(value) || lock.current) return
    lock.current = true; setPending(true); setRecoveryMessage('')
    try {
      const result = await getPurchaseRequestByKey(value.token, value.key)
      if (stillCurrent(value)) navigate('/purchase-requests/' + result.id)
    } catch (cause) {
      if (stillCurrent(value) && !(cause instanceof ApiError && cause.staleSession)) setRecoveryMessage(cause instanceof ApiError && cause.status === 404 ? 'Chưa tìm thấy yêu cầu. Yêu cầu trước có thể vẫn đang xử lý; hãy tra cứu hoặc thử lại cùng yêu cầu.' : purchaseRequestError(cause, 'Chưa thể tra cứu kết quả. Hãy thử lại cùng yêu cầu.'))
    } finally { if (stillCurrent(value)) { lock.current = false; setPending(false) } }
  }
  const product = products.find(row => row.id === Number(draft.product))
  const change = (field: keyof PurchaseRequestDraft, value: string) => { if (!busy && !review) setDraft(current => ({ ...current, [field]: value })) }
  return <section className="purchase-requests-page">
    <PageHeader title="Tạo yêu cầu mua hàng" description="Yêu cầu được gửi để quản trị viên xem xét trước khi xuất hàng." />
    <FeedbackMessage>Gửi yêu cầu và duyệt không giữ chỗ hoặc trừ tồn kho. Khả năng đáp ứng được kiểm tra khi xuất hàng.</FeedbackMessage>
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải dữ liệu biểu mẫu...</FeedbackMessage> : !loaded ? <Button onClick={() => setRetry(value => value + 1)}>Thử lại biểu mẫu</Button> : <form className="purchase-panel" onSubmit={beginReview} noValidate>
      <fieldset className="ui-form-fields ui-form-section" disabled={busy || review !== null}>
        <h2>Thông tin yêu cầu</h2>
        {!products.length && <FeedbackMessage variant="warning">Chưa có sản phẩm đang hoạt động để yêu cầu.</FeedbackMessage>}
        {!warehouses.length && <FeedbackMessage variant="warning">Chưa có kho hàng để yêu cầu.</FeedbackMessage>}
        <Select required label="Kho hàng" placeholder="Chọn kho hàng" value={draft.warehouse} onChange={event => change('warehouse', event.target.value)} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
        <Select required label="Sản phẩm" placeholder="Chọn sản phẩm" value={draft.product} onChange={event => change('product', event.target.value)} options={products.map(row => ({ value: row.id, label: row.sku + ' · ' + row.name }))} />
        <div className="ui-form-grid"><Input required label="Số lượng" type="number" min={1} max={2147483647} step={1} value={draft.quantity} onChange={event => change('quantity', event.target.value)} /><Input label="Tài khoản yêu cầu" readOnly value={user?.email ?? ''} /></div>
        <Input label="Ghi chú" hint="Không bắt buộc, tối đa 2000 ký tự" value={draft.note} onChange={event => change('note', event.target.value)} />
      </fieldset>
      <div className="purchase-actions">{busy || review !== null ? <span aria-disabled="true" className="ui-button ui-button--secondary ui-button--medium">Hủy</span> : <Link className="ui-button ui-button--secondary ui-button--medium" to="/purchase-requests">Hủy</Link>}<Button type="submit" disabled={busy || review !== null || !products.length || !warehouses.length}>Xem lại yêu cầu</Button></div>
    </form>}
    {uncertain && <section className="purchase-panel purchase-recovery" aria-live="polite"><h2>Chưa xác định kết quả</h2><p>Yêu cầu có thể đã được ghi nhận. Tra cứu hoặc gửi lại đúng yêu cầu, không tạo yêu cầu mới. Khóa và nội dung chỉ được giữ khi biểu mẫu còn mở; tải lại hoặc rời trang sẽ mất dữ liệu khôi phục này.</p>{recoveryMessage && <p>{recoveryMessage}</p>}<div className="purchase-actions"><Button variant="secondary" disabled={pending} onClick={() => void lookup()}>Tra cứu kết quả</Button><Button disabled={pending} onClick={() => { if (attemptRef.current) void send(attemptRef.current) }}>Thử lại cùng yêu cầu</Button></div>{pending && <p>Đang xử lý cùng yêu cầu...</p>}</section>}
    <ConfirmDialog open={review !== null} busy={pending} title="Xác nhận yêu cầu mua hàng" confirmLabel="Gửi yêu cầu mua hàng" description="Gửi để xem xét, không giữ chỗ hoặc trừ tồn kho." onCancel={() => { if (!lock.current) setReview(null) }} onConfirm={confirm}>
      {review && <div className="purchase-confirmation-copy"><p>{warehouses.find(row => row.id === review.warehouse_id)?.name ?? 'Kho #' + review.warehouse_id}</p><p>{product?.sku} · {product?.name}</p><p>Số lượng: {formatQuantity(review.quantity, product?.unit)}</p><p>{review.note ?? 'Không có ghi chú'}</p></div>}
    </ConfirmDialog>
  </section>
}
