import { request } from '../../api'
import type { Page } from '../../types'
import type { Transfer, TransferFilters, TransferInput } from './types'

export function listTransfers(token: string, filters: TransferFilters): Promise<Page<Transfer>> {
  const params = new URLSearchParams()
  for (const [name, value] of Object.entries({ page: 1, page_size: 20, ...filters })) {
    if (value !== undefined && value !== '') params.set(name, String(value))
  }
  return request('/transfers?' + params, {}, token)
}
export const getTransfer = (token: string, id: number): Promise<Transfer> => request('/transfers/' + id, {}, token)
export const getTransferByKey = (token: string, key: string): Promise<Transfer> => request('/transfers/by-key/' + encodeURIComponent(key), {}, token)
export const createTransfer = (token: string, key: string, input: TransferInput): Promise<Transfer> => request('/transfers', { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(input) }, token)
