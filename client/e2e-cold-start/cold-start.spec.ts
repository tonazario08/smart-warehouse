import { expect, test } from '@playwright/test'
import { apiAs, e2eCredentials, signIn, signOut, storedToken } from '../e2e/helpers'

declare const process: { env: Record<string, string | undefined> }
const scenario = process.env.E2E_COLD_START_SCENARIO
const runId = process.env.E2E_COLD_START_RUN_ID ?? ''
const staleRunId = process.env.E2E_COLD_START_STALE_RUN_ID ?? ''
const statusPath = '/forecasts/cold-start/status'

test.beforeEach(async () => {
  if (process.env.E2E_BASE_URL !== 'http://127.0.0.1:58081') throw new Error('Explicit isolated M8 target required.')
  if (!['ready', 'empty', 'failed', 'stale'].includes(scenario ?? '')) throw new Error('Explicit M8 scenario required.')
  if (scenario === 'ready' && !/^csv1-[0-9a-f]{64}$/.test(runId)) throw new Error('Verified fixture ID required.')
  if (scenario === 'stale' && !/^csv1-[0-9a-f]{64}$/.test(staleRunId)) throw new Error('Verified stale fixture ID required.')
  for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) for (const field of ['EMAIL', 'PASSWORD']) {
    if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated credentials required.')
  }
})

test('unauthenticated requests and protected page require login', async ({ page }) => {
  await apiAs(page, null, statusPath, 'GET', undefined, 401)
  await page.goto('/forecasting/cold-start')
  await expect(page).toHaveURL(/\/login$/)
})

test('admin reads the real fixture and viewing does not change business data', async ({ page }) => {
  test.skip(scenario !== 'ready', 'Requires the ready fixture catalog')
  await signIn(page, e2eCredentials.admin)
  const token = await storedToken(page)
  const stock = await apiAs(page, token, '/stock?page_size=100')
  const transactions = await apiAs(page, token, '/transactions?page_size=100')
  const status = await apiAs<{ state: string; latest_run_id: string; operational_state: string }>(page, token, statusPath)
  expect(status).toMatchObject({ state: 'ready', latest_run_id: runId, operational_state: 'unavailable' })
  const result = await apiAs<{ stale: boolean; report: { selected_k: number; fixture_label: string; samples: { horizon: number; prediction: number; baseline: number }[] } }>(page, token, '/forecasts/cold-start/runs/' + runId)
  expect(result.stale).toBe(false)
  expect(result.report.selected_k).toBe(2)
  expect(result.report.fixture_label).toBe('Dữ liệu kiểm thử')
  expect(result.report.samples.find(row => row.horizon === 1)).toMatchObject({ prediction: 8, baseline: 5 })
  expect(result.report.samples.find(row => row.horizon === 7)).toMatchObject({ prediction: 56, baseline: 35 })
  await page.goto('/forecasting')
  await page.getByRole('link', { name: 'Xem dự báo cho sản phẩm mới' }).click()
  await expect(page.getByText('Dữ liệu kiểm thử', { exact: true })).toBeVisible()
  await expect(page.getByText('Chưa sẵn sàng cho vận hành.')).toBeVisible()
  await expect(page.getByText(/chưa được xác minh trên nguồn nhiều sản phẩm/i)).toBeVisible()
  await expect(page.getByText('Số cụm đã chọn').locator('..')).toContainText('2')
  const table = page.getByRole('table', { name: 'Mẫu dự báo sản phẩm mới' })
  await expect(table.getByRole('row').filter({ hasText: '1 ngày' }).first().getByRole('cell').nth(2)).toHaveText('8')
  await expect(table.getByRole('row').filter({ hasText: '7 ngày' }).first().getByRole('cell').nth(2)).toHaveText('56')
  expect(await apiAs(page, token, '/stock?page_size=100')).toEqual(stock)
  expect(await apiAs(page, token, '/transactions?page_size=100')).toEqual(transactions)
  await signOut(page)
})

test('warehouse may read and client is denied', async ({ page }) => {
  await signIn(page, e2eCredentials.seededWarehouse)
  let token = await storedToken(page)
  await apiAs(page, token, statusPath)
  await apiAs(page, token, '/forecasts/cold-start/runs/csv1-' + 'f'.repeat(64), 'GET', undefined, 404)
  await signOut(page)
  await signIn(page, e2eCredentials.seededClient)
  token = await storedToken(page)
  await apiAs(page, token, statusPath, 'GET', undefined, 403)
  await apiAs(page, token, '/forecasts/cold-start/runs/csv1-' + 'f'.repeat(64), 'GET', undefined, 403)
  await page.goto('/forecasting/cold-start')
  await expect(page).not.toHaveURL(/\/forecasting\/cold-start/)
  await signOut(page)
})

test('desktop and mobile retain readable report without page overflow', async ({ page }) => {
  test.skip(scenario !== 'ready', 'Requires the ready fixture catalog')
  await signIn(page, e2eCredentials.admin)
  for (const viewport of [{ width: 1440, height: 1024 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/forecasting/cold-start')
    await expect(page.getByText('Dữ liệu kiểm thử', { exact: true })).toBeVisible()
    await expect(page.getByRole('table', { name: 'Kết quả theo khoảng dự báo' })).toBeVisible()
    const geometry = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth }))
    expect(geometry.page).toBeLessThanOrEqual(geometry.viewport + 1)
  }
  await signOut(page)
})

for (const [name, state, message] of [
  ['empty', 'unavailable', 'Chưa có báo cáo'],
  ['failed', 'failed', 'không thành công'],
  ['stale', 'stale', 'quá hạn'],
] as const) {
  test('real API and UI show ' + name + ' state', async ({ page }) => {
    test.skip(scenario !== name, 'Requires matching isolated catalog')
    await signIn(page, e2eCredentials.admin)
    const status = await apiAs<{ state: string; latest_run_id: string | null }>(page, await storedToken(page), statusPath)
    expect(status.state).toBe(state)
    expect(status.latest_run_id).toBeNull()
    if (name === 'stale') {
      const old = await apiAs<{ stale: boolean; report: { fixture_label: string } }>(page, await storedToken(page), '/forecasts/cold-start/runs/' + staleRunId)
      expect(old.stale).toBe(true)
      expect(old.report.fixture_label).toBe('Dữ liệu kiểm thử')
    }
    await page.goto('/forecasting/cold-start')
    await expect(page.getByText(message, { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('table')).toHaveCount(0)
    await signOut(page)
  })
}
