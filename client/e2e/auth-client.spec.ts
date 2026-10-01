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
  const productsResponsePromise = page.waitForResponse((response) => response.request().method() === 'GET' && new URL(response.url()).pathname === '/api/v1/products')
  await page.reload()
  const productsResponse = await productsResponsePromise
  expect(productsResponse.status()).toBe(200)
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('table', { name: 'Product ledger' }).or(page.getByText('No products match these filters.'))).toBeVisible()
  await expect(page.getByRole('link', { name: 'Stock' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Warehouses' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Inbound' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Outbound' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Transactions' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Create product' })).toHaveCount(0)

  const stockResponsePromise = page.waitForResponse((response) => response.request().method() === 'GET' && new URL(response.url()).pathname === '/api/v1/stock')
  await page.getByRole('link', { name: 'Stock' }).click()
  const stockResponse = await stockResponsePromise
  expect(stockResponse.status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Stock' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('table', { name: 'Stock quantity ledger' }).or(page.getByText('No stock records match these filters.'))).toBeVisible()
})
