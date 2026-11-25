import { afterEach, expect, it, vi } from 'vitest'
import { advanceApiSession, ApiError, onApiUnauthorized } from '../../api'
import { approvePurchaseRequest, createPurchaseRequest, fulfillPurchaseRequest, getPurchaseRequest, getPurchaseRequestByKey, listPurchaseRequests, purchaseRequestError, rejectPurchaseRequest } from './api'
import { validatePurchaseRequest, validateRejectionReason } from './schemas'
import type { PurchaseRequest } from './types'

const input = { warehouse_id: 1, product_id: 2, quantity: 3, note: null }
const key = 'e057be9a-8df1-47d0-baf0-20505e2b47b3'
const row: PurchaseRequest = { ...input, id: 9, request_number: 'PR-example', status: 'approved', requested_by_id: 7, created_at: '2026-10-19T00:00:00Z', updated_at: '2026-10-19T01:00:00Z', workflow_managed: true, decision: { kind: 'approved', actor_id: 1, decided_at: '2026-10-19T01:00:00Z', rejection_reason: null }, fulfillment: null }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
afterEach(() => vi.unstubAllGlobals())

it('sends exact confirmed body/key through central bearer transport and accepts CURRENT replay state', async () => {
  const fetcher = vi.fn(async () => json(row))
  vi.stubGlobal('fetch', fetcher)
  expect(await createPurchaseRequest('token', key, input)).toEqual(row)
  const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toMatch(/\/purchase-requests$/)
  expect(init.method).toBe('POST')
  expect(init.headers).toMatchObject({ Authorization: 'Bearer token', 'Idempotency-Key': key, 'Content-Type': 'application/json' })
  expect(JSON.parse(String(init.body))).toEqual(input)
})
it('encodes all conjunctive filters and exact seven endpoint operations', async () => {
  const fetcher = vi.fn(async (_url: unknown, _init?: RequestInit) => json(row))
  vi.stubGlobal('fetch', fetcher)
  await listPurchaseRequests('token', { warehouse_id: 1, product_id: 2, requested_by_id: 7, status: 'approved', created_from: '2026-10-19T07:00:00+07:00', created_to: '2026-10-20T00:00:00Z', page: 2, page_size: 100 })
  expect(Object.fromEntries(new URL(String(fetcher.mock.calls[0][0])).searchParams)).toEqual({ warehouse_id: '1', product_id: '2', requested_by_id: '7', status: 'approved', created_from: '2026-10-19T07:00:00+07:00', created_to: '2026-10-20T00:00:00Z', page: '2', page_size: '100' })
  await getPurchaseRequest('token', 9)
  await getPurchaseRequestByKey('token', 'own/key?')
  await approvePurchaseRequest('token', 9)
  await rejectPurchaseRequest('token', 9, 'lý do')
  await fulfillPurchaseRequest('token', 9)
  expect(fetcher.mock.calls.slice(1).map(([url]) => new URL(String(url)).pathname)).toEqual(['/api/v1/purchase-requests/9', '/api/v1/purchase-requests/by-key/own%2Fkey%3F', '/api/v1/purchase-requests/9/approve', '/api/v1/purchase-requests/9/reject', '/api/v1/purchase-requests/9/fulfill'])
  expect(fetcher.mock.calls.slice(3).map(([, init]) => [init?.method, JSON.parse(String(init?.body))])).toEqual([['POST', {}], ['POST', { rejection_reason: 'lý do' }], ['POST', {}]])
})
it('never automatically retries uncertain writes and explicit retries retain exact identity', async () => {
  const fetcher = vi.fn(async (_url: unknown, _init?: RequestInit) => json({ detail: { code: 'PURCHASE_REQUEST_RETRY_REQUIRED', message: 'private SQL', fields: null } }, 503))
  vi.stubGlobal('fetch', fetcher)
  await expect(createPurchaseRequest('token', key, input)).rejects.toMatchObject({ status: 503, code: 'PURCHASE_REQUEST_RETRY_REQUIRED' })
  expect(fetcher).toHaveBeenCalledTimes(1)
  await expect(createPurchaseRequest('token', key, input)).rejects.toBeInstanceOf(ApiError)
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect(fetcher.mock.calls[0]).toEqual(fetcher.mock.calls[1])
})
it('inherits stale401 isolation, current401 cleanup and403 retention', async () => {
  let finish!: (response: Response) => void
  const pendingResponse = new Promise<Response>(resolve => { finish = resolve })
  vi.stubGlobal('fetch', vi.fn(() => pendingResponse))
  const invalidated = vi.fn(), unsubscribe = onApiUnauthorized(invalidated)
  try {
    const pending = getPurchaseRequest('old-token', 9)
    advanceApiSession()
    finish(json({}, 401))
    await expect(pending).rejects.toMatchObject({ staleSession: true, status: 401 })
    expect(invalidated).not.toHaveBeenCalled()
    vi.stubGlobal('fetch', vi.fn(async () => json({}, 401)))
    await expect(getPurchaseRequest('new-token', 9)).rejects.toMatchObject({ staleSession: false, status: 401 })
    expect(invalidated).toHaveBeenCalledTimes(1)
    vi.stubGlobal('fetch', vi.fn(async () => json({}, 403)))
    await expect(getPurchaseRequest('new-token', 9)).rejects.toMatchObject({ status: 403 })
    expect(invalidated).toHaveBeenCalledTimes(1)
  } finally { unsubscribe() }
})
it.each([
  ['PURCHASE_REQUEST_NOT_FOUND', 404, 'Không tìm thấy yêu cầu mua hàng.'],
  ['PRODUCT_NOT_REQUESTABLE', 409, 'Sản phẩm đã ngừng hoạt động, không thể tạo hoặc duyệt xuất yêu cầu mới.'],
  ['LEGACY_PURCHASE_REQUEST_READ_ONLY', 409, 'Yêu cầu cũ chỉ có thể xem, không thể thay đổi.'],
  ['PURCHASE_REQUEST_STATE_CONFLICT', 409, 'Trạng thái yêu cầu đã thay đổi hoặc không cho phép thao tác này. Vui lòng tải lại.'],
  ['PURCHASE_REQUEST_RETRY_REQUIRED', 503, 'Chưa xác định kết quả yêu cầu mua hàng. Hãy tra cứu hoặc thử lại cùng yêu cầu.'],
] as const)('renders safe Vietnamese %s without database diagnostics', async (code, status, expected) => {
  vi.stubGlobal('fetch', vi.fn(async () => json({ detail: { code, message: 'private SQL', fields: null } }, status)))
  await expect(getPurchaseRequest('token', 9)).rejects.toMatchObject({ message: expected })
})
it('keeps feature-specific key conflict guidance without changing transfer transport copy', () => {
  const cause = new ApiError('Vui lòng kiểm tra phiếu chuyển kho.', 409, 'IDEMPOTENCY_KEY_CONFLICT')
  expect(purchaseRequestError(cause, 'fallback')).toBe('Khóa yêu cầu đã được dùng cho nội dung khác. Vui lòng tra cứu yêu cầu mua hàng trước khi tạo lại.')
})
const draft = { warehouse: '1', product: '2', quantity: '3', note: ' \n\t' }
it('normalizes note once and rejects forged nonpositive/fractional/overflow IDs and quantities', () => {
  expect(validatePurchaseRequest(draft)).toEqual({ input })
  expect(validatePurchaseRequest({ ...draft, note: '  tiếng Việt  ' }).input?.note).toBe('tiếng Việt')
  expect(validatePurchaseRequest({ ...draft, quantity: '2147483647' }).input?.quantity).toBe(2147483647)
  for (const field of ['warehouse', 'product', 'quantity']) for (const value of ['', '0', '-1', '1.5', '2147483648', 'true', '9'.repeat(5000)]) expect(validatePurchaseRequest({ ...draft, [field]: value }).error).toBeTruthy()
  expect(validatePurchaseRequest({ ...draft, note: ' ' + 'n'.repeat(2000) + ' ' }).input?.note).toHaveLength(2000)
  expect(validatePurchaseRequest({ ...draft, note: 'n'.repeat(2001) }).error).toBeTruthy()
})
it('normalizes rejection reason with strict nonblank1000-character boundary', () => {
  expect(validateRejectionReason('  lý do  ')).toEqual({ reason: 'lý do' })
  expect(validateRejectionReason(' ' + 'r'.repeat(1000) + ' ').reason).toHaveLength(1000)
  for (const value of ['', ' \n\t', 'r'.repeat(1001)]) expect(validateRejectionReason(value).error).toBeTruthy()
})
