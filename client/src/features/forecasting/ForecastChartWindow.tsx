import { useEffect, useState } from 'react'
import { ApiError } from '../../api'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Select } from '../../shared/ui/Select'
import { ForecastComparisonChart, chartPoints } from './ForecastComparisonChart'
import { getForecastChart } from './api'
import type { Algorithm } from './types'

type Result = { key: string; points: ReturnType<typeof chartPoints>; seriesKey: string | null }

export function ForecastChartWindow({ token, context, runId, horizon, algorithm, algorithmLabel, unit }: {
  token: string; context: string; runId: string; horizon: number; algorithm: Algorithm; algorithmLabel: string; unit: string;
}) {
  const [chosenLead, setLead] = useState(1)
  const [retry, setRetry] = useState(0)
  const [result, setResult] = useState<Result | null>(null)
  const lead = chosenLead <= horizon ? chosenLead : 1
  useEffect(() => {
    if (chosenLead > horizon) setLead(1)
  }, [chosenLead, horizon])

  const key = JSON.stringify([context, token, runId, horizon, algorithm, lead, unit, retry])
  useEffect(() => {
    const controller = new AbortController()
    void getForecastChart(token, runId, horizon, algorithm, lead, controller.signal).then(response => {
      if (!controller.signal.aborted) setResult({
        key,
        points: chartPoints(response.items, response.series_key, horizon, algorithm, lead, unit),
        seriesKey: response.series_key,
      })
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted && !(cause instanceof ApiError && cause.staleSession)) {
        setResult({ key, points: null, seriesKey: null })
      }
    })
    return () => controller.abort()
  }, [key, token, runId, horizon, algorithm, lead, unit])

  const current = result?.key === key ? result : null
  return <div className="forecast-chart-window">
    {horizon > 1 && <div className="forecast-filters">
      <Select label="Bước dự báo của biểu đồ" value={lead}
        options={Array.from({ length: horizon }, (_, i) => ({ value: i + 1, label: `Ngày thứ ${i + 1}` }))}
        onChange={event => {
          const next = Number(event.target.value)
          if (Number.isInteger(next) && next >= 1 && next <= horizon) setLead(next)
        }} />
    </div>}
    {!current ? <p role="status">Đang tải biểu đồ dự báo…</p>
      : current.points === null ? <>
        <FeedbackMessage variant="warning">Không tải được biểu đồ. Bảng chi tiết vẫn có thể tra cứu riêng.</FeedbackMessage>
        <Button variant="secondary" onClick={() => setRetry(value => value + 1)}>Thử tải lại biểu đồ</Button>
      </>
        : <ForecastComparisonChart rows={current.points} seriesKey={current.seriesKey} unit={unit}
          horizon={horizon} algorithmLabel={algorithmLabel} lead={lead} />}
  </div>
}
