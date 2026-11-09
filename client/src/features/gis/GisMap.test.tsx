import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { HeatmapMap, RouteMap } from './GisMap'
import type { HeatmapPoint, RouteRead, WarehouseRead } from './types'

const warehouse = { warehouse_id: 1, code: 'A', name: 'Kho A', latitude: 10.75, longitude: 106.65 }
const route: RouteRead = {
  stock_data_class: 'operational', stock_fixture_label: null,
  snapshot_state: 'available', snapshot: null,
  origin: { kind: 'warehouse', coordinate: { latitude: 10.75, longitude: 106.65 }, warehouse, request_id: null },
  destination: { kind: 'coordinate', coordinate: { latitude: 10.76, longitude: 106.66 }, warehouse: null, request_id: null },
  origin_snap: {
    node_id: 123, coordinates: [106.651, 10.75], distance_mm: 109133,
    connector: { type: 'LineString', coordinates: [[106.65, 10.75], [106.651, 10.75]] },
  },
  destination_snap: null,
  geometry: { type: 'LineString', coordinates: [[106.651, 10.75], [106.66, 10.76]] },
  distance_mm: 1500000, reason: null, transfer: null,
}

it('draws the road and snap connector as separate paths without a tile layer', () => {
  render(<RouteMap route={route} />)
  const map = screen.getByRole('img', { name: 'Sơ đồ tuyến đường' })
  expect(map.querySelectorAll('polyline.gis-map__road')).toHaveLength(1)
  expect(map.querySelectorAll('polyline.gis-map__connector')).toHaveLength(1)
  expect(map.querySelector('image')).toBeNull()
})

it('renders zero distance as one point and leaves missing routes unconnected', () => {
  const view = render(<RouteMap route={{
    ...route, distance_mm: 0, geometry: { type: 'Point', coordinates: [106.651, 10.75] },
  }} />)
  const map = screen.getByRole('img', { name: 'Sơ đồ tuyến đường' })
  expect(map.querySelector('circle.gis-map__same-node')).toBeTruthy()
  expect(map.querySelector('polyline.gis-map__road')).toBeNull()
  view.rerender(<RouteMap route={{ ...route, geometry: null, distance_mm: null, reason: 'no_route' }} />)
  expect(map.querySelectorAll('polyline')).toHaveLength(0)
})

it('uses the same heat bands in markers and legend and omits coordinates that are missing', () => {
  const row = (id: number, quantity: number, location: Partial<WarehouseRead> = {}): HeatmapPoint => ({
    warehouse: { ...warehouse, warehouse_id: id, ...location },
    fulfilled_quantity: quantity, transaction_count: 1,
  })
  render(<HeatmapMap points={[
    row(1, 0), row(2, 3, { longitude: 106.66 }), row(3, 9, { longitude: 106.67 }),
    row(4, 8, { latitude: null, longitude: null }),
  ]} unit="hộp" />)
  const map = screen.getByRole('img', { name: 'Bản đồ lượng xuất theo kho' })
  expect([...map.querySelectorAll('[data-heat-band]')].map(node => node.getAttribute('data-heat-band'))).toEqual(['zero', 'low', 'high'])
  expect(screen.getByText('0 hộp')).toBeInTheDocument()
  expect(screen.getByText('1 đến 3 hộp')).toBeInTheDocument()
  expect(screen.getByText('7 đến 9 hộp')).toBeInTheDocument()
})
