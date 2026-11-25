import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../shared/ui/Button'
import { validatedEoq } from './eoqRead'
import { getForecastPilot } from './api'
import type { ForecastPilot, ReplenishmentRun } from './types'

type Loaded = { context: string; run: ReplenishmentRun; pilot: ForecastPilot | null }
const number = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 })
const day = (value: string) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value))
function nonnegative(value: string | null) {
  if (typeof value !== 'string' || !value.trim()) return null
  const output = Number(value)
  return Number.isFinite(output) && output >= 0 ? output : null
}

function matches(pilot: ForecastPilot, run: ReplenishmentRun) {
  const { manifest, entity } = run
  const binding = manifest.binding
  return !!binding && !!entity
    && /^frv1-[0-9a-f]{64}$/.test(pilot.forecast_run_id)
    && pilot.replenishment_run_id === manifest.run_id && pilot.forecast_run_id === manifest.forecast_run_id
    && pilot.product_id === binding.product_id && pilot.warehouse_id === binding.warehouse_id
    && pilot.product_id === entity.product_id && pilot.warehouse_id === entity.warehouse_id
    && pilot.sku === entity.sku && pilot.warehouse_code === entity.warehouse_code
    && pilot.unit === binding.unit && pilot.unit === manifest.unit && pilot.data_version === manifest.data_version
    && pilot.algorithm === 'xgboost' && pilot.lead_time === 7 && pilot.policy === 'proposed' && pilot.service_level === '0.90'
    && day(pilot.origin) && day(pilot.scenario_day)
    && typeof pilot.training_cutoff === 'string' && pilot.training_cutoff.length < 65 && Number.isFinite(Date.parse(pilot.training_cutoff))
    && nonnegative(pilot.forecast_during_lead_time) !== null && nonnegative(pilot.safety_stock) !== null
    && Number.isSafeInteger(pilot.rop) && pilot.rop >= 0 && Number.isSafeInteger(pilot.simulated_inventory_position)
    && pilot.threshold === (pilot.simulated_inventory_position <= pilot.rop ? 'at_or_below' : 'above')
}

function comparison(position: number, rop: number) {
  return {
    symbol: position < rop ? '<' : position === rop ? '=' : '>',
    verdict: position <= rop ? 'Cần xem xét đặt thêm' : 'Chưa chạm ngưỡng đặt thêm',
  }
}

function ThresholdExamples() {
  const [position, choose] = useState<13 | 14 | 15>(14)
  const { symbol, verdict } = comparison(position, 14)
  return <section className="replenishment-pilot__examples" aria-label="Ví dụ: So sánh với ngưỡng 14">
    <h3>Ví dụ: So sánh với ngưỡng 14</h3>
    <p>Ba mức tồn giả định để minh họa quy tắc. Chọn một mức không đổi kết quả mô phỏng đã lưu, tồn kho hoặc đơn hàng.</p>
    <div className="replenishment-pilot__example-actions" role="group" aria-label="Mức tồn minh họa">
      {([13, 14, 15] as const).map(value => <Button type="button" size="small" key={value}
        aria-pressed={position === value} variant={position === value ? 'primary' : 'secondary'} onClick={() => choose(value)}>
        Tồn {value}
      </Button>)}
    </div>
    <p role="status"><strong>{position} {symbol} 14</strong> · {verdict} trong ví dụ.</p>
  </section>
}

export function ForecastPilotPanel({ token, context, run }: { token: string; context: string; run: ReplenishmentRun }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    void getForecastPilot(token, run.manifest.run_id, controller.signal).then(result => {
      if (!controller.signal.aborted) setLoaded({
        context, run, pilot: result.state === 'ready' && result.pilot && matches(result.pilot, run) ? result.pilot : null,
      })
    }).catch(() => {
      if (!controller.signal.aborted) setLoaded({ context, run, pilot: null })
    })
    return () => controller.abort()
  }, [context, token, run])

  const current = loaded?.context === context && loaded.run === run ? loaded : null
  const pilot = current?.pilot ?? null
  const amount = (value: number) => `${number.format(value)} ${pilot?.unit === 'unit' ? 'đơn vị' : pilot?.unit}`
  const wape = nonnegative(pilot?.holdout_wape ?? null)
  const leadTimeMae = nonnegative(pilot?.holdout_lead_time_mae ?? null)
  const verifiedEoq = validatedEoq(run)
  const eoq = pilot?.eoq === verifiedEoq ? verifiedEoq : null
  const decision = pilot ? comparison(pilot.simulated_inventory_position, pilot.rop) : null
  const title = 'Demo: Từ dự báo đến điểm đặt lại'
  return <section className="replenishment-panel" aria-label={title}>
    <h2>{title}</h2>
    <p><strong>Dữ liệu giả lập cho một kho và một SKU.</strong> Không phải cảnh báo tồn thật hay đề xuất đặt hàng vận hành.</p>
    {!current ? <p role="status">Đang đối chiếu cặp kết quả demo…</p>
      : !pilot || !decision ? <p role="status">Chưa có cặp dự báo và bổ sung hàng demo đã xác minh cho kết quả này.</p>
        : <>
          <div className={`replenishment-pilot__verdict${pilot.threshold === 'at_or_below' ? ' replenishment-pilot__verdict--review' : ''}`}>
            <h3>{decision.verdict}</h3>
            <p><strong>{amount(pilot.simulated_inventory_position)} {decision.symbol} {amount(pilot.rop)}</strong>
              {' · Vị thế tồn mô phỏng so với điểm đặt lại (ROP).'}</p>
            <p><span>{pilot.simulated_inventory_position < pilot.rop ? 'Dưới điểm đặt lại: xem xét bổ sung.'
              : pilot.simulated_inventory_position === pilot.rop ? 'Bằng điểm đặt lại: xem xét bổ sung.'
                : 'Trên điểm đặt lại: chưa chạm ngưỡng.'}</span> Chỉ là kết luận trong mô phỏng, không tự tạo đơn mua.</p>
          </div>
          {pilot.rop === 14 && <ThresholdExamples />}
          <p>Kho <strong>{pilot.warehouse_code}</strong> · SKU <strong>{pilot.sku}</strong> · XGBoost · thời gian cung ứng giả định 7 ngày · mức phục vụ mô phỏng 90%.</p>
          <dl className="replenishment-facts">
            <div><dt>Ngày gốc dự báo</dt><dd>{pilot.origin}</dd></div>
            <div><dt>Ngày đối chiếu mô phỏng</dt><dd>{pilot.scenario_day}</dd></div>
            <div><dt>Mốc dữ liệu dùng để huấn luyện</dt><dd>{pilot.training_cutoff}</dd></div>
            <div><dt>Tổng lượng xuất dự báo trong 7 ngày</dt><dd>{amount(Number(pilot.forecast_during_lead_time))}</dd></div>
            <div><dt>Tồn an toàn mô phỏng</dt><dd>{amount(Number(pilot.safety_stock))}</dd></div>
          </dl>
          <p>ROP là tổng lượng xuất dự báo trong thời gian cung ứng cộng tồn an toàn, làm tròn lên.</p>
          <p>{typeof eoq === 'number' ? <>Lượng đặt tham khảo theo EOQ: <strong>{amount(eoq)}</strong> trong kịch bản.</>
            : 'Chưa đủ cơ sở hiển thị lượng đặt EOQ. Không coi tham số chi phí chưa xác định là 0.'}</p>
          {wape !== null && Number.isFinite(wape * 100) && <p>Sai lệch WAPE trên tập kiểm tra: {number.format(wape * 100)}%.</p>}
          {leadTimeMae !== null && <p>Sai lệch tuyệt đối trung bình của tổng 7 ngày trên tập kiểm tra: {amount(leadTimeMae)}.</p>}
          <p><Link to={`/forecasting/runs/${pilot.forecast_run_id}`}>Mở đúng kết quả dự báo nguồn</Link> · Cùng kho, SKU và đơn vị. Chọn XGBoost và khoảng 7 ngày để đối chiếu.</p>
          <section aria-label="Phân biệt các số liệu kho">
            <h3>Không dùng lẫn bốn số liệu</h3>
            <dl className="replenishment-facts">
              <div><dt>Vị thế tồn mô phỏng</dt><dd>Số trong kịch bản để so với ROP, không phải số tồn kho hiện tại.</dd></div>
              <div><dt>Tồn thực</dt><dd>Hàng đang có, được đọc từ API ở phần đối chiếu bên dưới; kho trong bản thử vẫn là kho kiểm thử.</dd></div>
              <div><dt>Đơn khách B2B chờ giao</dt><dd>Hàng khách đang chờ, không phải hàng nhập. Dự báo lượng xuất không gồm đơn B2B đang chờ và không trừ chúng thêm vào vị thế mô phỏng.</dd></div>
              <div><dt>Hàng từ nhà cung cấp đang về</dt><dd>Chưa có số liệu vận hành đã xác minh. Chỉ cột hàng đang đến trong bảng mô phỏng dùng giả định của kịch bản.</dd></div>
            </dl>
            <p>Lượng xuất thấp khi hết hàng không chứng minh nhu cầu khách thấp.</p>
          </section>
        </>}
  </section>
}
