import { expect, test } from '@playwright/test'
import { apiAs, e2eCredentials, signIn, signOut, storedToken } from './helpers'

test.skip(process.env.E2E_ASSISTANT !== '1', 'Requires the isolated assistant stack')

for (const width of [390, 1440]) {
  test(`assistant conversation and cited source at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await signIn(page, width === 390 ? e2eCredentials.seededWarehouse : e2eCredentials.admin)
    await page.getByRole('link', { name: 'Trợ lý kho', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Trợ lý kho' })).toBeVisible()
    const question = page.getByRole('textbox', { name: 'Câu hỏi', exact: true })
    await question.fill('Chuyển kho thế nào?')
    await question.press('Tab')
    await expect(page.getByRole('button', { name: 'Gửi câu hỏi' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByText('Chọn kho nguồn, kho đích khác kho nguồn, sản phẩm và số lượng.', { exact: true })).toBeVisible()
    const citation = page.getByRole('button', { name: 'Chuyển hàng giữa hai kho' })
    await citation.focus()
    await citation.press('Enter')
    await expect(page.getByRole('heading', { name: 'Chuyển hàng giữa hai kho' })).toBeFocused()
    await expect(page.getByText('Phiên bản 1')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await signOut(page)
    await page.goto('/assistant')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByText('Chuyển kho thế nào?')).toHaveCount(0)
  })
}

test('client cannot open the assistant or call its API', async ({ page }) => {
  await signIn(page, e2eCredentials.seededClient)
  await expect(page.getByRole('link', { name: 'Trợ lý kho', exact: true })).toHaveCount(0)
  await page.goto('/assistant')
  await expect(page).toHaveURL(/\/products$/)
  await apiAs(page, await storedToken(page), '/assistant/chat', 'POST', { question: 'Chuyển kho thế nào?' }, 403)
})

test('retry resends the same question after a temporary service failure', async ({ page }) => {
  await signIn(page, e2eCredentials.admin)
  await page.goto('/assistant')
  await page.route('**/api/v1/assistant/chat', route => route.fulfill({
    status: 503,
    json: { detail: { code: 'ASSISTANT_PROVIDER_ERROR', message: 'Trợ lý tạm thời không khả dụng.' } },
  }), { times: 1 })

  const question = 'Chuyển kho thế nào?'
  await page.getByRole('textbox', { name: 'Câu hỏi', exact: true }).fill(question)
  await page.getByRole('button', { name: 'Gửi câu hỏi' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  const retry = page.getByRole('button', { name: 'Thử lại', exact: true })
  await retry.focus()
  await retry.press('Enter')
  await expect(page.getByRole('button', { name: 'Chuyển hàng giữa hai kho' })).toBeVisible()
  await expect(page.getByText(question, { exact: true })).toHaveCount(1)
})

test('a delayed response from a previous session is discarded after account change', async ({ page }) => {
  await signIn(page, e2eCredentials.admin)
  await page.goto('/assistant')
  const question = 'Câu hỏi thuộc phiên trước'
  const oldAnswer = 'Phản hồi thuộc phiên trước'
  let release!: () => void
  let finishRoute!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  const routeHandled = new Promise<void>(resolve => { finishRoute = resolve })
  await page.route('**/api/v1/assistant/chat', async route => {
    try {
      await pending
      await route.fulfill({ json: { status: 'answered', answer: oldAnswer, citations: [] } })
    } catch {
      // The browser may abort the old request when signing out.
    } finally {
      finishRoute()
    }
  }, { times: 1 })
  try {
    await page.getByRole('textbox', { name: 'Câu hỏi', exact: true }).fill(question)
    const oldRequest = page.waitForRequest('**/api/v1/assistant/chat', { timeout: 10_000 })
    await page.getByRole('button', { name: 'Gửi câu hỏi' }).click()
    await oldRequest
    await expect(page.getByText('Đang tìm tài liệu và soạn câu trả lời…')).toBeVisible()
    await signOut(page)
    await signIn(page, e2eCredentials.seededWarehouse)
    await page.goto('/assistant')
  } finally {
    release()
  }
  await routeHandled
  await expect(page.getByRole('heading', { name: 'Trợ lý kho' })).toBeVisible()
  await expect(page.getByText(question, { exact: true })).toHaveCount(0)
  await expect(page.getByText(oldAnswer, { exact: true })).toHaveCount(0)
})
