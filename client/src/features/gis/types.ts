import type { Product, Warehouse } from '../../types'

export type Coordinate = { latitude: number; longitude: number }
export type Position = [longitude: number, latitude: number]
export type Destination =
  | ({ kind: 'coordinate' } & Coordinate)
  | { kind: 'warehouse'; warehouse_id: number }
  | { kind: 'purchase_request'; request_id: number }
export type OptionsInput = { product_id: number; quantity: number; destination: Destination }
export type RouteInput =
  | { kind: 'warehouse_to_target'; warehouse_id: number; destination: Destination }
  | { kind: 'transfer'; transfer_id: number }
export type HeatmapInput = { product_id: number; start_date: string; end_date: string }
export type PolicyInput = { run_id: string; product_id: number; warehouse_id: number }

export type GisChoices = { products: Product[]; warehouses: Warehouse[] }
export type StockData = {
  stock_data_class: 'operational' | 'synthetic_fixture'
  stock_fixture_label: string | null
}
export type SnapshotState = 'available' | 'unconfigured' | 'invalid' | 'stale'
export type SnapshotMetadata = {
  snapshot_id: string
  dataset_class: 'public_osm' | 'synthetic_fixture'
  source_url: string | null
  snapshot_at: string
  bounds: [west: number, south: number, east: number, north: number]
  crs: 'EPSG:4326'
  weight_unit: 'mm'
  license: string
  attribution: string
  license_url: string | null
}
export type GisStatus = StockData & { state: SnapshotState; snapshot: SnapshotMetadata | null }
export type ProductRead = { product_id: number; sku: string; name: string; unit: string }
export type WarehouseRead = {
  warehouse_id: number
  code: string
  name: string
  latitude: number | null
  longitude: number | null
}
export type Place = {
  kind: Destination['kind']
  coordinate: Coordinate | null
  warehouse: WarehouseRead | null
  request_id: number | null
}
export type WarehouseOption = { warehouse: WarehouseRead; available_quantity: number | null }
export type RankedWarehouse = WarehouseOption & {
  available_quantity: number; distance_mm: number; snapshot_id: string
}
export type GeographicWarehouse = WarehouseOption & {
  available_quantity: number; distance_mm: number; reason: string
}
export type ExcludedWarehouse = WarehouseOption & { reason: string }
export type WarehouseOptions = StockData & {
  stock_as_of: string
  product: ProductRead
  quantity: number
  destination: Place
  snapshot_state: SnapshotState
  snapshot: SnapshotMetadata | null
  ranking_state: 'available' | 'unavailable' | 'budget_exceeded'
  ranked: RankedWarehouse[]
  geographic_only: GeographicWarehouse[]
  excluded: ExcludedWarehouse[]
}
export type LineString = { type: 'LineString'; coordinates: Position[] }
export type Geometry = LineString | { type: 'Point'; coordinates: Position }
export type Snap = {
  node_id: number
  coordinates: Position
  distance_mm: number
  connector: LineString | null
}
export type RouteRead = StockData & {
  snapshot_state: SnapshotState
  snapshot: SnapshotMetadata | null
  origin: Place
  destination: Place
  origin_snap: Snap | null
  destination_snap: Snap | null
  geometry: Geometry | null
  distance_mm: number | null
  reason: string | null
  transfer: { transfer_id: number; mode: 'immediate' } | null
}
export type HeatmapPoint = { warehouse: WarehouseRead; fulfilled_quantity: number; transaction_count: number }
export type MovementTotal = { quantity: number; transaction_count: number }
export type Exclusion = 'transfer_in' | 'transfer_out' | 'standard_outbound' | 'unclassified_outbound'
export type Heatmap = StockData & HeatmapInputFields & {
  product: ProductRead
  start_utc: string
  end_utc: string
  timezone: 'Asia/Ho_Chi_Minh'
  queried_at: string
  points: HeatmapPoint[]
  unlocated: HeatmapPoint[]
  excluded: Record<Exclusion, MovementTotal>
}
type HeatmapInputFields = Pick<HeatmapInput, 'start_date' | 'end_date'>
export type PolicyContext = {
  state: 'applicable' | 'not_applicable'
  run: { run_id: string; data_version: string; created_at: string; fixture_label: string; href: string } | null
}
