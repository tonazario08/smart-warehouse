import { expect, test, type Page as BrowserPage } from '@playwright/test'
import { apiResponse, assertTransferTarget, createTransferFixture, e2eCredentials, realApi, signIn, signOut, storedToken } from './helpers'
import type { Transfer } from '../src/features/transfers/types'
import type { Page, Stock, Transaction } from '../src/types'

test.beforeEach(async ({ page, baseURL }) => {
  expect(baseURL).toBe('http://127.0.0.1:58080')
  await page.goto('/login')
  assertTransferTarget(page)
})

async function prepare(page: BrowserPage) {
  await signIn(page, e2eCredentials.admin)
  return createTransferFixture(page)
}
async function fill(page: BrowserPage, fixture: Awaited<ReturnType<typeof createTransferFixture>>, quantity: string) {
  await page.goto('/transfers/new')
  await page.getByRole('combobox', { name: 'Kho nguồn', exact: true }).selectOption(String(fixture.source.id))
  await page.getByRole('combobox', { name: 'Kho đích', exact: true }).selectOption(String(fixture.destination.id))
  await page.getByRole('combobox', { name: 'Sản phẩm', exact: true }).selectOption(String(fixture.product.id))
  await page.getByRole('spinbutton', { name: 'Số lượng', exact: true }).fill(quantity)
  await page.getByRole('button', { name: 'Xem lại chuyển kho', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true })).toBeFocused()
}
async function assertRealPair(page: BrowserPage, fixture: Awaited<ReturnType<typeof createTransferFixture>>, transfer: Transfer) {
  expect([transfer.source_quantity_before, transfer.source_quantity_after, transfer.destination_quantity_before, transfer.destination_quantity_after]).toEqual([10, 7, 2, 5])
  const stock = await realApi<Page<Stock>>(page, '/stock?product_id=' + fixture.product.id)
  expect(stock.items.reduce((sum, row) => sum + row.quantity, 0)).toBe(12)
  expect(stock.items.find(row => row.warehouse_id === fixture.source.id)?.quantity).toBe(7)
  expect(stock.items.find(row => row.warehouse_id === fixture.destination.id)?.quantity).toBe(5)
  const history = await realApi<Page<Transaction>>(page, '/transactions?product_id=' + fixture.product.id)
  expect(history.items.filter(row => row.id === transfer.outbound_transaction_id)).toMatchObject([{ transaction_type: 'outbound', outbound_id: transfer.outbound_id, warehouse_id: fixture.source.id, quantity: 3 }])
  expect(history.items.filter(row => row.id === transfer.inbound_transaction_id)).toMatchObject([{ transaction_type: 'inbound', inbound_id: transfer.inbound_id, warehouse_id: fixture.destination.id, quantity: 3 }])
  const provenance = await realApi<Page<{ transaction_id: number; purpose: string; transfer_id: number }>>(page, '/movement-provenance?transfer_id=' + transfer.id)
  expect(provenance.items).toEqual([
    { transaction_id: transfer.outbound_transaction_id, purpose: 'transfer_out', transfer_id: transfer.id },
    { transaction_id: transfer.inbound_transaction_id, purpose: 'transfer_in', transfer_id: transfer.id },
  ])
}

for (const role of ['admin', 'warehouse'] as const) test('real ' + role + ' transfer, paired history and exact-key replay preserve stock', async ({ page }) => {
  const fixture = await prepare(page)
  if (role === 'warehouse') { await signOut(page); await signIn(page, e2eCredentials.seededWarehouse) }
  await expect(page.getByRole('link', { name: 'Chuyển kho', exact: true })).toBeVisible()
  await fill(page, fixture, '3')
  await expect(page.getByRole('dialog')).toContainText('Ngừng hoạt động')
  await page.getByRole('dialog').press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Xem lại chuyển kho', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Xem lại chuyển kho', exact: true }).click()
  const completed = apiResponse(page, '/transfers', 'POST')
  await page.getByRole('dialog').getByRole('button', { name: 'Xác nhận chuyển kho', exact: true }).click()
  const response = await completed
  expect(response.status()).toBe(201)
  const transfer = await response.json() as Transfer
  await expect(page).toHaveURL(new RegExp('/transfers/' + transfer.id + '$'))
  await expect(page.getByRole('heading', { name: 'Tồn kho tại thời điểm chuyển', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: '7 cái', exact: true })).toBeVisible()
  await assertRealPair(page, fixture, transfer)
  const token = await storedToken(page)
  const key = response.request().headers()['idempotency-key']
  expect(key).toMatch(/^[0-9a-f-]{36}$/)
  const replay = await page.request.post('/api/v1/transfers', { headers: { Authorization: 'Bearer ' + token, 'Idempotency-Key': key }, data: response.request().postDataJSON() })
  expect(replay.status()).toBe(200)
  expect(await replay.json()).toEqual(transfer)
  await assertRealPair(page, fixture, transfer)
})

test('insufficient source rejects atomically and retains the editable draft', async ({ page }) => {
  const fixture = await prepare(page)
  await fill(page, fixture, '11')
  const failed = apiResponse(page, '/transfers', 'POST')
  await page.getByRole('dialog').getByRole('button', { name: 'Xác nhận chuyển kho', exact: true }).click()
  expect((await failed).status()).toBe(409)
  await expect(page.getByRole('alert')).toContainText('Số lượng tồn kho')
  await expect(page.getByRole('spinbutton', { name: 'Số lượng', exact: true })).toHaveValue('11')
  const stock = await realApi<Page<Stock>>(page, '/stock?product_id=' + fixture.product.id)
  expect(stock.items.map(row => row.quantity).sort((a, b) => a - b)).toEqual([2, 10])
  expect((await realApi<Page<Transfer>>(page, '/transfers?product_id=' + fixture.product.id)).total).toBe(0)
})

test('client is denied all transfer routes and direct mutation without effects', async ({ page }) => {
  const fixture = await prepare(page)
  await signOut(page); await signIn(page, e2eCredentials.seededClient)
  await expect(page.getByRole('link', { name: 'Chuyển kho', exact: true })).toHaveCount(0)
  for (const path of ['/transfers', '/transfers/new', '/transfers/1']) {
    await page.goto(path); await expect(page).toHaveURL(/\/products$/)
  }
  const token = await storedToken(page)
  const denied = await page.request.post('/api/v1/transfers', { headers: { Authorization: 'Bearer ' + token, 'Idempotency-Key': crypto.randomUUID() }, data: { source_warehouse_id: fixture.source.id, destination_warehouse_id: fixture.destination.id, product_id: fixture.product.id, quantity: 3 } })
  expect(denied.status()).toBe(403)
  await signOut(page); await signIn(page, e2eCredentials.admin)
  expect((await realApi<Page<Transfer>>(page, '/transfers?product_id=' + fixture.product.id)).total).toBe(0)
})

test('committed response loss recovers through the same browser key without another movement', async ({ page }) => {
  const fixture = await prepare(page)
  let drop = true
  await page.route('**/api/v1/transfers', async route => {
    if (route.request().method() === 'POST' && drop) {
      drop = false
      const committed = await route.fetch()
      expect(committed.status()).toBe(201)
      await route.abort('failed')
    } else await route.continue()
  })
  await fill(page, fixture, '3')
  await page.getByRole('dialog').getByRole('button', { name: 'Xác nhận chuyển kho', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Chưa xác định kết quả', exact: true })).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Số lượng', exact: true })).toBeDisabled()
  const recovered = apiResponse(page, '/transfers', 'POST')
  await page.getByRole('button', { name: 'Thử lại cùng yêu cầu', exact: true }).click()
  const response = await recovered
  expect(response.status()).toBe(200)
  const transfer = await response.json() as Transfer
  await expect(page).toHaveURL(new RegExp('/transfers/' + transfer.id + '$'))
  await assertRealPair(page, fixture, transfer)
  expect((await realApi<Page<Transfer>>(page, '/transfers?product_id=' + fixture.product.id)).total).toBe(1)
})
