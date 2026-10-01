import { expect, test } from '@playwright/test'
import { signIn, uniqueRunId } from './helpers'

test('anonymous registers as client and receives read-only catalogue access', async ({ page }) => {
  const credentials = {
    email: `client-${uniqueRunId()}@example.com`,
    password: 'client-password-2026',
  }

  await page.goto('/register')
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password').fill(credentials.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('status')).toContainText('Account created')

  await signIn(page, credentials)
  await expect(page).toHaveURL(/\/products$/)
  await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Stock' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Warehouses' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Inbound' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Outbound' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Transactions' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Create product' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Stock' }).click()
  await expect(page.getByRole('heading', { name: 'Stock' })).toBeVisible()
})
