import { useId } from 'react'
import type { ReactNode } from 'react'
import { formatQuantity } from '../../shared/lib/formatters'
import { EmptyState } from '../../shared/ui/EmptyState'
import type { Coordinate, HeatmapPoint, Position, RouteRead } from './types'

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

function MapFrame({ title, description, children }: { title: string; description: string; children: ReactNode }) {
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
    <path className="gis-map__grid" aria-hidden="true" d="M0 80h640M0 160h640M0 240h640M160 0v320M320 0v320M480 0v320" />
    {children}
  </svg>
}

export function RouteMap({ route }: { route: RouteRead }) {
  const origin = position(route.origin.coordinate)
  const destination = position(route.destination.coordinate)
  const road = route.geometry?.type === 'LineString' ? route.geometry.coordinates : []
  const sameNode = route.geometry?.type === 'Point' ? route.geometry.coordinates : null
  const connectors = route.geometry ? [route.origin_snap?.connector, route.destination_snap?.connector]
    .flatMap(connector => connector ? [connector.coordinates] : []) : []
  const points = [...road, ...connectors.flat(), ...[origin, destination, sameNode].filter(point => point !== null)]
  if (!points.length) return <EmptyState title="Chưa có điểm để vẽ sơ đồ" description="Chi tiết tuyến cho biết điểm nào thiếu tọa độ." />

  const place = project(points)
  const path = (coordinates: Position[]) => coordinates.map(point => place(point).join(',')).join(' ')
  const start = origin && place(origin)
  const end = destination && place(destination)
  const zero = sameNode && place(sameNode)
  return <MapFrame
    title="Sơ đồ tuyến đường"
    description={route.geometry
      ? 'Nét liền là đường đi, nét đứt nối điểm yêu cầu với nút đường. Chi tiết nằm bên dưới.'
      : 'Sơ đồ chỉ đánh dấu các điểm có tọa độ. Chi tiết nằm bên dưới.'}
  >
    {road.length > 0 && <polyline className="gis-map__road" points={path(road)} />}
    {connectors.map((connector, index) => <polyline className="gis-map__connector" key={index} points={path(connector)} />)}
    {start && <circle className="gis-map__origin" cx={start[0]} cy={start[1]} r="9" />}
    {end && <rect className="gis-map__destination" x={end[0] - 7} y={end[1] - 7} width="14" height="14" transform={`rotate(45 ${end[0]} ${end[1]})`} />}
    {zero && <circle className="gis-map__same-node" cx={zero[0]} cy={zero[1]} r="6" />}
  </MapFrame>
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
