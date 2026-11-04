import { ApiError, request } from '../../api'
import type { Page } from '../../types'
import type { PurchaseRequest, PurchaseRequestFilters, PurchaseRequestInput } from './types'

export function listPurchaseRequests(token: string, filters: PurchaseRequestFilters): Promise<Page<PurchaseRequest>> {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries({ page: 1, page_size: 20, ...filters })) if (value !== undefined && value !== '') params.set(field, String(value))
  return request('/purchase-requests?' + params, {}, token)
}
export function getPurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id, {}, token) }
export function getPurchaseRequestByKey(token: string, key: string): Promise<PurchaseRequest> { return request('/purchase-requests/by-key/' + encodeURIComponent(key), {}, token) }
export function createPurchaseRequest(token: string, key: string, input: PurchaseRequestInput): Promise<PurchaseRequest> { return request('/purchase-requests', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(input) }, token) }
export function approvePurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/approve', { method: 'POST', body: '{}' }, token) }
export function rejectPurchaseRequest(token: string, id: number, reason: string): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/reject', { method: 'POST', body: JSON.stringify({ rejection_reason: reason }) }, token) }
export function fulfillPurchaseRequest(token: string, id: number): Promise<PurchaseRequest> { return request('/purchase-requests/' + id + '/fulfill', { method: 'POST', body: '{}' }, token) }
export function purchaseRequestError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && cause.code === 'IDEMPOTENCY_KEY_CONFLICT') return 'Khóa yêu cầu đã được dùng cho nội dung khác. Vui lòng tra cứu yêu cầu mua hàng trước khi tạo lại.'
  return cause instanceof ApiError ? cause.message : fallback
}
