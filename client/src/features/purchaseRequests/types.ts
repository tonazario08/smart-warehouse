export type PurchaseRequestStatus = 'pending' | 'approved' | 'rejected' | 'fulfilled'
export const statusLabels: Record<PurchaseRequestStatus, string> = { pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Từ chối', fulfilled: 'Đã xuất hàng' }
export type DeliveryGeocodeCandidate = { label: string; latitude: number; longitude: number; precision: 'house_number' | 'approximate' }
export type DeliveryGeocodeResult = { status: 'matches' | 'no_match' | 'unavailable'; candidates: DeliveryGeocodeCandidate[] }
export interface DeliveryLocation { address: string; latitude: number; longitude: number }
export interface PurchaseRequestInput { warehouse_id: number; product_id: number; quantity: number; note: string | null; delivery_location?: DeliveryLocation }
export interface PurchaseRequestDraft { warehouse: string; product: string; quantity: string; note: string }
export interface NearestWarehouseInput { product_id: number; quantity: number; latitude: number; longitude: number }
export interface NearestWarehouse { warehouse_id: number; code: string; name: string; available_quantity: number; distance_km: number }
export interface NearestWarehouseResult {
  product_id: number; quantity: number; method: 'great_circle_haversine'; earth_radius_meters: number; warehouses: NearestWarehouse[]
}
export interface PurchaseRequestFilters {
  status?: PurchaseRequestStatus; warehouse_id?: number; product_id?: number; requested_by_id?: number;
  created_from?: string; created_to?: string; page?: number; page_size?: number;
}
export interface PurchaseRequest extends PurchaseRequestInput {
  id: number; request_number: string; status: PurchaseRequestStatus; requested_by_id: number;
  created_at: string; updated_at: string; workflow_managed: boolean;
  decision: null | { kind: 'approved' | 'rejected'; actor_id: number; decided_at: string; rejection_reason: string | null };
  fulfillment: null | { outbound_id: number; transaction_id: number; actor_id: number; fulfilled_at: string; quantity_before: number; quantity_after: number };
}
