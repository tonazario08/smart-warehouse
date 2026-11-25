import { useId, useRef } from 'react'
import { Input } from '../../shared/ui/Input'
import type { PublicLandmark } from './publicLandmarks'

function plainSearch(value: string) {
  return value.normalize('NFD').toLowerCase().replace(/\p{M}/gu, '').replaceAll('đ', 'd')
    .replace(/[^a-z0-9]+/g, ' ').trim()
}

export function LandmarkPicker({ candidates, query, landmark, onSearch, onSelect }: {
  candidates: readonly PublicLandmark[]
  query: string
  landmark: PublicLandmark | null
  onSearch: (query: string) => void
  onSelect: (point: PublicLandmark) => void
}) {
  const panel = useRef<HTMLDivElement>(null)
  const hint = useId()
  if (!candidates.length) return <p className="gis-muted">
    Chưa có danh sách địa danh công cộng đã kiểm cho bản đồ này. Hãy chọn trên sơ đồ hoặc nhập tọa độ.
  </p>

  const normalized = plainSearch(query)
  const words = normalized.split(' ').filter(Boolean)
  const suggestions = candidates.filter(point => {
    const terms = [point.name, ...point.aliases].map(plainSearch)
    return words.every(word => terms.some(term => term.includes(word)))
  }).slice(0, 6)
  return <div className="gis-landmark-picker" ref={panel}>
    <Input label="Tìm địa danh" type="search" placeholder="Nhập tên, có thể không dấu"
      autoComplete="off" maxLength={100} aria-describedby={hint} value={query}
      onKeyDown={event => {
        if (event.key === 'Enter') event.preventDefault()
      }}
      onChange={event => onSearch(event.currentTarget.value)} />
    <p id={hint} className="gis-muted">Chọn tên từ danh sách hoặc đặt điểm trên bản đồ. Ghim là vị trí tham khảo, không phải lối vào.</p>
    {!landmark && (suggestions.length > 0 ? <ul className="gis-landmark-suggestions" aria-label="Địa danh công cộng gợi ý">
      {suggestions.map(point => <li key={point.id}>
        <button type="button" onClick={() => { onSelect(point); panel.current?.querySelector('input')?.focus() }}>{point.name}</button>
      </li>)}
    </ul> : <p role="status" className="gis-muted">Không tìm thấy địa danh. Hãy thử tên khác hoặc chọn vị trí thủ công.</p>)}
    {landmark && <p className="gis-landmark-confirmation" role="status">
      <strong>Điểm đến: {landmark.name}</strong>
      <span>{landmark.latitude}, {landmark.longitude} · <a href={landmark.sourceUrl} referrerPolicy="no-referrer" target="_blank" rel="noreferrer">{landmark.sourceLabel}</a></span>
    </p>}
  </div>
}
