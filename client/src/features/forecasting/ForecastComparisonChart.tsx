import { useEffect, useId, useRef, useState } from 'react'
import type { Algorithm, Prediction } from './types'

const DAY = 86_400_000
const format = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 })
const validQuantity = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0
type Point = { day: number; prediction: number; actual: number | null; iso: string }


function parseDay(value: string) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const time = Date.parse(value)
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time / DAY : null
}

export function chartPoints(items: Prediction[], seriesKey: string | null, horizon: number, algorithm: Algorithm, lead: number, unit: string): Point[] | null {
  if (!Array.isArray(items) || items.length > 30 || (items.length === 0 ? seriesKey !== null : typeof seriesKey !== 'string' || !seriesKey.trim())) return null
  const points: Point[] = []
  for (const row of items) {
    if (!row) return null
    const day = parseDay(row.target_date), origin = parseDay(row.origin)
    if (day === null || origin === null || row.algorithm !== algorithm || row.horizon !== horizon || row.unit !== unit
      || row.lead !== lead || origin + lead !== day || row.series_key !== seriesKey
      || !validQuantity(row.prediction) || (row.actual !== null && !validQuantity(row.actual))
      || (points.length && points.at(-1)!.day >= day)) return null
    points.push({ day, iso: row.target_date, prediction: row.prediction, actual: row.actual })
  }
  return points
}

function segmentPaths(rows: Point[], key: 'prediction' | 'actual', x: (day: number) => number, y: (value: number) => number) {
  let last: number | undefined
  let path = ''
  for (const row of rows) {
    const value = row[key]
    if (value === null) { last = undefined; continue }
    path += `${last !== undefined && row.day - last === 1 ? 'L' : 'M'}${x(row.day).toFixed(2)},${y(value).toFixed(2)} `
    last = row.day
  }
  return path.trim()
}

export function ForecastComparisonChart({ rows, seriesKey, horizon, algorithmLabel, lead, unit }: {
  rows: Point[]; seriesKey: string | null; horizon: number; algorithmLabel: string; lead: number; unit: string;
}) {
  const root = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(654)
  const titleId = useId(), captionId = useId()
  useEffect(() => {
    const node = root.current
    if (!node) return
    const fit = () => {
      if (node.clientWidth > 0) setWidth(Math.max(220, Math.min(1100, node.clientWidth)))
    }
    fit()
    if (typeof ResizeObserver !== 'function') return
    const observer = new ResizeObserver(fit)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const first = rows[0], last = rows.at(-1)
  const labelUnit = unit === 'unit' ? 'đơn vị' : unit
  const height = 220, pad = { left: width < 430 ? 64 : 83, right: 42, top: 23, bottom: 43 }
  const actualCount = rows.filter(row => row.actual !== null).length
  const maxValue = Math.max(1, ...rows.flatMap(row => row.actual === null ? [row.prediction] : [row.prediction, row.actual]))
  const x = (date: number) => first && last && first.day !== last.day
    ? pad.left + (date - first.day) / (last.day - first.day) * (width - pad.left - pad.right)
    : (pad.left + width - pad.right) / 2
  const y = (value: number) => height - pad.bottom - value / maxValue * (height - pad.top - pad.bottom)
  const tickIndices = new Set(rows.length > 2 && width >= 420
    ? [0, Math.floor((rows.length - 1) / 2), rows.length - 1] : [0, rows.length - 1])
  const shortSeries = seriesKey && seriesKey.length > 20 ? seriesKey.slice(0, 16) + '…' : seriesKey

  return <figure className="forecast-chart" aria-labelledby={titleId}>
    <h3 id={titleId}>Biểu đồ dự báo và thực tế{rows.length > 0 ? `: ${rows.length} ngày đích gần nhất có dữ liệu` : ''}</h3>
    <p id={captionId}>{algorithmLabel} · Kỳ dự báo {horizon} ngày · Bước ngày thứ {lead} · Đơn vị: {labelUnit}.
      {first && last ? <> Từ {first.iso} đến {last.iso}; {rows.length} điểm dự báo, {actualCount} có thực tế.
        {' '}Chuỗi: <code title={seriesKey ?? undefined} className="forecast-chart__series">{shortSeries}</code>.</> : <> Chưa có điểm cho bước này.</>}</p>
    {first && last && <>
      <ul className="forecast-chart__legend" aria-label="Chú giải biểu đồ">
        <li><span className="forecast-chart__solid" aria-hidden="true" />Thực tế (nét liền)</li>
        <li><span className="forecast-chart__dashed" aria-hidden="true" />Dự báo (nét đứt)</li>
      </ul>
      <div className="forecast-chart__body" ref={root}>
        <svg role="img" aria-label="Biểu đồ dự báo và thực tế" aria-describedby={captionId} viewBox={`0 0 ${width} ${height}`}>
          {[0, maxValue / 2, maxValue].map(tick => <g key={tick}>
            <line className="forecast-chart__gridline" x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} />
            <text textAnchor="end" x={pad.left - 8} y={y(tick) + 4}>{format.format(tick)}</text>
          </g>)}
          <text y={13} x={pad.left}>{labelUnit}</text>
          {rows.filter((_row, index) => tickIndices.has(index)).map(row => <text key={row.day} textAnchor="middle" x={x(row.day)} y={height - 24}>{row.iso}</text>)}
          <text textAnchor="middle" x={width / 2} y={height - 5}>Ngày dự báo</text>
          {!!actualCount && <path className="forecast-chart__actual" d={segmentPaths(rows, 'actual', x, y)} />}
          {rows.map(row => row.actual !== null && <circle key={row.day} className="forecast-chart__actual-point" cx={x(row.day)} cy={y(row.actual)} r="3.7" data-actual={row.actual} />)}
          <path className="forecast-chart__prediction" d={segmentPaths(rows, 'prediction', x, y)} />
          {rows.map(row => <circle key={row.day} className="forecast-chart__prediction-point" cx={x(row.day)} cy={y(row.prediction)} r="2.1" />)}
        </svg>
      </div>
      <figcaption>{actualCount === 0 ? 'Cửa sổ này chưa có thực tế để so sánh.' : 'Khoảng trống trên đường thực tế là dữ liệu chưa có, không phải bằng 0.'} Biểu đồ và bảng phân trang được hiển thị độc lập.</figcaption>
    </>}
  </figure>
}
