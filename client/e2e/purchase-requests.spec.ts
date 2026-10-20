import { expect, test, type Page as BrowserPage } from '@playwright/test'
import { apiAs, apiResponse, assertPurchaseRequestTarget, createPurchaseRequestFixture, purchaseRequestCredentials, realApi, signIn, signOut, storedToken } from './helpers'

declare const process: { env: Record<string, string | undefined> }

interface PurchaseRequest {
  id: number; request_number: string; warehouse_id: number; product_id: number; quantity: number;
  requested_by_id: number; status: string; workflow_managed: boolean; note: string | null;
  created_at: string; updated_at: string;
  decision: null | { kind: string; actor_id: number; decided_at: string; rejection_reason: string | null };
  fulfillment: null | { outbound_id: number; transaction_id: number; actor_id: number; fulfilled_at: string; quantity_before: number; quantity_after: number };
}
type Fixture = Awaited<ReturnType<typeof createPurchaseRequestFixture>>
interface Page<T> { items: T[]; total: number }

test.beforeEach(async ({ page, baseURL }) => {
  expect(baseURL).toBe('http://127.0.0.1:58081')
  purchaseRequestCredentials()
  await page.goto('/login')
  assertPurchaseRequestTarget(page)
})

async function prepare(page: BrowserPage) {
  await signIn(page, purchaseRequestCredentials().admin)
  return createPurchaseRequestFixture(page)
}
async function quantityAt(page: BrowserPage, fixture: Fixture) {
  const stock = await realApi<Page<{ quantity: number }>>(page, '/stock?warehouse_id=' + fixture.warehouse.id + '&product_id=' + fixture.product.id)
  return stock.items[0]?.quantity ?? 0
}
async function fillCreate(page: BrowserPage, fixture: Fixture, quantity: string) {
  await page.goto('/purchase-requests/new')
  await expect(page.getByRole('heading', { name: 'Tạo yêu cầu mua hàng', exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Kho hàng', exact: true }).selectOption(String(fixture.warehouse.id))
  await page.getByRole('combobox', { name: 'Sản phẩm', exact: true }).selectOption(String(fixture.product.id))
  await page.getByRole('spinbutton', { name: 'Số lượng', exact: true }).fill(quantity)
  await page.getByRole('textbox', { name: 'Ghi chú', exact: true }).fill('  Yêu cầu kiểm thử M4  ')
  await expect(page.getByRole('status').filter({ hasText: /không giữ chỗ/i })).toBeVisible()
  await page.getByRole('button', { name: 'Xem lại yêu cầu', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true })).toBeFocused()
}
async function submitCreate(page: BrowserPage): Promise<{ row: PurchaseRequest; key: string; input: unknown }> {
  const pending = apiResponse(page, '/purchase-requests', 'POST')
  await page.getByRole('dialog').getByRole('button', { name: 'Gửi yêu cầu mua hàng', exact: true }).click()
  const response = await pending
  expect(response.status()).toBe(201)
  const row = await response.json() as PurchaseRequest
  await expect(page).toHaveURL(new RegExp('/purchase-requests/' + row.id + '$'))
  return { row, key: response.request().headers()['idempotency-key'], input: response.request().postDataJSON() }
}
async function action(page: BrowserPage, id: number, kind: 'approve' | 'reject' | 'fulfill', name: string, confirm: string) {
  const response = apiResponse(page, '/purchase-requests/' + id + '/' + kind, 'POST')
  await page.getByRole('button', { name, exact: true }).click()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true })).toBeFocused()
  await page.getByRole('dialog').getByRole('button', { name: confirm, exact: true }).click()
  return response
}

test('client creates and tracks an owned request; staff approve and fulfill exactly once', async ({ page }) => {
  const fixture = await prepare(page)
  await signOut(page); await signIn(page, fixture.clients[0])
  await fillCreate(page, fixture, '3')
  await page.getByRole('dialog').press('Escape')
  await expect(page.getByRole('button', { name: 'Xem lại yêu cầu', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Xem lại yêu cầu', exact: true }).click()
  const created = await submitCreate(page)
  expect(created.key).toMatch(/^[0-9a-f-]{36}$/)
  expect(created.row.status).toBe('pending')
  expect(created.row.requested_by_id).toBe(fixture.clients[0].id)
  expect(created.row.note).toBe('Yêu cầu kiểm thử M4')
  const clientToken = await storedToken(page)
  await page.reload()
  await expect(page.getByText('Chờ duyệt', { exact: true })).toBeVisible()
  expect(await quantityAt(page, fixture)).toBe(10)
  await signOut(page); await signIn(page, fixture.clients[1])
  const tokenB = await storedToken(page)
  await apiAs(page, tokenB, '/purchase-requests/' + created.row.id, 'GET', undefined, 404)
  await apiAs(page, tokenB, '/purchase-requests/by-key/' + created.key, 'GET', undefined, 404)
  const ownB = await realApi<Page<PurchaseRequest>>(page, '/purchase-requests?product_id=' + fixture.product.id)
  expect(ownB.total).toBe(0)
  await signOut(page); await signIn(page, purchaseRequestCredentials().admin)
  await page.goto('/purchase-requests/' + created.row.id)
  const approved = await action(page, created.row.id, 'approve', 'Duyệt yêu cầu', 'Xác nhận duyệt')
  expect(approved.status()).toBe(200)
  expect(await quantityAt(page, fixture)).toBe(10)
  await signOut(page); await signIn(page, purchaseRequestCredentials().warehouse)
  await page.goto('/purchase-requests/' + created.row.id)
  const fulfilled = await action(page, created.row.id, 'fulfill', 'Xuất hàng', 'Xác nhận xuất hàng')
  expect(fulfilled.status()).toBe(200)
  const row = await fulfilled.json() as PurchaseRequest
  expect(row.status).toBe('fulfilled')
  expect(row.fulfillment).toMatchObject({ quantity_before: 10, quantity_after: 7 })
  await expect(page.getByRole('heading', { name: 'Tồn kho tại thời điểm xuất', exact: true })).toBeVisible()
  expect(await quantityAt(page, fixture)).toBe(7)
  const repeat = await realApi<PurchaseRequest>(page, '/purchase-requests/' + row.id + '/fulfill', 'POST', {})
  expect(repeat).toEqual(row)
  const createReplay = await page.request.post('/api/v1/purchase-requests', { headers: { Authorization: 'Bearer ' + clientToken, 'Idempotency-Key': created.key }, data: created.input })
  expect(createReplay.status()).toBe(200); expect(await createReplay.json()).toEqual(row)
  const transactions = await realApi<Page<{ id: number; transaction_type: string; outbound_id: number }>>(page, '/transactions?product_id=' + fixture.product.id)
  expect(transactions.total).toBe(2) // Fixture inbound plus exactly one customer outbound.
  expect(transactions.items.filter(item => item.transaction_type === 'outbound')).toMatchObject([{ id: row.fulfillment!.transaction_id, outbound_id: row.fulfillment!.outbound_id }])
  const purpose = await realApi<Page<{ transaction_id: number; purpose: string; transfer_id: null }>>(page, '/movement-provenance?transaction_id=' + row.fulfillment!.transaction_id)
  expect(purpose.items).toEqual([{ transaction_id: row.fulfillment!.transaction_id, purpose: 'purchase_request_fulfillment', transfer_id: null }])
})

test('admin rejection preserves reason and stock; incompatible repeats and forbidden roles have no effects', async ({ page }) => {
  const fixture = await prepare(page)
  await signOut(page); await signIn(page, fixture.clients[0])
  await fillCreate(page, fixture, '3')
  const created = await submitCreate(page)
  for (const kind of ['approve', 'reject', 'fulfill']) await realApi(page, '/purchase-requests/' + created.row.id + '/' + kind, 'POST', kind === 'reject' ? { rejection_reason: 'forged' } : {}, 403)
  await signOut(page); await signIn(page, purchaseRequestCredentials().admin)
  await realApi(page, '/purchase-requests', 'POST', { product_id: fixture.product.id, warehouse_id: fixture.warehouse.id, quantity: 3 }, 403)
  await page.goto('/purchase-requests/' + created.row.id)
  await page.getByRole('textbox', { name: 'Lý do từ chối', exact: true }).fill('  Cần xác nhận lại  ')
  const rejected = await action(page, created.row.id, 'reject', 'Từ chối yêu cầu', 'Xác nhận từ chối')
  expect(rejected.status()).toBe(200)
  const row = await rejected.json() as PurchaseRequest
  expect(row.decision?.rejection_reason).toBe('Cần xác nhận lại')
  expect(await realApi(page, '/purchase-requests/' + row.id + '/reject', 'POST', { rejection_reason: ' Cần xác nhận lại ' })).toEqual(row)
  await realApi(page, '/purchase-requests/' + row.id + '/reject', 'POST', { rejection_reason: 'Khác' }, 409)
  expect(await quantityAt(page, fixture)).toBe(10)
  await signOut(page); await signIn(page, purchaseRequestCredentials().warehouse)
  await realApi(page, '/purchase-requests', 'POST', { product_id: fixture.product.id, warehouse_id: fixture.warehouse.id, quantity: 3 }, 403)
  await realApi(page, '/purchase-requests/' + row.id + '/approve', 'POST', {}, 403)
  expect((await realApi<Page<unknown>>(page, '/transactions?product_id=' + fixture.product.id)).total).toBe(1)
})

test('insufficient stock retains approved request; inactive products cannot be requested', async ({ page }) => {
  const fixture = await prepare(page)
  await signOut(page); await signIn(page, fixture.clients[0])
  await fillCreate(page, fixture, '11')
  const created = await submitCreate(page)
  await signOut(page); await signIn(page, purchaseRequestCredentials().admin)
  await realApi(page, '/purchase-requests/' + created.row.id + '/approve', 'POST', {})
  await page.goto('/purchase-requests/' + created.row.id)
  const failed = await action(page, created.row.id, 'fulfill', 'Xuất hàng', 'Xác nhận xuất hàng')
  expect(failed.status()).toBe(409)
  await expect(page.getByRole('alert')).toBeVisible()
  expect((await realApi<PurchaseRequest>(page, '/purchase-requests/' + created.row.id)).status).toBe('approved')
  expect(await quantityAt(page, fixture)).toBe(10)
  const product = await realApi<{ sku: string; name: string; description: string | null; category_id: number; supplier_id: number | null; unit: string; reorder_level: number }>(page, '/products/' + fixture.product.id)
  await realApi(page, '/products/' + fixture.product.id, 'PUT', { sku: product.sku, name: product.name, description: product.description, category_id: product.category_id, supplier_id: product.supplier_id, unit: product.unit, reorder_level: product.reorder_level, is_active: false })
  await signOut(page); await signIn(page, fixture.clients[0])
  const token = await storedToken(page)
  const denied = await page.request.post('/api/v1/purchase-requests', { headers: { Authorization: 'Bearer ' + token, 'Idempotency-Key': crypto.randomUUID() }, data: { warehouse_id: fixture.warehouse.id, product_id: fixture.product.id, quantity: 1 } })
  expect(denied.status()).toBe(409); expect((await denied.json()).detail.code).toBe('PRODUCT_NOT_REQUESTABLE')
  await page.goto('/purchase-requests/new')
  await expect(page.getByRole('combobox', { name: 'Sản phẩm', exact: true }).getByRole('option', { name: fixture.product.sku + ' · ' + fixture.product.name, exact: true })).toHaveCount(0)
})

test('owned legacy request displays honest unknown history and is read-only for staff too', async ({ page }) => {
  const value = process.env.E2E_M4_LEGACY_REQUEST_ID ?? ''
  if (!/^[1-9]\d{0,9}$/.test(value) || Number(value) > 2147483647) throw new Error('Explicit parent-owned M4 legacy fixture identity is required.')
  await signIn(page, purchaseRequestCredentials().client)
  const me = await realApi<{ id: number }>(page, '/auth/me')
  const legacy = await realApi<PurchaseRequest>(page, '/purchase-requests/' + value)
  expect(legacy.requested_by_id).toBe(me.id)
  expect(legacy.workflow_managed).toBe(false)
  expect([legacy.note, legacy.decision, legacy.fulfillment]).toEqual([null, null, null])
  const product = await realApi<{ sku: string }>(page, '/products/' + legacy.product_id)
  expect(product.sku.startsWith('M4-LEGACY')).toBe(true)
  await page.goto('/purchase-requests/' + value)
  await expect(page.getByText(/Yêu cầu cũ chỉ có thể xem/)).toBeVisible()
  await signOut(page); await signIn(page, purchaseRequestCredentials().admin)
  await page.goto('/purchase-requests/' + value)
  await expect(page.getByText(/Yêu cầu cũ chỉ có thể xem/)).toBeVisible()
  for (const name of ['Duyệt yêu cầu', 'Từ chối yêu cầu', 'Xuất hàng']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  expect(await realApi<PurchaseRequest>(page, '/purchase-requests/' + value)).toEqual(legacy)
})

test('legal long content fits mobile detail and keeps list values readable inside its scrolling table', async ({ page }) => {
  const fixture = await prepare(page)
  const product = await realApi<{ sku: string; name: string; description: string | null; category_id: number; supplier_id: number | null; unit: string; reorder_level: number }>(page, '/products/' + fixture.product.id)
  const updated = await realApi<{ sku: string; name: string }>(page, '/products/' + fixture.product.id, 'PUT', { sku: product.sku.padEnd(80, 'S'), name: 'S'.repeat(200), description: product.description, category_id: product.category_id, supplier_id: product.supplier_id, unit: product.unit, reorder_level: product.reorder_level, is_active: true })
  Object.assign(fixture.product, updated)
  await signOut(page); await signIn(page, fixture.clients[0])
  await fillCreate(page, fixture, '3')
  await page.getByRole('dialog').press('Escape')
  await page.getByRole('textbox', { name: 'Ghi chú', exact: true }).fill('N'.repeat(2000))
  await page.getByRole('button', { name: 'Xem lại yêu cầu', exact: true }).click()
  const created = await submitCreate(page)
  expect(created.row.request_number.length).toBeGreaterThanOrEqual(35)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: created.row.request_number, exact: true })).toBeVisible()
  const detail = await page.locator('.purchase-panel').first().evaluate(panel => {
    const heading = panel.querySelector('h2')!
    return { documentWidth: document.documentElement.scrollWidth, viewport: innerWidth, panelRight: panel.getBoundingClientRect().right, headingRight: heading.getBoundingClientRect().right, headingClient: heading.clientWidth, headingScroll: heading.scrollWidth }
  })
  expect(detail.documentWidth).toBeLessThanOrEqual(detail.viewport + 1)
  expect(detail.headingRight).toBeLessThanOrEqual(detail.panelRight)
  expect(detail.headingScroll).toBeLessThanOrEqual(detail.headingClient + 1)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/purchase-requests')
  await page.getByRole('combobox', { name: 'Lọc sản phẩm', exact: true }).selectOption(String(fixture.product.id))
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  const row = page.getByRole('row').filter({ has: page.getByRole('link', { name: created.row.request_number, exact: true }) })
  const status = row.getByText('Chờ duyệt', { exact: true })
  await expect(status).toBeVisible()
  const semanticValues = await row.locator('.purchase-nowrap').evaluateAll(elements => elements.map(element => ({ whiteSpace: getComputedStyle(element).whiteSpace, client: element.clientWidth, scroll: element.scrollWidth })))
  expect(semanticValues).toHaveLength(5)
  expect(semanticValues.every(value => value.whiteSpace === 'nowrap' && value.scroll <= value.client + 1)).toBe(true)
  await page.setViewportSize({ width: 390, height: 844 })
  const table = page.locator('.ui-data-table-wrapper')
  const mobileTable = await table.evaluate(wrapper => {
    wrapper.scrollLeft = wrapper.scrollWidth
    return { overflowX: getComputedStyle(wrapper).overflowX, client: wrapper.clientWidth, scroll: wrapper.scrollWidth, left: wrapper.scrollLeft, documentWidth: document.documentElement.scrollWidth, viewport: innerWidth }
  })
  expect(mobileTable.overflowX).toBe('auto')
  expect(mobileTable.scroll).toBeGreaterThan(mobileTable.client)
  expect(mobileTable.left).toBeGreaterThan(0)
  expect(mobileTable.documentWidth).toBeLessThanOrEqual(mobileTable.viewport + 1)
})
