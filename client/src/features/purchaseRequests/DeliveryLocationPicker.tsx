import { useEffect, useRef, useState } from 'react'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import type { Coordinate } from '../gis/types'
import type { DeliveryMapData } from './deliveryMapData'
import { DeliveryPinMap } from './DeliveryPinMap'
import { geocodeDeliveryAddress, getDeliveryMap } from './api'
import type { DeliveryGeocodeCandidate, DeliveryLocation } from './types'

export type DeliveryLocationDraft = { address: string; latitude: string; longitude: string }
export const blankDeliveryDraft: DeliveryLocationDraft = { address: '', latitude: '', longitude: '' }

export function readDeliveryPoint(draft: DeliveryLocationDraft) {
  const latitude = Number(draft.latitude), longitude = Number(draft.longitude)
  return draft.latitude.trim() && draft.longitude.trim() && Number.isFinite(latitude) && Number.isFinite(longitude)
    && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null
}

const coordinateError = 'Nhập vĩ độ (-90 đến 90) và kinh độ (-180 đến 180) hợp lệ.'
type Search = { phase: 'idle' | 'loading' | 'no_match' | 'unavailable' } | { phase: 'matches'; candidates: DeliveryGeocodeCandidate[] }

function validCandidate(value: DeliveryGeocodeCandidate): boolean {
  return !!value && typeof value.label === 'string' && value.label.trim().length > 0 && value.label.length <= 500
    && Number.isFinite(value.latitude) && Number.isFinite(value.longitude)
    && Math.abs(value.latitude) <= 90 && Math.abs(value.longitude) <= 180
    && (value.precision === 'house_number' || value.precision === 'approximate')
}
function precisionText(value: DeliveryGeocodeCandidate) {
  return value.precision === 'approximate' ? 'Xấp xỉ theo đường, chưa xác định số nhà' : 'Điểm gắn số nhà OSM, không xác minh cổng giao hàng'
}

export function DeliveryLocationPicker({ token, draft, confirmed, disabled, onEdit, onConfirm }: {
  token: string | null
  draft: DeliveryLocationDraft
  confirmed: DeliveryLocation | null
  disabled: boolean
  onEdit: (draft: DeliveryLocationDraft) => void
  onConfirm: (location: DeliveryLocation) => void
}) {
  const [suggestion, setSuggestion] = useState<DeliveryGeocodeCandidate | null>(null)
  const [streetAcknowledged, setStreetAcknowledged] = useState(false)
  const [search, setSearch] = useState<Search>({ phase: 'idle' })
  const [map, setMap] = useState<DeliveryMapData | null>(null)
  const [mapLoading, setMapLoading] = useState(true)
  const [pasted, setPasted] = useState('')
  const activeSearch = useRef<AbortController | null>(null)
  const [accuracy, setAccuracy] = useState<number | null>(null)
  const [positioning, setPositioning] = useState(false)
  const [problem, setProblem] = useState('')
  const request = useRef(0)
  const latestDisabled = useRef(disabled)
  latestDisabled.current = disabled
  useEffect(() => () => {
    request.current += 1
    activeSearch.current?.abort()
  }, [])
  useEffect(() => {
    if (disabled) { request.current += 1; activeSearch.current?.abort(); setPositioning(false) }
  }, [disabled])
  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    setMapLoading(true)
    void getDeliveryMap(token, controller.signal).then(layer => {
      if (!controller.signal.aborted) setMap(layer.state === 'available' ? layer : null)
    }).catch(() => {
      if (!controller.signal.aborted) setMap(null)
    }).finally(() => {
      if (!controller.signal.aborted) setMapLoading(false)
    })
    return () => controller.abort()
  }, [token])

  const point = readDeliveryPoint(draft)
  const needsStreetAcknowledgment = suggestion?.precision === 'approximate' && !streetAcknowledged

  function setGeocodedCandidate(value: DeliveryGeocodeCandidate | null) {
    setSuggestion(value)
    setStreetAcknowledged(false)
  }

  function cancelWork() {
    request.current += 1
    activeSearch.current?.abort()
    activeSearch.current = null
    setSearch({ phase: 'idle' })
    setPositioning(false)
  }

  function edit(field: keyof DeliveryLocationDraft, value: string) {
    if (disabled) return
    cancelWork()
    setAccuracy(null); setPasted(''); setProblem('')
    // Changing the address requires a new pin; choosing a pin never rewrites the address.
    const next = field === 'address' ? { ...blankDeliveryDraft, address: value } : { ...draft, [field]: value }
    const nextPoint = readDeliveryPoint(next)
    if (field !== 'address' && suggestion?.precision === 'approximate' && (!nextPoint
      || (nextPoint.latitude === suggestion.latitude && nextPoint.longitude === suggestion.longitude))) {
      setStreetAcknowledged(false)
    } else {
      setGeocodedCandidate(null)
    }
    onEdit(next)
  }

  function manual(point: Coordinate) {
    if (disabled) return
    cancelWork()
    setAccuracy(null); setPasted(''); setProblem('')
    // Re-entering the same road reference is not a relocation.
    if (!suggestion || suggestion.latitude !== point.latitude || suggestion.longitude !== point.longitude) {
      setGeocodedCandidate(null)
    } else {
      setStreetAcknowledged(false)
    }
    onEdit({ ...draft, latitude: String(point.latitude), longitude: String(point.longitude) })
  }

  function applySuggestion(value: DeliveryGeocodeCandidate) {
    setAccuracy(null)
    setGeocodedCandidate(value)
    setProblem('')
    onEdit({ ...draft, latitude: String(value.latitude), longitude: String(value.longitude) })
  }

  function findAddress() {
    const address = draft.address.trim()
    if (disabled || !token || !address || Array.from(address).length > 300) return
    cancelWork(); setProblem(''); setAccuracy(null); setGeocodedCandidate(null); setPasted('')
    onEdit({ ...blankDeliveryDraft, address: draft.address })
    const controller = new AbortController()
    activeSearch.current = controller
    setSearch({ phase: 'loading' })
    void geocodeDeliveryAddress(token, address, controller.signal).then(result => {
      if (controller.signal.aborted || activeSearch.current !== controller || latestDisabled.current) return
      if (result.status === 'matches' && Array.isArray(result.candidates)) {
        const candidates = result.candidates.slice(0, 8).filter(validCandidate)
        if (candidates.length) {
          setSearch({ phase: 'matches', candidates })
          if (candidates.length === 1) applySuggestion(candidates[0])
          return
        }
      }
      setSearch({ phase: result.status === 'no_match' ? 'no_match' : 'unavailable' })
    }).catch(() => {
      if (!controller.signal.aborted && activeSearch.current === controller && !latestDisabled.current) {
        setSearch({ phase: 'unavailable' })
      }
    }).finally(() => {
      if (activeSearch.current === controller) activeSearch.current = null
    })
  }

  function pasteCoordinates() {
    const parts = pasted.trim().split(/\s*,\s*/)
    const parsed = parts.length === 2 ? readDeliveryPoint({ address: '', latitude: parts[0], longitude: parts[1] }) : null
    if (!parsed) { setProblem('Dán hai số theo thứ tự vĩ độ, kinh độ, ví dụ 10.77, 106.70.'); return }
    manual(parsed)
  }

  function locate() {
    if (disabled) return
    if (!navigator.geolocation || window.isSecureContext === false) {
      setProblem('Thiết bị hoặc trang này không hỗ trợ vị trí. Hãy đặt ghim hoặc nhập tọa độ.')
      return
    }
    cancelWork()
    const id = ++request.current
    const address = draft.address
    onEdit({ ...blankDeliveryDraft, address })
    setAccuracy(null); setGeocodedCandidate(null); setPasted(''); setProblem(''); setPositioning(true)
    const fail = (code?: number) => {
      if (request.current !== id || latestDisabled.current) return
      setPositioning(false)
      setProblem(code === 1 ? 'Bạn chưa cho phép dùng vị trí. Hãy đặt ghim hoặc nhập tọa độ.'
        : code === 3 ? 'Hết thời gian lấy vị trí. Hãy thử lại hoặc nhập tọa độ.'
          : 'Không xác định được vị trí hiện tại. Hãy đặt ghim hoặc nhập tọa độ.')
    }
    try {
      navigator.geolocation.getCurrentPosition(result => {
        if (request.current !== id || latestDisabled.current) return
        const { latitude, longitude, accuracy: meters } = result.coords
        const value = { address, latitude: String(latitude), longitude: String(longitude) }
        if (!readDeliveryPoint(value)) { fail(); return }
        setPositioning(false)
        setAccuracy(Number.isFinite(meters) && meters >= 0 ? Math.ceil(meters) : null)
        onEdit(value)
      }, cause => fail(cause.code), { enableHighAccuracy: false, maximumAge: 0, timeout: 10_000 })
    } catch {
      fail()
    }
  }

  function confirm() {
    if (disabled || positioning || search.phase === 'loading' || needsStreetAcknowledgment) return
    const address = draft.address.trim()
    if (!address || Array.from(address).length > 300) { setProblem('Nhập địa chỉ giao hàng từ 1 đến 300 ký tự.'); return }
    if (!point) { setProblem(coordinateError); return }
    setProblem('')
    onConfirm({ address, ...point })
  }

  return <section className="purchase-delivery-picker" aria-label="Xác nhận địa chỉ và điểm giao hàng">
    <Input label="Địa chỉ giao hàng" value={draft.address} maxLength={300} autoComplete="off"
      hint="Tra dữ liệu OpenStreetMap trong vùng TP. Hồ Chí Minh. Không phải mọi địa chỉ đều có kết quả."
      onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); findAddress() } }}
      onChange={event => edit('address', event.currentTarget.value)} />
    <Button type="button" variant="secondary" disabled={disabled || search.phase === 'loading' || !draft.address.trim()} onClick={findAddress}>Tìm địa chỉ</Button>
    {search.phase === 'loading' && <p role="status">Đang tìm địa chỉ trong dữ liệu nội bộ…</p>}
    {search.phase === 'no_match' && <p role="status">Không tìm thấy địa chỉ. Hãy đặt ghim, nhập tọa độ hoặc dùng vị trí hiện tại.</p>}
    {search.phase === 'unavailable' && <p role="status">Chưa có dữ liệu tra địa chỉ cho vùng này. Hãy đặt ghim, nhập tọa độ hoặc dùng vị trí hiện tại.</p>}
    {search.phase === 'matches' && search.candidates.length > 1 && <div>
      <p role="status">Có nhiều kết quả. Chọn một vị trí để xem ghim.</p>
      <ul className="purchase-delivery-samples" aria-label="Địa chỉ gợi ý">
        {search.candidates.map((value, index) => <li key={index}>
          <Button type="button" variant="secondary" size="small" aria-pressed={suggestion === value}
            onClick={() => { if (!disabled) applySuggestion(value) }}>
            {value.label} · {precisionText(value)}
          </Button>
        </li>)}
      </ul>
    </div>}
    {suggestion && <p role="status"><strong>{suggestion.label}</strong> · {precisionText(suggestion)}. Kiểm tra ghim rồi xác nhận.</p>}
    {suggestion?.precision === 'approximate' && !confirmed && <label className="purchase-delivery-road-ack">
      <input type="checkbox" checked={streetAcknowledged} disabled={disabled}
        onChange={event => setStreetAcknowledged(event.currentTarget.checked)} />
      <span>Tôi hiểu đây chỉ là điểm tham khảo trên đường, không phải số nhà hay cổng giao hàng.</span>
    </label>}
    <p className="purchase-nearest-method">Chỉ xin quyền vị trí khi bạn bấm nút. Vị trí hiện tại có thể khác điểm giao hàng.</p>
    <Button type="button" variant="secondary" disabled={disabled || positioning} onClick={locate}>Dùng vị trí hiện tại</Button>
    {positioning && <p role="status">Đang lấy vị trí thiết bị…</p>}
    {accuracy !== null && <p role="status">Độ chính xác ước tính: ±{accuracy} m. Kiểm tra lại trước khi xác nhận.</p>}
    <div className="ui-form-grid">
      <Input label="Vĩ độ điểm nhận" inputMode="decimal" value={draft.latitude} onChange={event => edit('latitude', event.currentTarget.value)} />
      <Input label="Kinh độ điểm nhận" inputMode="decimal" value={draft.longitude} onChange={event => edit('longitude', event.currentTarget.value)} />
    </div>
    <div className="purchase-actions">
      <Input label="Dán tọa độ (vĩ độ, kinh độ)" autoComplete="off" value={pasted} onKeyDown={event => {
        if (event.key === 'Enter') { event.preventDefault(); pasteCoordinates() }
      }} onChange={event => setPasted(event.currentTarget.value)} />
      <Button type="button" variant="secondary" disabled={disabled || !pasted.trim()} onClick={pasteCoordinates}>
        Dùng tọa độ đã dán
      </Button>
    </div>
    {mapLoading ? <p className="purchase-nearest-method">Đang tải bản đồ công cộng…</p>
      : <DeliveryPinMap layer={map} point={point} disabled={disabled} onStart={cancelWork} onPick={manual} />}
    {point && <>
      <p className="purchase-delivery-pin" aria-label="Ghim điểm giao đang chọn">
        <span aria-hidden="true">◆</span> Ghim {point.latitude}, {point.longitude}
      </p>

    </>}
    <div className="purchase-actions">
      <Button type="button" variant="secondary" disabled={disabled || positioning || search.phase === 'loading' || needsStreetAcknowledgment} onClick={confirm}>Xác nhận điểm giao</Button>
      {(draft.address || point || draft.latitude || draft.longitude || positioning) && <Button type="button" variant="secondary"
        disabled={disabled} onClick={() => { cancelWork(); setGeocodedCandidate(null); setAccuracy(null); setPasted(''); setProblem(''); onEdit(blankDeliveryDraft) }}>
        Xóa điểm giao
      </Button>}
    </div>
    {confirmed && <p role="status">Đã xác nhận điểm giao: {confirmed.address}</p>}
    {problem && <FeedbackMessage variant="warning">{problem}</FeedbackMessage>}
  </section>
}
