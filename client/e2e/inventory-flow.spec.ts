import { expect, test, type Page } from '@playwright/test'
import { apiResponse, createManagedUser, createMasterData, e2eCredentials, realApi, runNames, selectOptionByText, signIn, signOut, uniqueRunId } from './helpers'

async function dashboardMetric(page: Page, label: string) {
  const card = page.getByLabel('Chỉ số tổng quan', { exact: true }).locator('article').filter({ has: page.getByText(label, { exact: true }) })
  return Number((await card.locator('strong').innerText()).replace(/\D/g, ''))
}
async function fillMovement(page: Page, type: 'inbound' | 'outbound', product: string, warehouse: string, quantity: string, reference: string, note: string) {
  await page.goto('/' + type + '/new')
  await selectOptionByText(page.getByRole('combobox', { name: 'Kho hàng', exact: true }), warehouse)
  await selectOptionByText(page.getByRole('combobox', { name: 'Sản phẩm', exact: true }), product)
  await page.getByLabel('Số lượng', { exact: true }).fill(quantity)
  await page.getByLabel('Mã phiếu', { exact: true }).fill(reference)
  await page.getByLabel('Ghi chú', { exact: true }).fill(note)
}
async function preview(page: Page, label: string, quantity: string) {
  const impact = page.locator('.movement-stock-impact')
  await expect(impact.locator('dl > div').filter({ has: page.getByText(label, { exact: true }) }).locator('dd')).toHaveText(quantity + ' cái')
}

test('Figma inbound/outbound/409 updates real stock, supported history, dashboard and client guards', async ({ page }) => {
  const names = runNames('FLOW')
  const operator = { email: 'operator-' + uniqueRunId() + '@example.com', password: 'warehouse-operator-password-2026' }
  const inboundReference = 'IN-' + uniqueRunId(), outboundReference = 'OUT-' + uniqueRunId()
  await signIn(page, e2eCredentials.admin)
  const initialProducts = await dashboardMetric(page, 'Tổng sản phẩm')
  const initialStock = await dashboardMetric(page, 'Số lượng tồn kho')
  const ids = await createMasterData(page, names)
  const managed = await createManagedUser(page, operator, 'warehouse')
  await signOut(page)

  await signIn(page, operator)
  const productOption = names.sku + ' · ' + names.product
  await fillMovement(page, 'inbound', productOption, names.warehouse, '20', inboundReference, 'Ghi chú nhập thật')
  await preview(page, 'Tồn hiện tại', '0')
  await preview(page, 'Sau khi nhập', '20')
  const inbound = apiResponse(page, '/inbounds', 'POST')
  await page.getByRole('button', { name: 'Xác nhận nhập kho', exact: true }).click()
  expect((await inbound).status()).toBe(201)
  await expect(page).toHaveURL(/\/inbound$/)
  await page.getByRole('textbox', { name: 'Tìm sản phẩm hoặc kho hàng', exact: true }).fill(names.sku)
  await expect(page.getByRole('row').filter({ hasText: names.product })).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: names.product })).toContainText('20')

  await fillMovement(page, 'outbound', productOption, names.warehouse, '7', outboundReference, 'Ghi chú xuất thật')
  await preview(page, 'Tồn hiện tại', '20')
  await preview(page, 'Sau khi xuất', '13')
  const outbound = apiResponse(page, '/outbounds', 'POST')
  await page.getByRole('button', { name: 'Xác nhận xuất kho', exact: true }).click()
  expect((await outbound).status()).toBe(201)
  await expect(page).toHaveURL(/\/outbound$/)
  await page.getByRole('textbox', { name: 'Tìm sản phẩm hoặc kho hàng', exact: true }).fill(names.sku)
  await expect(page.getByRole('row').filter({ hasText: names.product })).toContainText('7')

  const query = '?warehouse_id=' + ids.warehouseId + '&product_id=' + ids.productId + '&page_size=100'
  for (const [path, reference, note, quantity] of [
    ['/inbounds', inboundReference, 'Ghi chú nhập thật', 20],
    ['/outbounds', outboundReference, 'Ghi chú xuất thật', 7],
  ] as const) {
    const records = await realApi<{ items: { reference: string; note: string; quantity: number; created_by_id: number; created_at: string }[]; total: number }>(page, path + query)
    expect(records.total).toBe(1)
    const record = records.items[0]
    expect(record.reference === reference && record.note === note && record.quantity === quantity && record.created_by_id === managed.id && Number.isFinite(Date.parse(record.created_at))).toBe(true)
  }

  await fillMovement(page, 'outbound', productOption, names.warehouse, '14', 'REJECT-' + uniqueRunId(), 'Ghi chú phải giữ trong bản nháp')
  await preview(page, 'Tồn hiện tại', '13')
  const rejected = apiResponse(page, '/outbounds', 'POST')
  await page.getByRole('button', { name: 'Xác nhận xuất kho', exact: true }).click()
  expect((await rejected).status()).toBe(409)
  await expect(page.getByRole('alert')).toContainText('không đủ')
  expect(await page.getByLabel('Số lượng', { exact: true }).inputValue() === '14').toBe(true)
  expect(await page.getByLabel('Ghi chú', { exact: true }).inputValue() === 'Ghi chú phải giữ trong bản nháp').toBe(true)
  const stock = await realApi<{ items: { quantity: number }[]; total: number }>(page, '/stock' + query)
  expect(stock.total === 1 && stock.items[0].quantity === 13).toBe(true)
  const transactions = await realApi<{ items: { transaction_type: string; quantity: number }[]; total: number }>(page, '/transactions' + query)
  expect(transactions.total).toBe(2)
  expect(transactions.items.some(item => item.transaction_type === 'inbound' && item.quantity === 20)).toBe(true)
  expect(transactions.items.some(item => item.transaction_type === 'outbound' && item.quantity === 7)).toBe(true)

  await page.goto('/inventory')
  await page.getByRole('textbox', { name: 'Tìm kiếm tồn kho', exact: true }).fill(names.sku)
  await selectOptionByText(page.getByRole('combobox', { name: 'Lọc theo kho hàng', exact: true }), names.warehouse)
  const row = page.getByRole('row').filter({ hasText: names.sku })
  await expect(row).toHaveCount(1)
  await expect(row.getByRole('cell', { name: '13 cái', exact: true })).toBeVisible()
  await row.getByRole('button').click()
  const history = page.getByRole('table', { name: 'Lịch sử nhập và xuất của sản phẩm tại kho', exact: true })
  await expect(history).toContainText(inboundReference)
  await expect(history).toContainText(outboundReference)
  await expect(history).toContainText('Ghi chú nhập thật')
  await expect(history).toContainText('Ghi chú xuất thật')
  await expect(history.getByText('Tài khoản #' + managed.id, { exact: true })).toHaveCount(2)

  await signOut(page)
  await signIn(page, e2eCredentials.admin)
  await page.goto('/dashboard')
  await expect.poll(() => dashboardMetric(page, 'Tổng sản phẩm')).toBe(initialProducts + 1)
  await expect.poll(() => dashboardMetric(page, 'Số lượng tồn kho')).toBe(initialStock + 13)
  await page.goto('/products')
  await page.getByRole('textbox', { name: 'Tìm kiếm sản phẩm', exact: true }).fill(names.sku)
  await page.getByRole('button', { name: 'Xóa ' + names.product, exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Xóa sản phẩm?' })
  const deleteRejected = apiResponse(page, '/products/' + ids.productId, 'DELETE')
  await dialog.getByRole('button', { name: 'Xóa sản phẩm', exact: true }).click()
  expect((await deleteRejected).status()).toBe(409)
  await expect(dialog.getByRole('alert')).toContainText('tham chiếu')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Hủy', exact: true }).click()
  await realApi(page, '/products/' + ids.productId)
  await signOut(page)

  await signIn(page, e2eCredentials.seededClient)
  await page.goto('/products')
  await page.getByRole('textbox', { name: 'Tìm kiếm sản phẩm', exact: true }).fill(names.sku)
  await expect(page.getByRole('row').filter({ hasText: names.sku })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Xóa ' + names.product, exact: true })).toHaveCount(0)
  let forbiddenHistoryCalls = 0
  page.on('request', request => { if (/\/api\/v1\/(inbounds|outbounds|transactions)(\?|$)/.test(request.url())) forbiddenHistoryCalls++ })
  await page.goto('/inventory/' + ids.warehouseId + '/' + ids.productId)
  await expect(page.getByRole('heading', { name: 'Chi tiết tồn kho', exact: true })).toBeVisible()
  await expect(page.getByText('Bạn không có quyền xem lịch sử nhập và xuất kho.', { exact: true })).toBeVisible()
  expect(forbiddenHistoryCalls).toBe(0)
  for (const deniedPath of ['/inbound', '/outbound/new', '/products/new']) {
    await page.goto(deniedPath)
    await expect(page).toHaveURL(/\/products$/)
  }
  await realApi(page, '/transactions' + query, 'GET', undefined, 403)
  await signOut(page)
  // This disposable movement fixture intentionally retains stock 13 plus immutable history.
})
