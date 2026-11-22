import { useEffect, useState } from 'react'
import { ApiError } from '../../api'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { getPurchaseDeliveryLocation } from './api'
import type { DeliveryLocation } from './types'

type Result = { phase: 'loading' } | { phase: 'error'; retry: boolean } | { phase: 'success'; location: DeliveryLocation | null }

export function PurchaseDeliveryDetails({ token, requestId }: { token: string; requestId: number }) {
  const [result, setResult] = useState<Result>({ phase: 'loading' })
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setResult({ phase: 'loading' })
    void getPurchaseDeliveryLocation(token, requestId, controller.signal).then(value => {
      if (controller.signal.aborted) return
      if (value.delivery_location === null) {
        setResult({ phase: 'success', location: null })
      } else if (value.delivery_location && typeof value.delivery_location.address === 'string'
        && Number.isFinite(value.delivery_location.latitude) && Number.isFinite(value.delivery_location.longitude)) {
        setResult({ phase: 'success', location: value.delivery_location })
      } else {
        setResult({ phase: 'error', retry: true })
      }
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted && !(cause instanceof ApiError && cause.staleSession)) {
        setResult({ phase: 'error', retry: !(cause instanceof ApiError && [401, 403, 404].includes(cause.status)) })
      }
    })
    return () => controller.abort()
  }, [token, requestId, version])

  return <section className="purchase-panel" aria-label="Điểm giao đã xác nhận">
    <h2>Điểm giao đã xác nhận</h2>
    {result.phase === 'loading' ? <p role="status">Đang tải điểm giao…</p>
      : result.phase === 'error' ? <>
        <FeedbackMessage variant="warning">Không thể xem thông tin điểm giao cho đơn này.</FeedbackMessage>
        {result.retry && <Button variant="secondary" onClick={() => setVersion(value => value + 1)}>Thử tải lại điểm giao</Button>}
      </> : result.location ? <dl className="purchase-facts">
        <div><dt>Địa chỉ giao hàng</dt><dd>{result.location.address}</dd></div>
        <div><dt>Tọa độ đã xác nhận</dt><dd>{result.location.latitude}, {result.location.longitude}</dd></div>
      </dl> : <p>Đơn này chưa có điểm giao đã xác nhận.</p>}
  </section>
}
