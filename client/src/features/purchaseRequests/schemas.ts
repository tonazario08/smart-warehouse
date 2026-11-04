import type { PurchaseRequestDraft, PurchaseRequestInput } from './types'

export function validatePurchaseRequest(draft: PurchaseRequestDraft): { input?: PurchaseRequestInput; error?: string } {
  if ([draft.warehouse, draft.product, draft.quantity].some(value => !/^[1-9]\d*$/.test(value) || value.length > 10 || Number(value) > 2147483647)) return { error: 'Chọn kho, sản phẩm và số lượng nguyên dương hợp lệ.' }
  const note = draft.note.trim() || null
  if (Array.from(note ?? '').length > 2000) return { error: 'Ghi chú tối đa 2000 ký tự.' }
  return { input: { warehouse_id: Number(draft.warehouse), product_id: Number(draft.product), quantity: Number(draft.quantity), note } }
}
export function validateRejectionReason(value: string): { reason?: string; error?: string } {
  const reason = value.trim()
  if (!reason || Array.from(reason).length > 1000) return { error: 'Nhập lý do từ chối từ 1 đến 1000 ký tự.' }
  return { reason }
}
