import type { Position, SnapshotMetadata } from '../gis/types'

type Road = { name: string | null; points: Position[] }
type Place = { name: string; kind: 'landmark' | 'water' | 'park' | 'neighbourhood'; point: Position }
type Area = { name: string | null; kind: 'water' | 'park'; ring: Position[] }

export type DeliveryMapData = {
  state: 'available' | 'unavailable'
  bounds: { west: number; south: number; east: number; north: number } | null
  roads?: Road[]
  places?: Place[]
  areas?: Area[]
  attribution: string | null
  license_url: string | null
}
export type DeliveryBasemap = { bounds: SnapshotMetadata['bounds']; roads: Road[]; places: Place[]; areas: Area[] }

const streetCategory = new Set(['landmark', 'water', 'park', 'neighbourhood'])
const areaCategory = new Set(['water', 'park'])

export function validatePublicBasemap(value: DeliveryMapData | null): DeliveryBasemap | null {
  if (value?.state !== 'available' || value.attribution !== '© OpenStreetMap contributors'
    || value.license_url !== 'https://www.openstreetmap.org/copyright'
    || !value.bounds || ![value.bounds.west, value.bounds.south, value.bounds.east, value.bounds.north].every(Number.isFinite)
    || !Array.isArray(value.roads) || !Array.isArray(value.places) || !Array.isArray(value.areas)
    || !value.roads.length || value.roads.length > 8000 || !value.places.length || value.places.length > 400 || value.areas.length > 500) return null

  const { west, south, east, north } = value.bounds
  if (west < -180 || east > 180 || south < -90 || north > 90 || west >= east || south >= north) return null
  const point = (p: Position) => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite)
    && p[0] >= west && p[0] <= east && p[1] >= south && p[1] <= north
  const label = (s: string | null) => s === null || (typeof s === 'string' && s.trim().length > 0 && Array.from(s).length <= 160)
  let vertices = value.places.length
  const path = (p: Position[], minimum: number) => Array.isArray(p)
    && p.length >= minimum && p.length <= 2048 && (vertices += p.length) <= 175_000 && p.every(point)
  if (!value.roads.every(row => row && label(row.name) && path(row.points, 2))
    || !value.roads.some(row => row.name !== null)
    || !value.places.every(row => row && row.name !== null && label(row.name) && streetCategory.has(row.kind) && point(row.point))
    || !value.areas.every(row => row && label(row.name) && areaCategory.has(row.kind) && path(row.ring, 4)
      && row.ring[0][0] === row.ring.at(-1)?.[0] && row.ring[0][1] === row.ring.at(-1)?.[1])) return null
  return { bounds: [west, south, east, north], roads: value.roads, places: value.places, areas: value.areas }
}
