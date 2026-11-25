import { useEffect, useRef, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/ApiError'
import {
  browserSessionStorage,
  clearPendingMovement,
  movementFingerprint,
  newMovementKey,
  normalizeMovementInput,
  readPendingMovement,
  savePendingMovement,
  type PendingMovement,
} from '../../shared/api/movementIdempotency'
import { FormFieldError } from '../../shared/ui/FormFieldError'
import { useAuth } from '../auth/useAuth'
import { createInventoryApi, inboundKeys, inventoryLookup, outboundKeys, stockKeys } from './api'
import { movementSchema, type MovementFormInput, type MovementFormValues } from './schemas'
import type { MovementInput } from './types'

export type MovementDirection = 'inbound' | 'outbound'

export function MovementForm({ direction }: { direction: MovementDirection }) {
  const { client, user } = useAuth()
  const api = createInventoryApi(client)
  const cache = useQueryClient()
  const products = useQuery({ queryKey: inventoryLookup.products, queryFn: api.listProducts, retry: false })
  const warehouses = useQuery({ queryKey: inventoryLookup.warehouses, queryFn: api.listWarehouses, retry: false })
  const lookupFailed = products.isError || warehouses.isError
  const lookupEmpty = !products.isPending && !warehouses.isPending && (!products.data?.items.length || !warehouses.data?.items.length)
  const [success, setSuccess] = useState<string | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [recoveryMessage, setRecoveryMessage] = useState('')
  const pendingGuard = useRef(false)
  const attemptRef = useRef<PendingMovement | null>(null)
  const restoredRef = useRef('')
  const form = useForm<MovementFormValues, unknown, MovementFormInput>({
    resolver: zodResolver(movementSchema),
    defaultValues: { warehouse_id: '', product_id: '', quantity: '', reference: '', note: '' },
  })

  // Reload recovery (D-05): reuse the stored key for an outcome-unknown
  // create instead of generating a fresh key that would duplicate it.
  // Wait for the lookup options so the restored values match a real option.
  useEffect(() => {
    if (!user?.id || !products.isSuccess || !warehouses.isSuccess) return
    const scope = user.id + ':' + direction
    if (restoredRef.current === scope) return
    restoredRef.current = scope
    const stored = readPendingMovement(browserSessionStorage(), user.id, direction)
    if (!stored) return
    attemptRef.current = stored
    setUncertain(true)
    setRecoveryMessage('Phiếu này chưa xác định kết quả sau lần gửi trước. Thử lại cùng yêu cầu để tránh tạo trùng.')
    form.reset({
      warehouse_id: String(stored.input.warehouse_id),
      product_id: String(stored.input.product_id),
      quantity: String(stored.input.quantity),
      reference: stored.input.reference ?? '',
      note: stored.input.note ?? '',
    })
  }, [direction, form, products.isSuccess, user?.id, warehouses.isSuccess])

  async function retryAttempt() {
    const attempt = attemptRef.current
    if (!attempt || pendingGuard.current) return
    pendingGuard.current = true
    setSuccess(null)
    try {
      const create = direction === 'inbound' ? api.createInbound : api.createOutbound
      const movement = await create(attempt.input, attempt.key)
      if (user?.id) clearPendingMovement(browserSessionStorage(), user.id, direction)
      attemptRef.current = null
      setUncertain(false)
      setRecoveryMessage('')
      await Promise.all([
        cache.invalidateQueries({ queryKey: stockKeys.all }),
        cache.invalidateQueries({ queryKey: direction === 'inbound' ? inboundKeys.all : outboundKeys.all }),
        cache.invalidateQueries({ queryKey: ['transactions'] }),
        cache.invalidateQueries({ queryKey: ['dashboard', 'stats'] }),
      ])
      form.reset({ warehouse_id: '', product_id: '', quantity: '', reference: '', note: '' })
      setSuccess(`${direction === 'inbound' ? 'Inbound' : 'Outbound'} recorded. Movement #${movement.id}.`)
    } catch (error) {
      if (error instanceof ApiError && error.status < 500 && error.status !== 408) {
        if (user?.id) clearPendingMovement(browserSessionStorage(), user.id, direction)
        attemptRef.current = null
        setUncertain(false)
        form.setError('root', { type: 'server', message: error.code === 'UNEXPECTED_RESPONSE' ? error.message : `${error.code}: ${error.message}` })
      } else {
        setRecoveryMessage(error instanceof ApiError ? error.message : 'Không thể xác định kết quả. Yêu cầu có thể đã được ghi nhận.')
      }
    } finally {
      pendingGuard.current = false
    }
  }

  function discardAttempt() {
    if (user?.id) clearPendingMovement(browserSessionStorage(), user.id, direction)
    attemptRef.current = null
    setUncertain(false)
    setRecoveryMessage('')
    form.setError('root', { type: 'server', message: 'Đã hủy khôi phục. Kiểm tra danh sách phiếu trước khi tạo phiếu mới để tránh trùng.' })
  }

  async function submit(input: MovementInput) {
    if (pendingGuard.current || uncertain) return
    pendingGuard.current = true
    setSuccess(null)
    form.clearErrors()
    try {
      const normalized = normalizeMovementInput(input)
      const fingerprint = movementFingerprint(normalized)
      let attempt = attemptRef.current
      if (!attempt || attempt.fingerprint !== fingerprint) {
        attempt = { key: newMovementKey(), direction, fingerprint, input: normalized }
        attemptRef.current = attempt
        if (user?.id) savePendingMovement(browserSessionStorage(), user.id, direction, attempt.key, normalized)
      }
      const create = direction === 'inbound' ? api.createInbound : api.createOutbound
      const movement = await create(attempt.input, attempt.key)
      if (user?.id) clearPendingMovement(browserSessionStorage(), user.id, direction)
      attemptRef.current = null
      setUncertain(false)
      const historyKey = direction === 'inbound' ? inboundKeys.all : outboundKeys.all
      await Promise.all([
        cache.invalidateQueries({ queryKey: stockKeys.all }),
        cache.invalidateQueries({ queryKey: historyKey }),
        cache.invalidateQueries({ queryKey: ['transactions'] }),
        cache.invalidateQueries({ queryKey: ['dashboard', 'stats'] }),
      ])
      form.reset({ warehouse_id: '', product_id: '', quantity: '', reference: '', note: '' })
      setSuccess(`${direction === 'inbound' ? 'Inbound' : 'Outbound'} recorded. Movement #${movement.id}.`)
    } catch (error) {
      if (error instanceof ApiError && (error.status >= 500 || error.status === 408)) {
        setUncertain(true)
        setRecoveryMessage(error.message)
      } else if (error instanceof ApiError) {
        if (user?.id) clearPendingMovement(browserSessionStorage(), user.id, direction)
        attemptRef.current = null
        setUncertain(false)
        const fieldMap = { warehouse_id: 'warehouse_id', product_id: 'product_id', quantity: 'quantity', reference: 'reference', note: 'note' } as const
        for (const [serverField, formField] of Object.entries(fieldMap) as [keyof typeof fieldMap, keyof MovementFormValues][]) {
          const value = error.fields?.[serverField]
          if (value) form.setError(formField, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
        }
        form.setError('root', { type: 'server', message: error.code === 'UNEXPECTED_RESPONSE' ? error.message : `${error.code}: ${error.message}` })
      } else {
        setUncertain(true)
        setRecoveryMessage(error instanceof Error ? error.message : 'Movement could not be recorded.')
      }
    } finally {
      pendingGuard.current = false
    }
  }

  const fieldError = (field: keyof MovementFormValues, id: string) => <FormFieldError id={id} message={form.formState.errors[field]?.message} />
  const directionName = direction === 'inbound' ? 'Inbound' : 'Outbound'

  return <section className={`movement-manifest movement-manifest-${direction}`} aria-labelledby={`${direction}-form-heading`}>
    <header><h3 id={`${direction}-form-heading`}>{direction === 'inbound' ? 'Receiving manifest' : 'Dispatch manifest'}</h3><p>{direction === 'inbound' ? 'Record goods arriving at a warehouse.' : 'Record goods leaving available stock.'}</p></header>
    {success && <p className="form-success" role="status">{success}</p>}
    {products.isPending && <p className="async-state" role="status">Loading product options…</p>}
    {warehouses.isPending && <p className="async-state" role="status">Loading warehouse options…</p>}
    {products.isError && <p className="async-state async-state-error" role="alert">{products.error instanceof Error ? products.error.message : 'Product lookup could not be loaded.'} <button type="button" className="quiet" aria-label="Retry product lookup" onClick={() => void products.refetch()}>Retry product lookup</button></p>}
    {warehouses.isError && <p className="async-state async-state-error" role="alert">{warehouses.error instanceof Error ? warehouses.error.message : 'Warehouse lookup could not be loaded.'} <button type="button" className="quiet" aria-label="Retry warehouse lookup" onClick={() => void warehouses.refetch()}>Retry warehouse lookup</button></p>}
    {!products.isPending && !products.isError && !products.data?.items.length && <p className="async-state async-state-empty">No products are available for movements.</p>}
    {!warehouses.isPending && !warehouses.isError && !warehouses.data?.items.length && <p className="async-state async-state-empty">No warehouses are available for movements.</p>}
    <form className="movement-fields" aria-label={`${directionName} movement`} noValidate onSubmit={form.handleSubmit(submit)}>
      <label>{directionName} warehouse
        <select {...form.register('warehouse_id')} aria-label={`Warehouse for ${direction}`} aria-invalid={Boolean(form.formState.errors.warehouse_id)} aria-describedby={form.formState.errors.warehouse_id ? `${direction}-warehouse-error` : undefined} disabled={!warehouses.isSuccess || !warehouses.data.items.length || form.formState.isSubmitting}>
          <option value="">Select warehouse</option>{warehouses.data?.items.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>)}
        </select>{fieldError('warehouse_id', `${direction}-warehouse-error`)}
      </label>
      <label>{directionName} product
        <select {...form.register('product_id')} aria-label={`Product for ${direction}`} aria-invalid={Boolean(form.formState.errors.product_id)} aria-describedby={form.formState.errors.product_id ? `${direction}-product-error` : undefined} disabled={!products.isSuccess || !products.data.items.length || form.formState.isSubmitting}>
          <option value="">Select product</option>{products.data?.items.map((product) => <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>)}
        </select>{fieldError('product_id', `${direction}-product-error`)}
      </label>
      <label>{directionName} quantity
        <input aria-label={`${directionName} quantity`} type="number" min="1" step="1" inputMode="numeric" {...form.register('quantity')} aria-invalid={Boolean(form.formState.errors.quantity)} aria-describedby={form.formState.errors.quantity ? `${direction}-quantity-error` : undefined} />
        {fieldError('quantity', `${direction}-quantity-error`)}
      </label>
      <label>Reference<input aria-label="Reference" {...form.register('reference')} maxLength={120} aria-invalid={Boolean(form.formState.errors.reference)} aria-describedby={form.formState.errors.reference ? `${direction}-reference-error` : undefined} />{fieldError('reference', `${direction}-reference-error`)}</label>
      <label>Note<textarea aria-label="Note" {...form.register('note')} maxLength={2000} rows={2} aria-invalid={Boolean(form.formState.errors.note)} aria-describedby={form.formState.errors.note ? `${direction}-note-error` : undefined} />{fieldError('note', `${direction}-note-error`)}</label>
      {form.formState.errors.root?.message && <p className="form-error" role="alert">{form.formState.errors.root.message}</p>}
      <button type="submit" disabled={form.formState.isSubmitting || uncertain || lookupFailed || lookupEmpty || !products.isSuccess || !warehouses.isSuccess}>
        {form.formState.isSubmitting ? `Recording ${direction}…` : `Record ${direction}`}
      </button>
    </form>
    {uncertain && attemptRef.current && <section className="movement-recovery" aria-live="polite">
      <h2>Chưa xác định kết quả</h2>
      <p>Yêu cầu có thể đã được ghi nhận. Thử lại cùng yêu cầu để tránh tạo trùng phiếu.</p>
      {recoveryMessage && <p>{recoveryMessage}</p>}
      <div className="ui-form-actions">
        <button type="button" onClick={() => void retryAttempt()}>Thử lại cùng yêu cầu</button>
        <button type="button" className="quiet" onClick={discardAttempt}>Hủy khôi phục và tạo phiếu mới</button>
      </div>
    </section>}
  </section>
}
