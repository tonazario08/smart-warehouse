import { useId } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { formatQuantity } from '../../shared/lib/formatters'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import type { Coordinate, HeatmapPoint, Position, RouteRead, SnapshotMetadata, StreetLayer, WarehouseOptions, WarehouseRead } from './types'

const WIDTH = 640
const HEIGHT = 320
const PADDING = 36

function position(point: Coordinate | null): Position | null {
  return point === null ? null : [point.longitude, point.latitude]
}

function project(points: Position[]) {
  let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity
  for (const [longitude, latitude] of points) {
    west = Math.min(west, longitude)
    east = Math.max(east, longitude)
    south = Math.min(south, latitude)
    north = Math.max(north, latitude)
  }
  const midLongitude = (west + east) / 2
  const midLatitude = (south + north) / 2
  const longitudeScale = Math.max(Math.cos(midLatitude * Math.PI / 180), 0.01)
  const spanX = Math.max((east - west) * longitudeScale, 0.0001)
  const spanY = Math.max(north - south, 0.0001)
  const scale = Math.min((WIDTH - 2 * PADDING) / spanX, (HEIGHT - 2 * PADDING) / spanY)
  return ([longitude, latitude]: Position): Position => [
    WIDTH / 2 + (longitude - midLongitude) * longitudeScale * scale,
    HEIGHT / 2 - (latitude - midLatitude) * scale,
  ]
}

type Bounds = SnapshotMetadata['bounds']
type Projection = {
  place: (point: Position) => Position
  unplace: (point: Position) => Position
  contains: (point: Position) => boolean
}

/** One north-up, local WGS84 projection for the area border, roads, and markers. */
export function boundedProjection(bounds: Bounds): Projection | null {
  if (!Array.isArray(bounds) || bounds.length !== 4 || !bounds.every(Number.isFinite)) return null
  const [west, south, east, north] = bounds
  if (west < -180 || east > 180 || south < -90 || north > 90 || west >= east || south >= north) return null
  const lon = (west + east) / 2, lat = (south + north) / 2
  const lonScale = Math.max(Math.cos(lat * Math.PI / 180), 0.01)
  const scale = Math.min((WIDTH - 2 * PADDING) / ((east - west) * lonScale), (HEIGHT - 2 * PADDING) / (north - south))
  if (!Number.isFinite(scale)) return null
  return {
    place: ([x, y]) => [WIDTH / 2 + (x - lon) * lonScale * scale, HEIGHT / 2 - (y - lat) * scale],
    unplace: ([x, y]) => [lon + (x - WIDTH / 2) / (scale * lonScale), lat - (y - HEIGHT / 2) / scale],
    contains: ([x, y]) => x >= west && x <= east && y >= south && y <= north,
  }
}

export function positionFromViewport(x: number, y: number, width: number, height: number, projection: Projection): Position | null {
  if (width <= 0 || height <= 0) return null
  const scale = Math.min(width / WIDTH, height / HEIGHT)
  const point = projection.unplace([(x - (width - WIDTH * scale) / 2) / scale, (y - (height - HEIGHT * scale) / 2) / scale])
  return projection.contains(point) ? point.map(value => Number(value.toFixed(7))) as Position : null
}

export function matchedStreetLayer(layer: StreetLayer | null, snapshot: SnapshotMetadata | null): StreetLayer | null {
  if (!snapshot || snapshot.dataset_class !== 'public_osm' || layer?.state !== 'available'
      || !layer.bounds || !snapshot.bounds || layer.snapshot_id !== snapshot.snapshot_id
      || !layer.attribution || layer.license_url !== 'https://www.openstreetmap.org/copyright'
      || !Array.isArray(layer.segments) || !layer.segments.length || layer.segments.length > 2400) return null
  const bounds = layer.bounds
  const projection = boundedProjection(bounds)
  if (!projection || !bounds.every((value, index) => value === snapshot.bounds[index])
      || !layer.segments.every(segment => Array.isArray(segment) && segment.length === 2 && segment.every(
        point => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite) && projection.contains(point),
      ))) return null
  return layer
}

function StreetLines({ layer, place }: { layer: StreetLayer; place: Projection['place'] }) {
  // One path rather than up to 2,400 DOM nodes; each subpath ends at a source graph vertex.
  const path = layer.segments.map(([a, b]) => 'M' + place(a).join(',') + 'L' + place(b).join(',')).join('')
  return <path className="gis-map__streets" d={path} aria-hidden="true" />
}

function WarehouseLegend() {
  return <ul className="gis-legend gis-map-legend" aria-label="Chú giải bản đồ kho">
    <li><i className="gis-symbol gis-symbol--destination" aria-hidden="true" />Điểm đến</li>
    <li><i className="gis-symbol gis-symbol--enough" aria-hidden="true" />Kho đủ tồn</li>
    <li><i className="gis-symbol gis-symbol--short" aria-hidden="true" />Kho thiếu tồn</li>
    <li><i className="gis-symbol gis-symbol--route" aria-hidden="true" />Tuyến A*</li>
  </ul>
}

type StockKind = 'enough' | 'short'
function stockKinds(options: WarehouseOptions | null) {
  const kinds = new Map<number, StockKind>()
  if (!options) return kinds
  for (const row of [...options.ranked, ...options.geographic_only, ...options.excluded]) {
    const amount = row.available_quantity
    if (amount === null || !Number.isFinite(amount)) continue
    if (amount >= options.quantity) kinds.set(row.warehouse.warehouse_id, 'enough')
    else if ('reason' in row && row.reason === 'insufficient_stock') kinds.set(row.warehouse.warehouse_id, 'short')
  }
  return kinds
}

function routeParts(route: RouteRead | null) {
  return {
    road: route?.geometry?.type === 'LineString' ? route.geometry.coordinates : [],
    sameNode: route?.geometry?.type === 'Point' ? route.geometry.coordinates : null,
    connectors: route?.geometry ? [route.origin_snap?.connector, route.destination_snap?.connector]
      .flatMap(connector => connector ? [connector.coordinates] : []) : [],
  }
}

function routeBounds(bounds: Bounds, points: Position[]): Bounds | null {
  if (!points.length) return null
  const [west, south, east, north] = bounds
  const axis = (index: 0 | 1, low: number, high: number): [number, number] => {
    const values = points.map(point => point[index])
    const min = Math.min(...values), max = Math.max(...values)
    const padding = Math.max((max - min) * 0.15, (high - low) * 0.025)
    return [Math.max(low, min - padding), Math.min(high, max + padding)]
  }
  const [left, right] = axis(0, west, east)
  const [bottom, top] = axis(1, south, north)
  return left < right && bottom < top && (right - left < east - west || top - bottom < north - south)
    ? [left, bottom, right, top] : null
}

export function DestinationPicker({ snapshot, layer, warehouses, selected, targetLabel, onPick, options, route, onClear, hasDraft, zoom, setZoom }: {
  snapshot: SnapshotMetadata | null
  layer: StreetLayer | null
  warehouses: WarehouseRead[]
  selected: Coordinate | null
  targetLabel?: string
  onPick?: (coordinate: Coordinate) => void
  options: WarehouseOptions | null
  route: RouteRead | null
  onClear?: () => void
  hasDraft: boolean
  zoom: boolean
  setZoom: (zoom: boolean) => void
}) {
  const clip = useId()
  const coverage = snapshot?.bounds
  const full = coverage ? boundedProjection(coverage) : null
  const currentRoute = snapshot && route?.snapshot_state === 'available'
    && route.snapshot?.snapshot_id === snapshot.snapshot_id
    && options?.snapshot?.snapshot_id === snapshot.snapshot_id ? route : null
  const { road, sameNode, connectors } = routeParts(currentRoute)
  const points = [...road, ...connectors.flat(), ...(sameNode ? [sameNode] : [])]
  if (currentRoute?.geometry) {
    for (const place of [currentRoute.origin, currentRoute.destination]) {
      const endpoint = position(place.coordinate)
      if (endpoint) points.push(endpoint)
    }
  }
  const drawable = points.length > 0 && full !== null && points.every(full.contains)
  const zoomBounds = drawable && coverage ? routeBounds(coverage, points) : null
  const bounds = (zoom ? zoomBounds : null) ?? coverage
  const projection = bounds ? boundedProjection(bounds) : null
  const clear = onClear && <Button type="button" variant="secondary" size="small" disabled={!hasDraft} onClick={onClear}>Xóa điểm đến</Button>
  if (!snapshot || !bounds || !projection) return <div className="gis-picker">
    {onPick && <p className="gis-muted">Chưa có vùng chọn trên sơ đồ. Hãy nhập vĩ độ và kinh độ.</p>}
    {clear}
  </div>

  const [west, south, east, north] = bounds
  const [left, top] = projection.place([west, north])
  const [right, bottom] = projection.place([east, south])
  const target = position(selected)
  const marker = target && projection.contains(target) ? projection.place(target) : null
  const kinds = stockKinds(options)
  const locations = options
    ? [...new Map([...options.ranked, ...options.geographic_only, ...options.excluded].map(row => [row.warehouse.warehouse_id, row.warehouse])).values()]
    : warehouses
  const path = (coordinates: Position[]) => coordinates.map(point => projection.place(point).join(',')).join(' ')
  const pointsOnMap = locations.flatMap(warehouse => {
    const { longitude, latitude } = warehouse
    if (longitude === null || latitude === null || !projection.contains([longitude, latitude])) return []
    const kind = kinds.get(warehouse.warehouse_id)
    if (options && !kind) return []
    const [x, y] = projection.place([longitude, latitude])
    return [{ warehouse, kind, x, y }]
  })

  // Prioritize the selected destination and a few readable warehouse labels, not every crowded point.
  const occupied: Array<[number, number, number, number]> = []
  const textSpace = (title: string, x: number, y: number) => {
    const width = Math.min(235, title.length * 8 + 8)
    const left = x + 10 + width < WIDTH - 8 ? x + 10 : x - width - 10
    const top = y < 26 ? y + 10 : y - 22
    const box: [number, number, number, number] = [left, top, left + width, top + 20]
    if (left < 0 || occupied.some(other => box[0] < other[2] && box[2] > other[0] && box[1] < other[3] && box[3] > other[1])) return null
    occupied.push(box)
    return [left, top + 16]
  }
  const targetText = marker && targetLabel ? textSpace(targetLabel, ...marker) : null
  const warehouseLabels = pointsOnMap.flatMap(({ warehouse, x, y }) => {
    if (occupied.length >= 8) return []
    const full = warehouse.code + ' · ' + warehouse.name
    const label = full.length > 27 ? full.slice(0, 26) + '…' : full
    const at = textSpace(label, x, y)
    return at ? [{ id: warehouse.warehouse_id, label, full, short: warehouse.code, at }] : []
  })

  function choose(event: MouseEvent<SVGSVGElement>) {
    const svg = event.currentTarget
    const rect = svg.getBoundingClientRect()
    const point = positionFromViewport(
      event.clientX - rect.left - svg.clientLeft, event.clientY - rect.top - svg.clientTop,
      svg.clientWidth || rect.width, svg.clientHeight || rect.height, projection!,
    )
    if (point && onPick) onPick({ longitude: point[0], latitude: point[1] })
  }

  return <figure className="gis-picker">
    {onPick && <p className="gis-muted">Chạm để chọn điểm đến hoặc nhập tọa độ bằng bàn phím.</p>}
    <svg className={onPick ? 'gis-map gis-map--picker' : 'gis-map'} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
      aria-label={onPick ? (layer ? 'Chọn điểm đến trên nền đường OpenStreetMap' : 'Chọn điểm đến trên sơ đồ tọa độ') : 'Vị trí kho và điểm đến'}
      data-map-frame={zoom && zoomBounds ? 'route' : 'coverage'} onClick={onPick ? choose : undefined}>
      <defs><clipPath id={clip}><rect x={left} y={top} width={right - left} height={bottom - top} /></clipPath></defs>
      <rect className="gis-map__bounds" x={left} y={top} width={right - left} height={bottom - top} />
      <g clipPath={`url(#${clip})`}>
        {layer && <StreetLines layer={layer} place={projection.place} />}
        {drawable && road.length > 0 && <polyline className="gis-map__road" points={path(road)} />}
        {drawable && connectors.map((connector, index) => <polyline className="gis-map__connector" key={index} points={path(connector)} />)}
        {drawable && sameNode && <circle className="gis-map__same-node" cx={projection.place(sameNode)[0]} cy={projection.place(sameNode)[1]} r="5" />}
      </g>
      {pointsOnMap.map(({ warehouse, kind, x, y }) => {
        const title = <title>{warehouse.code + ' · ' + warehouse.name + (kind ? (kind === 'enough' ? ' · Đủ tồn' : ' · Thiếu tồn') : '')}</title>
        if (kind === 'enough') return <rect key={warehouse.warehouse_id} className="gis-map__stock-enough" x={x - 5} y={y - 5} width="10" height="10">{title}</rect>
        if (kind === 'short') return <polygon key={warehouse.warehouse_id} className="gis-map__stock-short" points={`${x},${y - 7} ${x + 7},${y + 6} ${x - 7},${y + 6}`}>{title}</polygon>
        return <circle key={warehouse.warehouse_id} className="gis-map__origin" cx={x} cy={y} r="4">{title}</circle>
      })}
      {marker && <rect className="gis-map__destination" x={marker[0] - 6} y={marker[1] - 6} width="12" height="12"
        transform={`rotate(45 ${marker[0]} ${marker[1]})`} />}
      {warehouseLabels.map(({ id, label, short, full, at }) => <g key={id} className="gis-map-warehouse-label">
        <title>{full}</title>
        <text className="gis-map-label-wide" x={at[0]} y={at[1]} aria-hidden="true">{label}</text>
        <text className="gis-map-label-narrow" x={at[0]} y={at[1]} aria-hidden="true">{short}</text>
      </g>)}
      {targetText && <text className="gis-map-target-label" x={targetText[0]} y={targetText[1]} aria-hidden="true">{targetLabel}</text>}
    </svg>
    <WarehouseLegend />
    <div className="gis-map-actions">
      {clear}
      {zoomBounds && <Button type="button" variant="secondary" size="small" onClick={() => setZoom(!zoom)}>
        {zoom ? 'Về khung vùng' : 'Xem gần tuyến'}
      </Button>}
    </div>
    <figcaption className="gis-muted">
      {layer ? <>Nền đường tham khảo · <a href={layer.license_url ?? undefined} referrerPolicy="no-referrer">{layer.attribution}</a></>
        : snapshot.dataset_class === 'synthetic_fixture' ? 'Sơ đồ tọa độ mô phỏng, không có nền đường phố.'
        : 'Sơ đồ tọa độ, không có nền đường phố.'}
      {target && !marker && <> Điểm nhập nằm ngoài vùng hiển thị.</>}
    </figcaption>
    <p className="visually-hidden" role="status">{selected && !targetLabel ? `Điểm đến: ${selected.latitude}, ${selected.longitude}` : ''}</p>
  </figure>
}

function MapFrame({ title, description, children, grid = true }: { title: string; description: string; children: ReactNode; grid?: boolean }) {
  const id = useId()
  return <svg
    className="gis-map"
    viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
    role="img"
    aria-labelledby={`${id}-title`}
    aria-describedby={`${id}-description`}
  >
    <title id={`${id}-title`}>{title}</title>
    <desc id={`${id}-description`}>{description}</desc>
    {grid && <path className="gis-map__grid" aria-hidden="true" d="M0 80h640M0 160h640M0 240h640M160 0v320M320 0v320M480 0v320" />}
    {children}
  </svg>
}

export function RouteMap({ route, streetLayer = null }: { route: RouteRead; streetLayer?: StreetLayer | null }) {
  const origin = position(route.origin.coordinate)
  const destination = position(route.destination.coordinate)
  const { road, sameNode, connectors } = routeParts(route)
  const points = [...road, ...connectors.flat(), ...[origin, destination, sameNode].filter(point => point !== null)]
  if (!points.length) return <EmptyState title="Chưa có điểm để vẽ sơ đồ" description="Chi tiết tuyến cho biết điểm nào thiếu tọa độ." />

  const layer = route.snapshot_state === 'available' ? matchedStreetLayer(streetLayer, route.snapshot) : null
  const bounded = layer?.bounds ? boundedProjection(layer.bounds) : null
  const showStreets = bounded !== null && points.every(bounded.contains)
  const place = showStreets ? bounded.place : project(points)
  const path = (coordinates: Position[]) => coordinates.map(point => place(point).join(',')).join(' ')
  const start = origin && place(origin)
  const end = destination && place(destination)
  const zero = sameNode && place(sameNode)
  return <>
    <MapFrame
    title={showStreets ? 'Tuyến trên nền đường OpenStreetMap' : 'Sơ đồ tuyến đường'}
    grid={!showStreets}
    description={route.geometry
      ? 'Nét liền là đường đi, nét đứt nối điểm yêu cầu với nút đường. Chi tiết nằm bên dưới.'
      : 'Sơ đồ chỉ đánh dấu các điểm có tọa độ. Chi tiết nằm bên dưới.'}
  >
    {showStreets && layer && <StreetLines layer={layer} place={place} />}
    {road.length > 0 && <polyline className="gis-map__road" points={path(road)} />}
    {connectors.map((connector, index) => <polyline className="gis-map__connector" key={index} points={path(connector)} />)}
    {start && <circle className="gis-map__origin" cx={start[0]} cy={start[1]} r="9" />}
    {end && <rect className="gis-map__destination" x={end[0] - 7} y={end[1] - 7} width="14" height="14" transform={`rotate(45 ${end[0]} ${end[1]})`} />}
    {zero && <circle className="gis-map__same-node" cx={zero[0]} cy={zero[1]} r="6" />}
    </MapFrame>
    {!showStreets && <p className="gis-muted">{route.snapshot?.dataset_class === 'synthetic_fixture'
      ? 'Sơ đồ tuyến mô phỏng, không có nền đường phố.' : 'Sơ đồ tuyến, không có nền đường phố.'}</p>}
  </>
}

type HeatBand = { id: 'zero' | 'low' | 'medium' | 'high'; from: number; to: number }

function heatBands(maximum: number): HeatBand[] {
  const low = Math.ceil(maximum / 3)
  const medium = Math.ceil(2 * maximum / 3)
  const bands: HeatBand[] = [
    { id: 'zero', from: 0, to: 0 },
    { id: 'low', from: 1, to: low },
    { id: 'medium', from: low + 1, to: medium },
    { id: 'high', from: medium + 1, to: maximum },
  ]
  return bands.filter(band => band.from <= band.to)
}

export function HeatmapMap({ points, unit }: { points: HeatmapPoint[]; unit: string }) {
  const located = points.flatMap(({ warehouse, fulfilled_quantity }) => {
    const { latitude, longitude } = warehouse
    if (latitude === null || longitude === null) return []
    const coordinate: Position = [longitude, latitude]
    return [{ warehouse, fulfilled_quantity, coordinate }]
  })
  if (!located.length) return <EmptyState title="Chưa có điểm kho trên bản đồ" description="Xem số liệu trong bảng theo kho." />

  const maximum = located.reduce((max, point) => Math.max(max, point.fulfilled_quantity), 0)
  const bands = heatBands(maximum)
  const place = project(located.map(point => point.coordinate))
  return <>
    <MapFrame title="Bản đồ lượng xuất theo kho" description="Các điểm tô màu theo lượng xuất đã ghi nhận. Bảng bên dưới cung cấp số liệu từng kho.">
      {located.map(({ warehouse, fulfilled_quantity, coordinate }) => {
        const [x, y] = place(coordinate)
        const band = bands.find(item => fulfilled_quantity <= item.to)
        return <circle
          key={warehouse.warehouse_id}
          className="gis-map__heat-point"
          data-heat-band={band?.id}
          cx={x}
          cy={y}
          r="12"
        ><title>{warehouse.name + ' · ' + formatQuantity(fulfilled_quantity, unit)}</title></circle>
      })}
    </MapFrame>
    <ul className="gis-legend" aria-label="Chú giải lượng xuất">
      {bands.map(({ id, from, to }) => <li key={id}>
        <span aria-hidden="true" className="gis-legend__swatch" data-heat-band={id} />
        {from === to ? formatQuantity(to, unit) : `${formatQuantity(from)} đến ${formatQuantity(to, unit)}`}
      </li>)}
    </ul>
  </>
}
