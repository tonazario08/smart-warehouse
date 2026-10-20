export type PurchaseRequestStatus = 'pending' | 'approved' | 'rejected' | 'fulfilled'
export const statusLabels: Record<PurchaseRequestStatus, string> = { pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Từ chối', fulfilled: 'Đã xuất hàng' }
export interface PurchaseRequestInput { warehouse_id: number; product_id: number; quantity: number; note: string | null }
export interface PurchaseRequestDraft { warehouse: string; product: string; quantity: string; note: string }
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
