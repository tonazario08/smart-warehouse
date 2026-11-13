import { expect, test } from '@playwright/test'
import { apiAs, signIn, storedToken, uniqueRunId } from './helpers'

declare const process: { env: Record<string, string | undefined> }

const viewports = process.env.E2E_PASSWORD_RECOVERY === '1'
  ? [{ width: 390, height: 844 }, { width: 1440, height: 900 }]
  : []

for (const viewport of viewports) {
  test(`password recovery and in-session change at ${viewport.width}px`, async ({ page }) => {
    const target = new URL(process.env.E2E_BASE_URL ?? '')
    if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || target.port !== '58081' || target.username || target.password) throw new Error('Password recovery requires the isolated loopback test stack.')
    await page.setViewportSize(viewport)
    const credentials = { email: `recovery-${uniqueRunId()}@example.com`, password: 'initial-password-2026' }
    const resetPassword = 'reset-password-2026'
    const changedPassword = 'changed-password-2026'
    await page.goto('/login')
    await apiAs(page, null, '/auth/register', 'POST', credentials, 201)
    await page.getByRole('link', { name: 'Quên mật khẩu?' }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByLabel('Email').fill(credentials.email)
    await page.getByRole('button', { name: 'Gửi liên kết' }).click()
    await expect(page.getByRole('status')).toContainText(/nếu.*tài khoản/i)

    let resetUrl: string | null = null
    await expect.poll(async () => {
      const response = await page.request.get('/api/v1/_test/password-inbox', { params: { email: credentials.email } })
      if (!response.ok()) return false
      const inbox = await response.json() as { reset_url: string | null; change_notices: number }
      resetUrl = inbox.reset_url
      return Boolean(resetUrl)
    }).toBe(true)
    const link = new URL(resetUrl!)
    expect(link.origin === target.origin && link.pathname === '/reset-password').toBe(true)
    const fragment = link.hash
    await page.goto('/reset-password')
    await page.evaluate(value => history.replaceState(history.state, '', location.pathname + value), fragment)
    await page.reload()
    await expect.poll(() => page.evaluate(() => location.hash === '')).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByLabel('Mật khẩu mới', { exact: true }).fill(resetPassword)
    await page.getByLabel('Xác nhận mật khẩu mới').fill(resetPassword)
    await page.getByRole('button', { name: 'Đặt lại mật khẩu' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('status')).toContainText(/thành công/i)
    await signIn(page, { email: credentials.email, password: resetPassword })
    const staleToken = await storedToken(page)
    expect(Boolean(staleToken)).toBe(true)
    await page.locator('.user-menu__trigger').click()
    await page.getByRole('link', { name: 'Đổi mật khẩu' }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByLabel('Mật khẩu hiện tại').fill(resetPassword)
    await page.getByLabel('Mật khẩu mới', { exact: true }).fill(changedPassword)
    await page.getByLabel('Xác nhận mật khẩu mới').fill(changedPassword)
    await page.getByRole('button', { name: 'Đổi mật khẩu' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('status')).toContainText(/thành công/i)
    await apiAs(page, staleToken, '/auth/me', 'GET', undefined, 401)
    await expect.poll(async () => {
      const result = await page.request.get('/api/v1/_test/password-inbox', { params: { email: credentials.email } })
      if (!result.ok()) return false
      const inbox = await result.json() as { change_notices: number }
      return inbox.change_notices >= 2
    }).toBe(true)
    await signIn(page, { email: credentials.email, password: changedPassword })
  })
}
