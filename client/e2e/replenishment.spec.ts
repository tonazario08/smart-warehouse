import { expect, test } from '@playwright/test'
import { apiAs, e2eCredentials, signIn, signOut, storedToken } from './helpers'

declare const process: { env: Record<string, string | undefined> }
const scenario = process.env.E2E_REPLENISHMENT_SCENARIO
const fixtureId = process.env.E2E_REPLENISHMENT_RUN_ID ?? ''
const researchId = process.env.E2E_REPLENISHMENT_RESEARCH_RUN_ID ?? ''
const profile = process.env.E2E_REPLENISHMENT_PROFILE ?? 'local'
const missing = 'rrv1-' + 'f'.repeat(64)
const validId = (id: string) => /^rrv1-[0-9a-f]{64}$/.test(id)
const statusUrl = (url: URL) => url.pathname === '/api/v1/replenishment/status'
const display = (value: number | string) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(Number(value))

test.beforeEach(async ({ page }) => {
  const target = new URL(process.env.E2E_BASE_URL ?? '')
  if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || target.port !== '58082' || target.username || target.password) throw new Error('Explicit isolated M7 target required.')
  if (!['valid', 'unavailable', 'failed', 'stale', 'corrupt', 'unsupported'].includes(scenario ?? '')) throw new Error('Explicit M7 catalog scenario required.')
  if (!['local', 'synthetic-only'].includes(profile)) throw new Error('Explicit fixture profile required.')
  if (profile === 'synthetic-only' && (process.env.CI !== 'true' || researchId)) throw new Error('Synthetic CI profile required.')
  if (scenario === 'valid' && (!validId(fixtureId) || (profile === 'local' && !validId(researchId)))) throw new Error('Verified run identities are required.')
  for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) for (const field of ['EMAIL', 'PASSWORD']) if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated credentials required.')
  await page.goto('/login')
})

test('logged-out replenishment route requires authentication', async ({ page }) => {
  await page.goto('/replenishment')
  await expect(page).toHaveURL(/\/login/)
})

test.describe('actual generated fixture', () => {
  test.skip(scenario !== 'valid', 'Requires the CLI-generated valid catalog')

  test('admin sees the same verified run and day rows without business writes', async ({ page }) => {
    await signIn(page, e2eCredentials.admin)
    const token = await storedToken(page)
    const beforeStock = await apiAs(page, token, '/stock?page_size=100')
    const beforeTransactions = await apiAs(page, token, '/transactions?page_size=100')
    const status = await apiAs<{ state: string; latest: { manifest: { run_id: string }; fixture_label: string } }>(page, token, '/replenishment/status?mode=operational')
    expect(status.state).toBe('ready')
    expect(status.latest.manifest.run_id).toBe(fixtureId)
    expect(status.latest.fixture_label).toBe('Dữ liệu kiểm thử')
    const first = await apiAs<{ items: { day: string; reorder_point: number; ordered: number }[]; total: number }>(page, token, `/replenishment/runs/${fixtureId}/days?algorithm=persistence&lead_time=1&service=0.90&policy=proposed&page=1&page_size=20`)
    expect(first.total).toBe(178)
    expect(first.items).toHaveLength(20)
    await page.goto('/replenishment')
    await expect(page.getByText('Dữ liệu kiểm thử').first()).toBeVisible()
    await page.getByRole('link', { name: fixtureId, exact: true }).click()
    await expect(page.getByText(/Kịch bản kiểm thử tổng hợp/)).toBeVisible()
    await expect(page.getByText('M7-E2E-SYNTHETIC', { exact: false })).toBeVisible()
    const trace = page.getByRole('table', { name: 'Diễn biến tồn và đơn hàng theo ngày' })
    const firstRow = trace.getByRole('row').filter({ hasText: first.items[0].day })
    await expect(firstRow).toBeVisible()
    await expect(firstRow.getByRole('cell').nth(3)).toHaveText(display(first.items[0].reorder_point))
    await expect(firstRow.getByRole('cell').nth(4)).toHaveText(display(first.items[0].ordered))
    await page.getByRole('button', { name: 'Trang sau' }).last().click()
    const second = await apiAs<{ items: { day: string }[] }>(page, token, `/replenishment/runs/${fixtureId}/days?algorithm=persistence&lead_time=1&service=0.90&policy=proposed&page=2&page_size=20`)
    await expect(trace.getByRole('row').filter({ hasText: second.items[0].day })).toBeVisible()
    const lead = page.getByLabel('Thời gian cung ứng')
    await lead.focus()
    await page.keyboard.press('End')
    await page.keyboard.press('Enter')
    await expect(lead).toHaveValue('7')
    await expect(lead).toBeFocused()
    await expect(page.getByText('Trang 1 / 9')).toBeVisible()
    await page.reload()
    await expect(page.getByText(/Kịch bản kiểm thử tổng hợp/)).toBeVisible()
    expect((await storedToken(page)) === token).toBe(true)
    expect(await apiAs(page, token, '/stock?page_size=100')).toEqual(beforeStock)
    expect(await apiAs(page, token, '/transactions?page_size=100')).toEqual(beforeTransactions)
    await signOut(page)
  })

  test('admin can read the separate retrospective result', async ({ page }) => {
    test.skip(profile !== 'local', 'Real retrospective artifact requires the approved local profile')
    await signIn(page, e2eCredentials.admin)
    await page.goto('/replenishment')
    await page.getByRole('button', { name: 'Nghiên cứu', exact: true }).click()
    await expect(page.getByText(/nghiên cứu hồi cứu/i).first()).toBeVisible()
    await page.getByRole('link', { name: researchId, exact: true }).click()
    await expect(page.getByText(/không chứng minh hiệu quả tại kho thực tế/i)).toBeVisible()
    await signOut(page)
  })

  test('admin sees unavailable research in synthetic CI', async ({ page }) => {
    test.skip(profile !== 'synthetic-only', 'Synthetic-only CI profile')
    await signIn(page, e2eCredentials.admin)
    const token = await storedToken(page)
    const status = await apiAs<{ state: string; reason_code: string; latest: null }>(page, token, '/replenishment/status?mode=research')
    expect(status.state).toBe('unavailable')
    expect(status.reason_code).toBe('NO_RUNS')
    expect(status.latest).toBeNull()
    await apiAs(page, token, '/replenishment/runs/' + missing, 'GET', undefined, 404)
    await page.goto('/replenishment')
    await page.getByRole('button', { name: 'Nghiên cứu', exact: true }).click()
    await expect(page.getByText('Chưa có kết quả khả dụng', { exact: true })).toBeVisible()
    await signOut(page)
  })

  test('warehouse cannot access research and client has no grant', async ({ page }) => {
    await signIn(page, e2eCredentials.seededWarehouse)
    let token = await storedToken(page)
    await apiAs(page, token, '/replenishment/status?mode=research', 'GET', undefined, 403)
    await apiAs(page, token, '/replenishment/runs/' + (researchId || missing), 'GET', undefined, 404)
    await apiAs(page, token, '/replenishment/runs/' + missing, 'GET', undefined, 404)
    await page.goto('/replenishment')
    await expect(page.getByRole('button', { name: 'Nghiên cứu' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: fixtureId, exact: true })).toBeVisible()
    expect((await storedToken(page)) === token).toBe(true)
    await signOut(page)
    await signIn(page, e2eCredentials.seededClient)
    token = await storedToken(page)
    await expect(page.getByRole('link', { name: 'Bổ sung hàng', exact: true })).toHaveCount(0)
    await apiAs(page, token, '/replenishment/status?mode=operational', 'GET', undefined, 403)
    await page.goto('/replenishment')
    await expect(page).toHaveURL(/\/products$/)
    expect((await storedToken(page)) === token).toBe(true)
    await signOut(page)
  })

  test('loading waits for a delayed real response', async ({ page }) => {
    await signIn(page, e2eCredentials.admin)
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    await page.route(statusUrl, async route => {
      await gate
      await route.continue()
    })
    try {
      await page.goto('/replenishment', { waitUntil: 'domcontentloaded' })
      await expect(page.getByText('Đang tải kết quả bổ sung hàng...')).toBeVisible()
      release()
      await expect(page.getByRole('link', { name: fixtureId, exact: true })).toBeVisible()
    } finally {
      release()
      await page.unroute(statusUrl)
    }
    await signOut(page)
  })

  test('captures protected list and detail at desktop and mobile sizes', async ({ page }, testInfo) => {
    await signIn(page, e2eCredentials.admin)
    for (const viewport of [{ name: 'desktop', width: 1440, height: 1024 }, { name: 'mobile', width: 390, height: 844 }]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.goto('/replenishment')
      await expect(page.getByRole('link', { name: fixtureId, exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(viewport.name + '-list.png'), mask: [page.locator('.user-menu')] })
      await page.getByRole('link', { name: fixtureId, exact: true }).click()
      await expect(page.getByRole('table', { name: 'Diễn biến tồn và đơn hàng theo ngày' })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(viewport.name + '-detail.png'), mask: [page.locator('.user-menu')] })
    }
    await signOut(page)
  })

  test('network failure is recoverable without a fabricated response', async ({ page }) => {
    await signIn(page, e2eCredentials.admin)
    await page.route(statusUrl, route => route.abort())
    await page.goto('/replenishment')
    await expect(page.getByText('Không thể tải dữ liệu bổ sung hàng. Vui lòng thử lại.')).toBeVisible()
    await page.unroute(statusUrl)
    await page.getByRole('button', { name: 'Thử lại' }).click()
    await expect(page.getByRole('link', { name: fixtureId, exact: true })).toBeVisible()
    await signOut(page)
  })

  test('mobile tables scroll internally while controls remain readable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await signIn(page, e2eCredentials.admin)
    await page.goto('/replenishment/runs/' + fixtureId)
    const region = page.getByRole('region', { name: 'Cuộn bảng so sánh chính sách' })
    await expect(region).toBeVisible()
    const geometry = await region.evaluate(element => {
      element.scrollLeft = element.scrollWidth
      return { document: document.documentElement.scrollWidth, viewport: innerWidth,
        content: element.scrollWidth, client: element.clientWidth, left: element.scrollLeft }
    })
    expect(geometry.document).toBeLessThanOrEqual(geometry.viewport + 1)
    expect(geometry.content).toBeGreaterThan(geometry.client)
    expect(geometry.left).toBeGreaterThan(0)
    await signOut(page)
  })
})

for (const [name, message] of [
  ['unavailable', 'Chưa có dữ liệu được duyệt để tính chính sách bổ sung hàng.'],
  ['failed', 'Chưa có chi phí đặt hàng.'],
  ['stale', 'Dự báo không bao phủ khoảng thời gian được yêu cầu.'],
  ['corrupt', 'Kết quả không hợp lệ hoặc không còn khả dụng.'],
  ['unsupported', 'Kết quả có định dạng không tương thích.'],
] as const) {
  test('real API shows ' + name + ' state', async ({ page }) => {
    test.skip(scenario !== name, 'Requires matching owned catalog mount')
    await signIn(page, e2eCredentials.admin)
    await page.goto('/replenishment')
    await expect(page.getByText(message, { exact: false })).toBeVisible()
    await signOut(page)
  })
}
