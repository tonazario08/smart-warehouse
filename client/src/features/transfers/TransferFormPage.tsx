import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { createTransfer, getTransferByKey } from './api'
import { validateTransfer } from './schemas'
import type { TransferDraft, TransferInput } from './types'
import './transfers.css'

const blankDraft: TransferDraft = { source: '', destination: '', product: '', quantity: '', reference: '', note: '' }
type Attempt = { key: string; input: TransferInput; scope: string }
export function TransferFormPage() {
  const { token, user } = useAuth(), navigate = useNavigate()
  const scope = `${token}:${user?.id}:${user?.role}`, scopeRef = useRef(scope), mounted = useRef(true)
  scopeRef.current = scope
  const [draft, setDraft] = useState<TransferDraft>(blankDraft)
  const [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [loaded, setLoaded] = useState(false), [loading, setLoading] = useState(true), [retry, setRetry] = useState(0)
  const [error, setError] = useState(''), [review, setReview] = useState<TransferInput | null>(null)
  const [pending, setPending] = useState(false), pendingLock = useRef(false)
  const [attempt, setAttempt] = useState<Attempt | null>(null), attemptRef = useRef<Attempt | null>(null)
  const [uncertain, setUncertain] = useState(false), [recoveryMessage, setRecoveryMessage] = useState('')
  const [stockRetry, setStockRetry] = useState(0), [stockError, setStockError] = useState('')
  const [stock, setStock] = useState<{ context: string; source: number; destination: number } | null>(null)
  const context = `${scope}:${draft.source}:${draft.destination}:${draft.product}`
  const busy = pending || uncertain || attempt !== null
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    setDraft(blankDraft); setReview(null); setAttempt(null); attemptRef.current = null
    setUncertain(false); setPending(false); pendingLock.current = false; setError(''); setRecoveryMessage('')
  }, [scope])
  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true); setLoaded(false); setError('')
    void Promise.all([api.productsAll(token), api.warehouses(token)])
      .then(([productRows, warehouseRows]) => { if (active) { setProducts(productRows); setWarehouses(warehouseRows); setLoaded(true) } })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setError(cause instanceof ApiError ? cause.message : 'Không thể tải dữ liệu biểu mẫu.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, scope, retry])
  useEffect(() => {
    setStock(null); setStockError('')
    if (!token || !draft.source || !draft.destination || !draft.product) return
    let active = true
    void api.stock(token).then(rows => {
      if (!active) return
      const quantity = (warehouseId: string) => rows.find(row => row.warehouse_id === Number(warehouseId) && row.product_id === Number(draft.product))?.quantity ?? 0
      setStock({ context, source: quantity(draft.source), destination: quantity(draft.destination) })
    }).catch((cause: unknown) => {
      if (active && !(cause instanceof ApiError && cause.staleSession)) setStockError('Không thể kiểm tra tồn kho. Vui lòng thử lại.')
    })
    return () => { active = false }
  }, [token, context, draft.source, draft.destination, draft.product, stockRetry])
  const current = stock?.context === context ? stock : null
  const amount = /^[1-9]\d*$/.test(draft.quantity) && Number(draft.quantity) <= 2147483647 ? Number(draft.quantity) : null
  const product = products.find(row => row.id === Number(draft.product))
  const name = (id: number) => warehouses.find(row => row.id === id)?.name ?? 'Kho #' + id
  const stillCurrent = (value: Attempt) => mounted.current && value.scope === scopeRef.current && attemptRef.current === value
  function beginReview(event: FormEvent) {
    event.preventDefault()
    if (busy || pendingLock.current || !loaded) return
    const validation = validateTransfer(draft)
    if (!validation.input) { setError(validation.error ?? 'Dữ liệu chưa hợp lệ.'); return }
    if (!products.some(row => row.id === validation.input!.product_id) || !warehouses.some(row => row.id === validation.input!.source_warehouse_id) || !warehouses.some(row => row.id === validation.input!.destination_warehouse_id)) { setError('Kho hoặc sản phẩm không còn trong danh sách. Vui lòng tải lại.'); return }
    setError(''); setReview(validation.input)
  }
  async function send(value: Attempt) {
    if (!token || pendingLock.current || value.scope !== scopeRef.current) return
    pendingLock.current = true; setPending(true); setError(''); setRecoveryMessage('')
    try {
      const result = await createTransfer(token, value.key, value.input)
      if (!stillCurrent(value)) return
      // Existing destinations read live stock/history on mount; also refresh these
      // real adapters after success without treating refresh failure as a failed write.
      void Promise.allSettled([api.stock(token), api.transactions(token)])
      navigate('/transfers/' + result.id)
    } catch (cause) {
      if (!stillCurrent(value) || (cause instanceof ApiError && cause.staleSession)) return
      setReview(null)
      if (!(cause instanceof ApiError) || cause.status >= 500 || cause.status === 408) {
        setUncertain(true)
      } else {
        setError(cause.message); setUncertain(false); setAttempt(null); attemptRef.current = null
        setStockRetry(count => count + 1)
      }
    } finally {
      if (mounted.current && value.scope === scopeRef.current) { pendingLock.current = false; setPending(false) }
    }
  }
  function confirm() {
    if (!review || pendingLock.current || attemptRef.current) return
    const value: Attempt = { key: crypto.randomUUID(), input: review, scope }
    attemptRef.current = value; setAttempt(value)
    void send(value)
  }
  async function lookup() {
    const value = attemptRef.current
    if (!token || !value || pendingLock.current) return
    pendingLock.current = true; setPending(true); setRecoveryMessage('')
    try {
      const result = await getTransferByKey(token, value.key)
      if (stillCurrent(value)) navigate('/transfers/' + result.id)
    } catch (cause) {
      if (!stillCurrent(value) || (cause instanceof ApiError && cause.staleSession)) return
      setRecoveryMessage(cause instanceof ApiError && cause.status === 404 ? 'Phiếu chưa được tìm thấy. Yêu cầu trước có thể vẫn đang xử lý; hãy thử lại cùng yêu cầu.' : cause instanceof ApiError ? cause.message : 'Chưa thể tra cứu kết quả. Hãy thử lại cùng yêu cầu.')
    } finally { if (mounted.current && value.scope === scopeRef.current) { pendingLock.current = false; setPending(false) } }
  }
  const change = (field: keyof TransferDraft, value: string) => { if (!busy && !review) setDraft(currentDraft => ({ ...currentDraft, [field]: value })) }
  return <section className="transfers-page">
    <PageHeader title="Tạo phiếu chuyển kho" description="Một lần xác nhận ghi nhận xuất tại kho nguồn và nhập tại kho đích." />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải dữ liệu biểu mẫu...</FeedbackMessage> : !loaded ? <Button onClick={() => setRetry(value => value + 1)}>Thử lại biểu mẫu</Button> : <form className="transfer-panel" onSubmit={beginReview} noValidate>
      <fieldset className="ui-form-fields ui-form-section" disabled={busy || review !== null}>
        <h2>Thông tin chuyển kho</h2>
        <div className="ui-form-grid">
          <Select required label="Kho nguồn" placeholder="Chọn kho nguồn" value={draft.source} onChange={event => change('source', event.target.value)} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
          <Select required label="Kho đích" placeholder="Chọn kho đích" value={draft.destination} onChange={event => change('destination', event.target.value)} options={warehouses.map(row => ({ value: row.id, label: row.name }))} />
        </div>
        <Select required label="Sản phẩm" placeholder="Chọn sản phẩm" value={draft.product} onChange={event => change('product', event.target.value)} options={products.map(row => ({ value: row.id, label: row.sku + ' · ' + row.name + (row.is_active ? '' : ' · Ngừng hoạt động') }))} />
        <div className="ui-form-grid">
          <Input required label="Số lượng" type="number" min={1} max={2147483647} step={1} value={draft.quantity} onChange={event => change('quantity', event.target.value)} />
          <Input label="Tài khoản thực hiện" readOnly value={user?.email ?? ''} />
        </div>
        <Input label="Mã phiếu" value={draft.reference} maxLength={120} onChange={event => change('reference', event.target.value)} hint="Không bắt buộc" />
        <Input label="Ghi chú" value={draft.note} maxLength={2000} onChange={event => change('note', event.target.value)} hint="Không bắt buộc, tối đa 2000 ký tự" />
      </fieldset>
      <section aria-live="polite" className="transfer-panel">
        <h2>Tồn kho dự kiến</h2><p>Số lượng thực tế được kiểm tra lại khi xác nhận chuyển kho.</p>
        {!draft.source || !draft.destination || !draft.product ? <p>Chọn hai kho và sản phẩm để xem ảnh hưởng tồn kho.</p> : !current ? <><p>Chưa xác định tồn kho</p>{stockError ? <><FeedbackMessage variant="error">{stockError}</FeedbackMessage><Button disabled={busy} onClick={() => setStockRetry(value => value + 1)} variant="secondary">Kiểm tra lại tồn kho</Button></> : <p>Đang kiểm tra tồn kho...</p>}</> : <div className="transfer-impact">{[
          { id: 'source', label: 'Kho nguồn', warehouse: draft.source, before: current.source, after: amount === null ? null : current.source - amount },
          { id: 'destination', label: 'Kho đích', warehouse: draft.destination, before: current.destination, after: amount === null ? null : current.destination + amount },
        ].map(row => <div key={row.id}><h3>{row.label}</h3><p>{name(Number(row.warehouse))}</p><dl><div><dt>Trước khi chuyển</dt><dd>{formatQuantity(row.before, product?.unit)}</dd></div><div><dt>Sau khi chuyển</dt><dd>{formatQuantity(row.after, product?.unit)}</dd></div></dl></div>)}</div>}
        {current && amount !== null && current.source < amount && <FeedbackMessage variant="warning">Số lượng chuyển vượt tồn kho nguồn dự kiến.</FeedbackMessage>}
        {current && amount !== null && current.destination > 2147483647 - amount && <FeedbackMessage variant="warning">Kho đích sẽ vượt giới hạn số lượng.</FeedbackMessage>}
      </section>
      <div className="transfer-actions"><Button disabled={busy} variant="secondary" onClick={() => navigate('/transfers')}>Hủy</Button><Button disabled={busy} type="submit">Xem lại chuyển kho</Button></div>
    </form>}
    {uncertain && <section className="transfer-panel transfer-recovery" aria-live="polite">
      <h2>Chưa xác định kết quả</h2><p>Yêu cầu có thể đã hoàn tất. Tra cứu hoặc gửi lại đúng yêu cầu để tránh chuyển trùng. Dữ liệu khôi phục chỉ được giữ khi biểu mẫu này còn mở; tải lại hoặc rời trang sẽ mất khóa yêu cầu.</p>
      {recoveryMessage && <p>{recoveryMessage}</p>}
      <div className="transfer-actions"><Button disabled={pending} onClick={() => void lookup()} variant="secondary">Tra cứu kết quả</Button><Button disabled={pending} onClick={() => { if (attemptRef.current) void send(attemptRef.current) }}>Thử lại cùng yêu cầu</Button></div>
      {pending && <p>Đang xử lý cùng yêu cầu...</p>}
    </section>}
    <ConfirmDialog open={review !== null} busy={pending} title="Xác nhận chuyển kho" confirmLabel="Xác nhận chuyển kho" onCancel={() => { if (!pendingLock.current) setReview(null) }} onConfirm={confirm} description="Tồn kho tại hai kho thay đổi ngay khi giao dịch hoàn tất.">
      {review && <div className="transfer-confirmation-copy"><p>{name(review.source_warehouse_id)} → {name(review.destination_warehouse_id)}</p><p>{product?.sku} · {product?.name}{product && !product.is_active ? ' · Ngừng hoạt động' : ''}</p><p>Số lượng: {formatQuantity(review.quantity, product?.unit)}</p></div>}
    </ConfirmDialog>
  </section>
}
