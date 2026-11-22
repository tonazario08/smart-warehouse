import { expect, test } from '@playwright/test'
import { apiAs, apiResponse, e2eCredentials, signIn, signOut, storedToken, tokenKey } from './helpers'

declare const process: { env: Record<string, string | undefined> }
const research = 'frv1-' + '1'.repeat(64)
const operational = 'frv1-' + '2'.repeat(64)
const ratio = 'frv1-' + '3'.repeat(64)
const missing = 'frv1-' + 'f'.repeat(64)
const scenario = process.env.E2E_FORECAST_SCENARIO

// The runner must select exactly the pre-reviewed owned scenario mount for each stack run.
test.beforeEach(async ({ page }) => {
  const url = new URL(process.env.E2E_BASE_URL ?? '')
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !['58081', '58082'].includes(url.port) || url.username || url.password) throw new Error('An isolated forecast loopback target is required.')
  if (!['valid', 'unavailable', 'failed-valid', 'corrupt', 'unsupported', 'ratio'].includes(scenario ?? '')) throw new Error('An explicit forecast fixture scenario is required.')
  for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) for (const field of ['EMAIL', 'PASSWORD']) if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated credentials are required.')
  await page.goto('/login')
})

test('finite WAPE is rendered as a percentage', async ({ page }) => {
  test.skip(scenario !== 'ratio', 'Requires the ratio fixture catalog mount')
  await signIn(page, e2eCredentials.admin)
  await page.goto('/forecasting/runs/' + ratio)
  await expect(page.getByText('100%', { exact: true })).toBeVisible()
  await page.getByLabel('Phương pháp').selectOption('xgboost')
  await expect(page.getByText('50%', { exact: true })).toBeVisible()
  await signOut(page)
})

test('logged-out access redirects to login', async ({ page }) => {
  await page.goto('/forecasting')
  await expect(page).toHaveURL(/\/login/)
})

test.describe('valid fixture catalog', () => {
  test.skip(scenario !== 'valid', 'Requires the valid fixture catalog mount')
  test('mobile forecast tables preserve readable rows and scroll within the viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await signIn(page, e2eCredentials.admin)
    await page.goto('/forecasting')
    await page.getByRole('button', { name: 'Nghiên cứu' }).click()
    const link = page.getByRole('link', { name: research, exact: true })
    await expect(link).toBeVisible()
    const list = page.getByRole('table', { name: 'Danh sách kết quả dự báo' }).locator('..')
    const geometry = await list.evaluate(wrapper => {
      const row = wrapper.querySelector('tbody tr')!
      const id = row.querySelector('a')!
      const last = row.lastElementChild!
      wrapper.scrollLeft = wrapper.scrollWidth
      return { viewport: innerWidth, document: document.documentElement.scrollWidth,
        client: wrapper.clientWidth, scroll: wrapper.scrollWidth, left: wrapper.scrollLeft,
        wrapperRight: wrapper.getBoundingClientRect().right, lastRight: last.getBoundingClientRect().right,
        rowHeight: row.getBoundingClientRect().height, idWhitespace: getComputedStyle(id).whiteSpace }
    })
    expect(geometry.document).toBeLessThanOrEqual(geometry.viewport + 1)
    expect(geometry.scroll).toBeGreaterThan(geometry.client)
    expect(geometry.left).toBeGreaterThan(0)
    expect(geometry.lastRight).toBeLessThanOrEqual(geometry.wrapperRight + 1)
    expect(geometry.idWhitespace).toBe('nowrap')
    expect(geometry.rowHeight).toBeLessThan(160)
    await link.click()
    const metrics = page.getByRole('table', { name: 'Chỉ số sai lệch' }).locator('..')
    await expect(metrics).toBeVisible()
    const metricGeometry = await metrics.evaluate(wrapper => {
      const last = wrapper.querySelector('tbody tr')!.lastElementChild!
      wrapper.scrollLeft = wrapper.scrollWidth
      return { viewport: innerWidth, document: document.documentElement.scrollWidth,
        client: wrapper.clientWidth, scroll: wrapper.scrollWidth, left: wrapper.scrollLeft,
        wrapperRight: wrapper.getBoundingClientRect().right, lastRight: last.getBoundingClientRect().right }
    })
    expect(metricGeometry.document).toBeLessThanOrEqual(metricGeometry.viewport + 1)
    expect(metricGeometry.scroll).toBeGreaterThan(metricGeometry.client)
    expect(metricGeometry.left).toBeGreaterThan(0)
    expect(metricGeometry.lastRight).toBeLessThanOrEqual(metricGeometry.wrapperRight + 1)
    await signOut(page)
  })
  test('admin sees actual operational and retrospective fixture results with filters and paging', async ({ page }) => {
    await signIn(page, e2eCredentials.admin)
    const token = await storedToken(page)
    const products = await apiAs<{ items: { id: number; sku: string; unit: string }[] }>(page, token, '/products?page=1&page_size=100')
    const warehouses = await apiAs<{ items: { id: number; code: string }[] }>(page, token, '/warehouses?page=1&page_size=100')
    expect(products.items.some(item => item.id === 1 && item.sku === 'DEMO-001' && item.unit === 'each')).toBe(true)
    expect(warehouses.items.some(item => item.id === 1 && item.code === 'HCM-01')).toBe(true)
    await page.goto('/forecasting')
    const latest = page.getByRole('heading', { name: 'Kết quả mới nhất', exact: true }).locator('..')
    const caveat = 'Kết quả của kịch bản kiểm thử, không phản ánh dự báo hay độ mới của kho thật.'
    const freshness = /không còn cập nhật|cập nhật cho ngày hiện tại/i
    await expect(latest.getByText('Dữ liệu kiểm thử', { exact: true })).toBeVisible()
    await expect(latest.getByText('Mô phỏng kiểm thử', { exact: true })).toBeVisible()
    await expect(latest.getByText(caveat, { exact: true })).toBeVisible()
    await expect(latest.getByText(freshness)).toHaveCount(0)
    const operationalLink = page.getByRole('link', { name: operational, exact: true })
    await expect(operationalLink).toHaveAttribute('href', '/forecasting/runs/' + operational)
    await operationalLink.click()
    await expect(page.getByRole('table', { name: 'Các giá trị dự báo' }).getByRole('cell', { name: 'Chưa có', exact: true }).first()).toBeVisible()
    await expect(page.getByText('Mô phỏng kiểm thử', { exact: true })).toBeVisible()
    await expect(page.getByText(caveat, { exact: true })).toBeVisible()
    await expect(page.getByText(freshness)).toHaveCount(0)
    await page.goto('/forecasting')
    await page.getByRole('button', { name: 'Nghiên cứu' }).click()
    await expect(page.getByText(/nghiên cứu hồi cứu/i).first()).toBeVisible()
    const researchLink = page.getByRole('link', { name: research, exact: true })
    const researchRow = page.getByRole('table', { name: 'Danh sách kết quả dự báo' }).getByRole('row').filter({ has: researchLink })
    await expect(researchRow).toContainText('1 ngày, 7 ngày')
    await expect(researchLink).toHaveText(research.slice(0, 14) + '…')
    await expect(researchLink).toHaveAttribute('title', research)
    await expect(researchLink).toHaveAttribute('href', '/forecasting/runs/' + research)
    await researchLink.click()
    await expect(page.getByText(/tổng thực tế bằng 0/i)).toBeVisible()
    await expect(page.getByText('0 each').first()).toBeVisible()
    await page.getByLabel('Khoảng dự báo').selectOption('7')
    await expect(page.getByText('Trang 1 / 2')).toBeVisible()
    await page.getByRole('button', { name: 'Trang sau' }).click()
    await expect(page.getByText('Trang 2 / 2')).toBeVisible()
    await page.getByLabel('Phương pháp').selectOption('xgboost')
    await expect(page.getByText('Trang 1 / 2')).toBeVisible()
    const me = apiResponse(page, '/auth/me')
    await page.reload()
    expect((await me).status()).toBe(200)
    await expect(page.getByText('Dữ liệu kiểm thử')).toBeVisible()
    await signOut(page)
  })
  test('warehouse cannot enumerate research or distinguish inaccessible and unknown IDs', async ({ page }) => {
    await signIn(page, e2eCredentials.seededWarehouse)
    const token = await storedToken(page)
    await apiAs(page, token, '/forecasts/status?mode=research', 'GET', undefined, 403)
    await apiAs(page, token, '/forecasts/runs/' + research, 'GET', undefined, 404)
    await apiAs(page, token, '/forecasts/runs/' + missing, 'GET', undefined, 404)
    expect((await storedToken(page)) === token).toBe(true)
    await page.goto('/forecasting')
    await expect(page.getByRole('button', { name: 'Nghiên cứu' })).toHaveCount(0)
    await page.goto('/forecasting/runs/' + research)
    await expect(page.getByRole('alert')).toBeVisible()
    expect((await storedToken(page)) === token).toBe(true)
    await signOut(page)
  })
  test('client has no forecast menu or endpoint grant and invalid token clears session', async ({ page }) => {
    await signIn(page, e2eCredentials.seededClient)
    const token = await storedToken(page)
    await expect(page.getByRole('link', { name: 'Dự báo', exact: true })).toHaveCount(0)
    await apiAs(page, token, '/forecasts/status?mode=operational', 'GET', undefined, 403)
    await page.goto('/forecasting')
    await expect(page).toHaveURL(/\/products$/)
    expect((await storedToken(page)) === token).toBe(true)
    await page.evaluate(key => localStorage.setItem(key, 'invalid-fixture-token'), tokenKey)
    const me = apiResponse(page, '/auth/me')
    await page.reload()
    expect((await me).status()).toBe(401)
    await expect(page).toHaveURL(/\/login$/)
    expect((await storedToken(page)) === null).toBe(true)
  })
})

for (const [name, mode, message] of [
  ['unavailable', 'operational', 'Chưa có dữ liệu vận hành đủ điều kiện để dự báo.'],
  ['failed-valid', 'operational', 'Lần tạo kết quả gần nhất không thành công'],
  ['corrupt', 'research', 'Kết quả dự báo không hợp lệ'],
  ['unsupported', 'research', 'Kết quả có định dạng không tương thích'],
] as const) {
  test('real server reports ' + name + ' fixture state', async ({ page }) => {
    test.skip(scenario !== name, 'Requires matching separate fixture catalog mount')
    await signIn(page, e2eCredentials.admin)
    await page.goto('/forecasting')
    if (mode === 'research') await page.getByRole('button', { name: 'Nghiên cứu' }).click()
    await expect(page.getByText(message, { exact: false })).toBeVisible()
    await signOut(page)
  })
}
