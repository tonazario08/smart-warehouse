import { expect, test } from '@playwright/test'
import { apiAs, e2eCredentials, realApi, signIn, signOut, storedToken } from '../e2e/helpers'

type Row = { alert_id: string; version: number; review_status: 'new' | 'confirmed' | 'dismissed' }
type AlertDetail = Row & { score: number; explanation: { state: 'available' | 'unavailable'; reason: string | null; base_value: number | null; contributions: number[] | null; residual: number | null } }
async function findAlerts(page: import('@playwright/test').Page) {
  const list = await realApi<{ items: Row[] }> (page, '/anomalies?page=1&page_size=100')
  let available: AlertDetail | undefined
  let unavailable: AlertDetail | undefined
  for (const row of list.items) {
    const detail = await realApi<AlertDetail>(page, '/anomalies/' + row.alert_id)
    if (!available && detail.explanation.state === 'available') available = detail
    if (!unavailable && detail.explanation.reason === 'EXPLAINER_ERROR') unavailable = detail
    if (available && unavailable) break
  }
  expect(available).toBeTruthy(); expect(unavailable).toBeTruthy()
  return { available: available!, unavailable: unavailable! }
}

test('empty fixture environment', async ({ page }) => {
  test.skip(process.env.E2E_ANOMALIES_EMPTY !== '1', 'Run before catalog import')
  await signIn(page, e2eCredentials.admin)
  await page.goto('/anomalies')
  await expect(page.getByText('Chưa có cảnh báo khả dụng')).toBeVisible()
})

test('available run with no alerts shows empty list', async ({ page }) => {
  test.skip(process.env.E2E_ANOMALIES_EMPTY_LIST !== '1', 'Run after empty catalog import')
  await signIn(page, e2eCredentials.admin)
  await page.goto('/anomalies')
  await expect(page.getByText('Không có cảnh báo')).toBeVisible()
})

test('three roles, real explanation, review replay and conflict', async ({ page }) => {
  test.skip(process.env.E2E_ANOMALIES_EMPTY === '1' || process.env.E2E_ANOMALIES_EMPTY_LIST === '1', 'Run after catalog import')
  await signIn(page, e2eCredentials.admin)
  const { available, unavailable } = await findAlerts(page)
  const e = available.explanation
  expect(e.base_value).not.toBeNull(); expect(e.contributions).toHaveLength(6)
  expect(Math.abs(e.base_value! + e.contributions!.reduce((a, b) => a + b, 0) - available.score)).toBeLessThanOrEqual(1e-8)
  await page.goto('/anomalies')
  await expect(page.getByText(/Hiệu quả trên dữ liệu thực chưa được xác minh/)).toBeVisible()
  await expect(page.getByRole('link', { name: available.alert_id })).toBeVisible()
  await page.getByLabel('Trạng thái đánh giá').selectOption(available.review_status)
  await expect(page.getByRole('link', { name: available.alert_id })).toBeVisible()
  await page.getByLabel('Trạng thái đánh giá').selectOption('')
  await page.getByRole('link', { name: available.alert_id }).click()
  await expect(page.getByRole('heading', { name: 'Giải thích của mô hình' })).toBeVisible()
  await expect(page.getByText(/không chứng minh quan hệ nhân quả/)).toBeVisible()
  await expect(page.getByText(/Giá trị nền:/)).toBeVisible()
  await expect(page.getByText('Phiên bản dữ liệu')).toBeVisible()
  const selected = available.review_status === 'confirmed' ? 'dismissed' : 'confirmed'
  await page.getByLabel('Quyết định').selectOption(selected)
  await page.getByLabel('Ghi chú').fill('Rà soát dữ liệu kiểm thử')
  const requestPromise = page.waitForRequest(req => req.method() === 'PATCH' && new URL(req.url()).pathname.endsWith('/review'))
  const responsePromise = page.waitForResponse(res => res.request().method() === 'PATCH' && new URL(res.url()).pathname.endsWith('/review'))
  await page.getByRole('button', { name: 'Lưu đánh giá' }).click()
  const submitted = await requestPromise, response = await responsePromise
  expect(response.status()).toBe(200)
  await expect(page.getByText('Đã lưu đánh giá.')).toBeVisible()
  const token = await storedToken(page)
  expect(Boolean(token)).toBe(true)
  const payload = submitted.postDataJSON() as { expected_version: number; decision: string; note: string }
  const key = submitted.headers()['idempotency-key']
  expect(Boolean(key)).toBe(true)
  const replay = await page.request.patch('/api/v1/anomalies/' + available.alert_id + '/review', { headers: { Authorization: 'Bearer ' + token, 'Idempotency-Key': key }, data: payload })
  expect(replay.status()).toBe(200); expect((await replay.json()).replayed).toBe(true)
  const conflict = await page.request.patch('/api/v1/anomalies/' + available.alert_id + '/review', { headers: { Authorization: 'Bearer ' + token, 'Idempotency-Key': crypto.randomUUID() }, data: payload })
  expect(conflict.status()).toBe(409)
  await page.goto('/anomalies/' + unavailable.alert_id)
  await expect(page.getByText(/Chưa có giải thích/)).toBeVisible()
  await expect(page.getByText(/Không thể tính giải thích/)).toBeVisible()
  await signOut(page)
  await signIn(page, e2eCredentials.seededWarehouse)
  await page.goto('/anomalies/' + available.alert_id)
  await expect(page.getByRole('heading', { name: 'Đánh giá cảnh báo' })).toBeVisible()
  const afterAdmin = await realApi<AlertDetail>(page, '/anomalies/' + available.alert_id)
  await page.getByLabel('Quyết định').selectOption(afterAdmin.review_status === 'confirmed' ? 'dismissed' : 'confirmed')
  await page.getByLabel('Ghi chú').fill('Nhân viên kho rà soát')
  const warehouseResponse = page.waitForResponse(res => res.request().method() === 'PATCH' && new URL(res.url()).pathname.endsWith('/review'))
  await page.getByRole('button', { name: 'Lưu đánh giá' }).click()
  expect((await warehouseResponse).status()).toBe(200)
  await expect(page.getByText('Đã lưu đánh giá.')).toBeVisible()
  const history = await realApi<{ items: { note: string }[] }>(page, '/anomalies/' + available.alert_id + '/reviews')
  expect(history.items.some(item => item.note === 'Nhân viên kho rà soát')).toBe(true)
  await signOut(page)
  await signIn(page, e2eCredentials.seededClient)
  await expect(page.getByRole('link', { name: 'Bất thường' })).toHaveCount(0)
  const clientToken = await storedToken(page)
  await apiAs(page, clientToken, '/anomalies', 'GET', undefined, 403)
  await apiAs(page, clientToken, '/anomalies/' + available.alert_id + '/review', 'PATCH', payload, 403)
  await page.goto('/anomalies')
  await expect(page).toHaveURL(/\/products$/)
})

test('network error can be retried against real API', async ({ page }) => {
  test.skip(process.env.E2E_ANOMALIES_EMPTY === '1' || process.env.E2E_ANOMALIES_EMPTY_LIST === '1', 'Run after catalog import')
  await signIn(page, e2eCredentials.admin)
  await page.route('**/api/v1/anomalies/status', route => route.abort(), { times: 1 })
  await page.goto('/anomalies')
  await expect(page.getByText(/Không thể tải cảnh báo/)).toBeVisible()
  await page.getByRole('button', { name: 'Thử lại' }).click()
  await expect(page.getByRole('table', { name: 'Danh sách cảnh báo' })).toBeVisible()
})
