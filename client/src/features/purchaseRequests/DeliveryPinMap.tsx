import { useEffect, useId, useMemo, useRef } from 'react'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coordinate, Position } from '../gis/types'
import { Button } from '../../shared/ui/Button'
import { validatePublicBasemap } from './deliveryMapData'
import type { DeliveryBasemap, DeliveryMapData } from './deliveryMapData'

type PinProps = {
  point: Coordinate | null
  disabled: boolean
  onStart: () => void
  onPick: (point: Coordinate) => void
}

function latLng([longitude, latitude]: Position): L.LatLngTuple { return [latitude, longitude] }
function pointAt(location: L.LatLng): Coordinate {
  return { latitude: +location.lat.toFixed(7), longitude: +location.lng.toFixed(7) }
}

function vectorLabels(data: DeliveryBasemap) {
  const places = data.places.map(row => ({ name: row.name, point: row.point, priority: row.kind === 'landmark' ? 0 : 1 }))
  const roads = data.roads.flatMap(row => row.name
    ? [{ name: row.name, point: row.points[Math.floor(row.points.length / 2)], priority: 2 }] : [])
  return [...places, ...roads].sort((a, b) => a.priority - b.priority)
}

function LeafletPinMap({ data, ...props }: PinProps & { data: DeliveryBasemap }) {
  const hint = useId()
  const host = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const marker = useRef<L.Marker | null>(null)
  const draggingPin = useRef(false)
  const latest = useRef(props)
  latest.current = props
  const [west, south, east, north] = data.bounds
  const bounds = useMemo(() => L.latLngBounds([south, west], [north, east]), [west, south, east, north])
  const inBounds = (point: Coordinate) => bounds.contains([point.latitude, point.longitude])
  const outside = props.point && !inBounds(props.point)

  useEffect(() => {
    const container = host.current
    if (!container) return
    const local = L.map(container, {
      attributionControl: false, zoomControl: false, keyboard: false, scrollWheelZoom: false,
      preferCanvas: typeof CanvasRenderingContext2D !== 'undefined',
      doubleClickZoom: false, minZoom: 10, maxZoom: 19, maxBounds: bounds.pad(0.08), maxBoundsViscosity: 1,
      zoomAnimation: false, markerZoomAnimation: false,
    })
    map.current = local
    const viewport = () => local.fitBounds(bounds, { padding: [12, 12], animate: false })
    viewport()
    const areas = data.areas.map(row => L.polygon(row.ring.map(latLng), {
      interactive: false, color: row.kind === 'water' ? '#9ac9de' : '#a4c68a',
      fillColor: row.kind === 'water' ? '#b7dcea' : '#cfdfaf', fillOpacity: 0.92, weight: 1,
    }))
    L.layerGroup(areas).addTo(local)
    L.polyline(data.roads.map(row => row.points.map(latLng)), { interactive: false, color: '#7b8997', opacity: 0.72, weight: 1.3 }).addTo(local)
    const labels = L.layerGroup().addTo(local)
    const availableLabels = vectorLabels(data)

    function renderLabels() {
      labels.clearLayers()
      const viewport = local.getBounds()
      const zoom = local.getZoom()
      const occupied: Array<{ x: number; y: number; width: number }> = []
      const names = new Set<string>()
      for (const label of availableLabels) {
        const location = latLng(label.point)
        if (!viewport.contains(location) || names.has(label.name)) continue
        const { x, y } = local.latLngToContainerPoint(location)
        const width = Math.min(112, Math.max(26, label.name.length * 3.1))
        if (occupied.some(item => Math.abs(item.y - y) < 19 && Math.abs(item.x - x) < item.width + width)) continue
        const text = document.createElement('span')
        text.textContent = label.name
        labels.addLayer(L.marker(location, { keyboard: false, interactive: false, icon: L.divIcon({
          className: 'purchase-delivery-leaflet-label', html: text, iconSize: [0, 0], iconAnchor: [0, 0],
        }) }))
        occupied.push({ x, y, width })
        names.add(label.name)
        if (occupied.length >= (zoom >= 15 ? 46 : 22)) break
      }
    }

    local.on('click', (event: L.LeafletMouseEvent) => {
      if (latest.current.disabled || !bounds.contains(event.latlng)) return
      latest.current.onStart()
      latest.current.onPick(pointAt(event.latlng))
    })
    local.on('moveend zoomend', renderLabels)
    renderLabels()
    const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(() => local.invalidateSize({ pan: false, animate: false })) : null
    resize?.observe(container)
    return () => {
      resize?.disconnect()
      local.remove()
      map.current = null
      marker.current = null
      draggingPin.current = false
    }
  }, [bounds, data])

  useEffect(() => {
    const local = map.current
    if (!local || draggingPin.current) return
    const point = props.point
    if (!point || outside) {
      marker.current?.remove()
      marker.current = null
      return
    }
    const position: L.LatLngTuple = [point.latitude, point.longitude]
    if (!marker.current) {
      const pin = L.marker(position, { draggable: !props.disabled, keyboard: false, bubblingMouseEvents: false,
        alt: 'Ghim điểm giao', icon: L.divIcon({ className: 'purchase-delivery-leaflet-pin', html: '', iconSize: [25, 25], iconAnchor: [12, 12] }),
      }).addTo(local)
      pin.on('dragstart', () => {
        if (latest.current.disabled) return
        draggingPin.current = true
        latest.current.onStart()
      })
      pin.on('dragend', () => {
        draggingPin.current = false
        const position = pin.getLatLng()
        if (!latest.current.disabled && bounds.contains(position)) latest.current.onPick(pointAt(position))
        else if (latest.current.point) pin.setLatLng([latest.current.point.latitude, latest.current.point.longitude])
      })
      marker.current = pin
    } else {
      marker.current.setLatLng(position)
    }
    if (props.disabled) marker.current.dragging?.disable()
    else marker.current.dragging?.enable()
    if (!local.getBounds().contains(position)) local.panTo(position, { animate: false })
  }, [bounds, data, outside, props.disabled, props.point])

  function zoom(amount: number) { map.current?.zoomIn(amount, { animate: false }) }
  function reframe() { map.current?.fitBounds(bounds, { padding: [12, 12], animate: false }) }
  function focusPin() {
    const local = map.current
    if (!local || !props.point || outside) return
    local.setView([props.point.latitude, props.point.longitude], Math.max(15, local.getZoom()), { animate: false })
  }

  return <figure className="purchase-delivery-leaflet-frame">
    <div ref={host} className="purchase-delivery-leaflet" data-delivery-map-renderer="leaflet" role="application"
      aria-label="Bản đồ chọn ghim giao hàng" aria-describedby={hint} tabIndex={0}
      onKeyDown={event => {
        const local = map.current
        if (!local) return
        if (['+', '=', '-', 'Home'].includes(event.key)) {
          event.preventDefault()
          if (event.key === 'Home') reframe()
          else zoom(event.key === '-' ? -1 : 1)
          return
        }
        if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
        event.preventDefault()
        const dx = event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowRight' ? 1 : 0
        const dy = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0
        if (event.shiftKey) { local.panBy([dx * 70, dy * 70], { animate: false }); return }
        if (props.disabled) return
        const base = props.point && !outside ? L.latLng(props.point.latitude, props.point.longitude) : local.getCenter()
        const shifted = local.containerPointToLatLng(local.latLngToContainerPoint(base).add([dx * 16, dy * 16]))
        const next = { latitude: Math.max(south, Math.min(north, +shifted.lat.toFixed(7))), longitude: Math.max(west, Math.min(east, +shifted.lng.toFixed(7))) }
        props.onStart(); props.onPick(next)
      }} />
    <div className="purchase-actions" aria-label="Điều khiển bản đồ">
      <Button type="button" size="small" variant="secondary" onClick={() => zoom(1)}>Phóng to</Button>
      <Button type="button" size="small" variant="secondary" onClick={() => zoom(-1)}>Thu nhỏ</Button>
      <Button type="button" size="small" variant="secondary" onClick={reframe}>Về vùng phủ</Button>
      {props.point && !outside && <Button type="button" size="small" variant="secondary" onClick={focusPin}>Về ghim</Button>}
    </div>
    <figcaption id={hint}>Chạm bản đồ hoặc kéo ghim để chọn điểm giao. Phím mũi tên dịch ghim; Shift + mũi tên dịch bản đồ.
      {' · '}<a href="https://www.openstreetmap.org/copyright" referrerPolicy="no-referrer" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a> · ODbL 1.0.
      {outside && <strong> Điểm đang chọn nằm ngoài vùng bản đồ. Kiểm tra tọa độ trước khi xác nhận.</strong>}
    </figcaption>
  </figure>
}

export function DeliveryPinMap({ layer, ...props }: PinProps & { layer: DeliveryMapData | null }) {
  const data = useMemo(() => validatePublicBasemap(layer), [layer])
  return data ? <LeafletPinMap data={data} {...props} />
    : <p className="purchase-nearest-method">Chưa có bản đồ nền OSM có nhãn. Nhập hoặc dán tọa độ, hoặc dùng vị trí hiện tại.</p>
}
