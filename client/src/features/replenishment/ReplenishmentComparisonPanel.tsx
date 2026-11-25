import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { useReplenishmentPosition } from '../orderAnalytics/OrderAnalyticsPanels'
import type { AnalyticsTarget, SimulationSelection } from '../orderAnalytics/types'
import type { ReplenishmentAlert } from './alert'

const fmt = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 })

export function ReplenishmentComparisonPanel({ token, context, target, selection, runId, sku, unit, warehouseCode,
  alert, waiting, sourceError, traceError, referenceRop, verifiedEoq }: {
  token: string; context: string; target: AnalyticsTarget; selection: SimulationSelection;
  runId: string; sku: string; unit: string; warehouseCode: string; alert: ReplenishmentAlert | null;
  waiting: boolean; sourceError: string; traceError: string; referenceRop: number | null; verifiedEoq: number | null;
}) {
  const current = useReplenishmentPosition({ token, context, target, view: 'operational', selection })
  const demo = useReplenishmentPosition({ token, context, target: selection.reference_date ? target : null, view: 'demo', selection: { ...selection, run_id: runId } })
  const facts = current.data
  const demoData = demo.data
  const canonical = facts && facts.sku === sku && facts.unit === unit ? facts : null
  const canonicalReady = canonical && typeof canonical.on_hand === 'number' && Number.isSafeInteger(canonical.on_hand)
    && canonical.on_hand >= 0
  const actualReference = alert?.status === 'above' || alert?.status === 'reorder' ? alert : null
  const actualOK = canonicalReady && actualReference && actualReference.onHand === canonical.on_hand
    && actualReference.unit === unit && actualReference.sku === sku && actualReference.warehouseCode === warehouseCode
    && actualReference.day === selection.reference_date && actualReference.rop === referenceRop
  const demoOK = canonicalReady && demoData?.dataset_class === 'fixture' && demoData.state === 'available'
    && demoData.run_id === runId && demoData.unit === unit && demoData.sku === sku
    && demoData.rop_date === selection.reference_date && demoData.rop === referenceRop && referenceRop !== null
    && demoData.on_hand === canonical.on_hand && demoData.open_quantity === canonical.open_quantity
    && demoData.projected_quantity === canonical.projected_quantity
    && typeof canonical.open_quantity === 'number' && Number.isSafeInteger(canonical.open_quantity) && canonical.open_quantity >= 0
    && typeof canonical.projected_quantity === 'number' && Number.isSafeInteger(canonical.projected_quantity)
  const unverified = current.error || (facts && !canonical)
  const noStock = canonical && !canonicalReady
  const articleUnit = unit === 'unit' ? 'đơn vị' : unit
  const amount = (value: number | null) => typeof value !== 'number' || !Number.isFinite(value)
    ? 'Chưa có dữ liệu' : `${fmt.format(value)} ${articleUnit}`
  const validOperational = canonicalReady && canonical.state === 'available'
    && canonical.rop !== null && Number.isFinite(canonical.rop) && canonical.rop >= 0
    && canonical.projected_quantity !== null
    && Boolean(canonical.dataset_class && !['fixture', 'research'].includes(canonical.dataset_class))

  return <section className="replenishment-panel replenishment-alert" aria-label="Cảnh báo bổ sung hàng demo">
    <h2>Đối chiếu ngưỡng bổ sung hàng (demo)</h2>
    <p>Kho <strong>{warehouseCode}</strong> · SKU <strong>{sku}</strong>
      {selection.reference_date && referenceRop !== null && <> · Ngày ROP tham chiếu <strong>{selection.reference_date}</strong>: <strong>{amount(referenceRop)}</strong></>}.</p>
    {unverified ? <FeedbackMessage variant="warning">Thiếu dữ liệu để đối chiếu. Chưa xác minh được số tồn cho kho và SKU này.</FeedbackMessage>
      : noStock ? <FeedbackMessage variant="warning">Chưa có bản ghi tồn kho. Không thể kết luận cả hai phép đối chiếu.</FeedbackMessage>
        : !canonical ? <FeedbackMessage>Đang kiểm tra tồn kho, danh mục và ROP của ngày mô phỏng...</FeedbackMessage>
          : <>
            <dl className="replenishment-facts" aria-label="Số liệu tồn dùng chung">
              <div><dt>Tồn hiện tại</dt><dd>{amount(canonical.on_hand)}</dd></div>
              <div><dt>Đơn khách B2B chờ giao</dt><dd>{amount(canonical.open_quantity)}</dd></div>
              <div><dt>Tồn dự kiến = tồn hiện tại − lượng chờ</dt><dd>{amount(canonical.projected_quantity)}</dd></div>
            </dl>
            <div className="replenishment-comparison__decisions">
              <section aria-label="Tồn hiện tại so với ROP">
                <h3>Tồn hiện tại so với ROP</h3>
                {actualOK ? <FeedbackMessage variant={actualReference.status === 'reorder' ? 'warning' : undefined}>
                  {actualReference.status === 'reorder' ? 'Tồn thực tại hoặc dưới ngưỡng ROP mô phỏng' : 'Tồn kho trên ngưỡng ROP tham chiếu'}.
                </FeedbackMessage> : <p>{sourceError || traceError
                  ? 'Thiếu dữ liệu để đối chiếu tồn hiện tại.' : waiting ? 'Đang kiểm tra tồn kho, danh mục và ROP của ngày mô phỏng...'
                    : actualReference ? 'Hai nguồn tồn hiện tại không khớp, chưa kết luận.' : 'Chưa xác minh được ROP và tồn hiện tại cùng nguồn.'}</p>}
              </section>
              <section aria-label="Tồn dự kiến so với ROP">
                <h3>Tồn dự kiến so với ROP</h3>
                {demoOK ? <FeedbackMessage variant={canonical.projected_quantity! <= referenceRop! ? 'warning' : undefined}>
                  {canonical.projected_quantity! <= referenceRop! ? 'Tồn dự kiến tại hoặc dưới ROP mô phỏng.' : 'Tồn dự kiến trên ROP mô phỏng.'}
                </FeedbackMessage> : <p>{demo.error ? 'Không đọc được đối chiếu tồn dự kiến.'
                  : !selection.reference_date ? 'Chưa có ngày mô phỏng để đối chiếu.'
                    : !demoData || demoData.state === 'computing' ? 'Đang kiểm tra tồn dự kiến.'
                      : demoData.state === 'available' ? 'Số liệu hoặc tham chiếu tồn dự kiến không khớp, chưa kết luận.'
                        : 'Chưa xác minh được tồn dự kiến với ROP của cùng ngày mô phỏng.'}</p>}
              </section>
            </div>
            {((actualOK && actualReference.status === 'reorder') || demoOK) && verifiedEoq !== null
              && ((actualOK && actualReference.status === 'reorder' && actualReference.eoq === verifiedEoq)
                || (demoOK && demoData.eoq === verifiedEoq))
              && <p>Lượng đặt tham khảo theo EOQ: <strong>{amount(verifiedEoq)}</strong>.</p>}
            {actualOK && actualReference.status === 'reorder' && actualReference.eoq === null
              && !(demoOK && demoData.eoq === verifiedEoq && verifiedEoq !== null) && <p>Chưa đủ cơ sở hiển thị lượng đặt EOQ.</p>}
            {validOperational
              ? <p>ROP vận hành: {amount(canonical.rop)}.{canonical.recommendation && ' Đề xuất xem xét bổ sung.'}</p>
              : canonical.reason_code === 'OPERATIONAL_ROP_NOT_FOUND' && <p>Chưa có ROP vận hành được xác minh.</p>}
          </>}
    {(current.error || demo.error) && <Button variant="secondary" onClick={() => { current.retry(); demo.retry() }}>Thử lại phân tích đơn</Button>}
    <p className="replenishment-alert-disclosure">Dữ liệu demo/fixture, chỉ dùng trình diễn; lead time {selection.lead_time} ngày là giả định của kịch bản.
      ROP của ngày mô phỏng không phải ngưỡng đã phê duyệt cho vận hành thực tế. Không tự đặt hàng.</p>
  </section>
}
