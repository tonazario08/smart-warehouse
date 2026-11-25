import { ApiError, request } from '../../api'
import type { DeliveryMapData } from './deliveryMapData'
import type { Page } from '../../types'
import type { DeliveryGeocodeResult, DeliveryLocation, PurchaseRequest, PurchaseRequestFilters, PurchaseRequestInput, NearestWarehouseInput, NearestWarehouseResult } from './types'

export function listPurchaseRequests(token: string, filters: PurchaseRequestFilters): Promise<Page<PurchaseRequest>> {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries({ page: 1, page_size: 20, ...filters })) if (value !== undefined && value !== '') params.set(field, String(value))
  return request('/purchase-requests?' + params, {}, token)
}
export function getPurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id, {}, token) }
export function getPurchaseRequestByKey(token: string, key: string): Promise<PurchaseRequest> { return request('/purchase-requests/by-key/' + encodeURIComponent(key), {}, token) }
export function getNearestWarehouses(token: string, input: NearestWarehouseInput): Promise<NearestWarehouseResult> {
  return request('/purchase-requests/nearest-warehouses', {
    method: 'POST', body: JSON.stringify(input), cache: 'no-store',
  }, token)
}
export function geocodeDeliveryAddress(token: string, address: string, signal: AbortSignal): Promise<DeliveryGeocodeResult> {
  return request('/purchase-requests/geocode-delivery-address', {
    method: 'POST', body: JSON.stringify({ address }), cache: 'no-store', signal,
  }, token)
}
export function getDeliveryMap(token: string, signal: AbortSignal): Promise<DeliveryMapData> {
  return request('/purchase-requests/delivery-map', { cache: 'no-store', signal }, token)
}
export function getPurchaseDeliveryLocation(token: string, id: number, signal?: AbortSignal): Promise<{ delivery_location: DeliveryLocation | null }> {
  return request(`/purchase-requests/${id}/delivery-location`, { cache: 'no-store', signal }, token)
}
export function createPurchaseRequest(token: string, key: string, input: PurchaseRequestInput): Promise<PurchaseRequest> { return request('/purchase-requests', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(input) }, token) }
export function approvePurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/approve', { method: 'POST', body: '{}' }, token) }
export function rejectPurchaseRequest(token: string, id: number, reason: string): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/reject', { method: 'POST', body: JSON.stringify({ rejection_reason: reason }) }, token) }
export function fulfillPurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/fulfill', { method: 'POST', body: '{}' }, token) }
export function purchaseRequestError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && cause.code === 'IDEMPOTENCY_KEY_CONFLICT') return 'Khóa yêu cầu đã được dùng cho nội dung khác. Vui lòng tra cứu yêu cầu mua hàng trước khi tạo lại.'
  return cause instanceof ApiError ? cause.message : fallback
}
