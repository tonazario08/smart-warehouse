import type { Coordinate } from './types'

export type PublicLandmark = Coordinate & {
  id: string
  name: string
  aliases: readonly string[]
  sourceUrl: string
  sourceLabel: string
}

// Representative OpenStreetMap feature positions, not entrances. All are within
// the pinned TP.HCM car graph and independently routable from both demo origins.
const attribution = '© OpenStreetMap contributors · ODbL 1.0'

export const publicLandmarks: readonly PublicLandmark[] = [
  {
    id: 'dinh-doc-lap', name: 'Dinh Độc Lập', aliases: ['Dinh Thống Nhất', 'Independence Palace'],
    latitude: 10.7770348, longitude: 106.6954880,
    sourceUrl: 'https://www.openstreetmap.org/way/39598493', sourceLabel: attribution,
  },
  {
    id: 'buu-dien-trung-tam', name: 'Bưu điện Trung tâm Sài Gòn', aliases: ['Bưu điện Thành phố', 'Saigon Central Post Office'],
    latitude: 10.7799557, longitude: 106.6999921,
    sourceUrl: 'https://www.openstreetmap.org/way/39514793', sourceLabel: attribution,
  },
  {
    id: 'nha-hat-thanh-pho', name: 'Nhà hát Thành phố', aliases: ['Nhà hát Lớn', 'Saigon Opera House'],
    latitude: 10.7767437, longitude: 106.7032488,
    sourceUrl: 'https://www.openstreetmap.org/way/801710792', sourceLabel: attribution,
  },
]
