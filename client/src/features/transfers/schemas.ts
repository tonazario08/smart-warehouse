import type { TransferDraft, TransferInput } from './types'

export function validateTransfer(draft: TransferDraft): { input?: TransferInput; error?: string } {
  if ([draft.source, draft.destination, draft.product, draft.quantity].some(value => !/^[1-9]\d*$/.test(value) || Number(value) > 2_147_483_647)) {
    return { error: 'Chọn hai kho, sản phẩm và số lượng nguyên dương hợp lệ.' }
  }
  if (draft.source === draft.destination) return { error: 'Kho nguồn và kho đích phải khác nhau.' }
  const reference = draft.reference.trim() || null, note = draft.note.trim() || null
  if ((reference?.length ?? 0) > 120 || (note?.length ?? 0) > 2000) return { error: 'Mã phiếu tối đa 120 ký tự; ghi chú tối đa 2000 ký tự.' }
  return { input: { source_warehouse_id: Number(draft.source), destination_warehouse_id: Number(draft.destination), product_id: Number(draft.product), quantity: Number(draft.quantity), reference, note } }
}
