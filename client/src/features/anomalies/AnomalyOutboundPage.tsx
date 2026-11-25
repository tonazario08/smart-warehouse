import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { formatQuantity } from '../../shared/lib/formatters'
import { can } from '../../shared/lib/permissions'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { PageHeader } from '../../shared/ui/PageHeader'
import { formatVietnamTime } from './alertReadability'
import { getAlertOutbound } from './api'
import type { AlertOutbound } from './types'
import '../../shared/styles/management.css'
import './anomalies.css'

type LinkState =
  | { kind: 'loading' | 'unlinked' | 'denied' | 'failed' }
  | { kind: 'verified'; voucher: AlertOutbound }

const loading: LinkState = { kind: 'loading' }
const denied: LinkState = { kind: 'denied' }
export const alertPath = (alertId: string) => '/anomalies/' + encodeURIComponent(alertId)

function validVoucher(value: AlertOutbound) {
  const positiveInteger = (field: number) => Number.isSafeInteger(field) && field > 0
  return value && positiveInteger(value.outbound_id) && positiveInteger(value.performed_by_id)
    && positiveInteger(value.quantity)
    && [value.product_name, value.product_sku, value.warehouse_code, value.warehouse_name, value.unit]
      .every(field => typeof field === 'string' && Boolean(field.trim()))
    && typeof value.occurred_at === 'string' && Boolean(formatVietnamTime(value.occurred_at))
}

function useAlertOutbound(alertId: string) {
  const { token, user } = useAuth()
  const allowed = Boolean(token && can(user?.role, 'anomaly:read') && can(user?.role, 'inventory:history:read'))
  const scope = JSON.stringify([token, user?.id, user?.role, alertId])
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ scope: string; attempt: number; state: LinkState }>()
  useEffect(() => {
    setResult(undefined)
    if (!allowed || !token || !alertId) return
    let active = true
    const update = (state: LinkState) => { if (active) setResult({ scope, attempt, state }) }
    void getAlertOutbound(token, alertId).then(voucher => {
      update(validVoucher(voucher) ? { kind: 'verified', voucher } : { kind: 'failed' })
    }).catch((error: unknown) => {
      if (error instanceof ApiError) {
        if (error.staleSession) return
        if (error.status === 403 || error.status === 401) return update(denied)
        if (error.status === 404) return update({ kind: 'unlinked' })
      }
      update({ kind: 'failed' })
    })
    return () => { active = false }
  }, [allowed, token, alertId, scope, attempt])
  return {
    state: !allowed ? denied : result?.scope === scope && result.attempt === attempt ? result.state : loading,
    retry: () => setAttempt(previous => previous + 1),
  }
}

function OutboundStatus({ kind, retry }: { kind: LinkState['kind']; retry: () => void }) {
  if (kind === 'loading') return <FeedbackMessage>Đang kiểm tra liên kết phiếu xuất...</FeedbackMessage>
  if (kind === 'unlinked') return <FeedbackMessage>Chưa liên kết được phiếu xuất đối chiếu.</FeedbackMessage>
  if (kind === 'denied') return <FeedbackMessage variant="warning">Bạn không có quyền xem phiếu xuất.</FeedbackMessage>
  if (kind === 'failed') return <>
    <FeedbackMessage variant="error">Không thể kiểm tra liên kết phiếu xuất lúc này.</FeedbackMessage>
    <Button onClick={retry} variant="secondary">Thử tải lại liên kết phiếu</Button>
  </>
  return null
}

export function AnomalyOutboundLink({ alertId }: { alertId: string }) {
  const { state, retry } = useAlertOutbound(alertId)
  return <section className="management-panel anomalies-panel">
    <h2>Phiếu xuất đối chiếu</h2>
    {state.kind === 'verified'
      ? <Link to={alertPath(alertId) + '/outbound'}>Mở phiếu xuất #{state.voucher.outbound_id}</Link>
      : <OutboundStatus kind={state.kind} retry={retry} />}
  </section>
}

export function AnomalyOutboundPage() {
  const { alertId = '' } = useParams()
  const { state, retry } = useAlertOutbound(alertId)
  const voucher = state.kind === 'verified' ? state.voucher : null
  return <section className="anomalies-page management-workspace">
    <PageHeader title="Phiếu xuất đối chiếu" description="Thông tin đối chiếu chỉ hiển thị khi xác minh được giao dịch nguồn."
      actions={<Link to={alertPath(alertId)}>Về chi tiết cảnh báo</Link>} />
    {voucher
      ? <section className="management-panel anomalies-panel">
        <h2>Phiếu xuất #{voucher.outbound_id}</h2>
        <FeedbackMessage variant="warning">Dữ liệu tổng hợp trong demo, không phải phiếu vận hành.</FeedbackMessage>
        <dl className="anomalies-facts">
          <div><dt>Sản phẩm</dt><dd>{voucher.product_name} ({voucher.product_sku})</dd></div>
          <div><dt>Kho xuất</dt><dd>{voucher.warehouse_name} ({voucher.warehouse_code})</dd></div>
          <div><dt>Số lượng xuất thực tế</dt><dd>{formatQuantity(voucher.quantity, voucher.unit)}</dd></div>
          <div><dt>Thời điểm xuất</dt><dd>{formatVietnamTime(voucher.occurred_at)} (giờ Việt Nam)</dd></div>
          <div><dt>Người thực xuất</dt><dd>Người dùng #{voucher.performed_by_id}</dd></div>
        </dl>
      </section>
      : <OutboundStatus kind={state.kind} retry={retry} />}
  </section>
}
