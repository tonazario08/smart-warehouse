import { expect, test, type Locator, type Page } from '@playwright/test'
import { createManagedUser, createMasterData, e2eCredentials, selectOptionByText, signIn, signOut, uniqueRunId } from './helpers'

async function dashboardMetric(page: Page, label: string) {
  const card = page.getByLabel('Warehouse status').locator('div').filter({ hasText: label })
  return Number(await card.locator('strong').innerText())
}

async function filterInventory(page: Page, product: string, warehouse: string) {
  const filters = page.getByRole('form', { name: 'Filter inventory' })
  await selectOptionByText(filters.getByRole('combobox', { name: 'Warehouse', exact: true }), warehouse)
  await selectOptionByText(filters.getByRole('combobox', { name: 'Product', exact: true }), product)
  await filters.getByRole('button', { name: 'Apply filters' }).click()
}

async function expectMovementRow(table: Locator, reference: string, quantity: string) {
  const row = table.getByRole('row').filter({ hasText: reference })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText(quantity)
}

test('warehouse movement flow updates stock, history, dashboard, and client permissions', async ({ page }) => {
  const runId = uniqueRunId()
  const operator = {
    email: `operator-${runId}@example.com`,
    password: 'warehouse-operator-password-2026',
  }
  const names = {
    category: `Flow Category ${runId}`,
    supplier: `Flow Supplier ${runId}`,
    supplierEmail: `flow-supplier-${runId}@example.com`,
    sku: `FLOW-${runId}`.toUpperCase(),
    product: `Flow Product ${runId}`,
    warehouseCode: `FLOW-${runId}`.toUpperCase(),
    warehouse: `Flow Warehouse ${runId}`,
  }
  const productOption = `${names.sku} · ${names.product}`
  const warehouseOption = `${names.warehouseCode} · ${names.warehouse}`
  const inboundReference = `IN-${runId}`
  const outboundReference = `OUT-${runId}`

  await signIn(page, e2eCredentials.admin)
  const initialProducts = await dashboardMetric(page, 'Products')
  const initialStock = await dashboardMetric(page, 'Total stock')
  await createMasterData(page, names)
  await createManagedUser(page, operator, 'warehouse')
  await signOut(page)

  await signIn(page, operator)
  await page.getByRole('link', { name: 'Inbound' }).click()
  const inboundForm = page.getByRole('form', { name: 'Inbound movement' })
  await inboundForm.getByLabel('Warehouse for inbound').selectOption({ label: warehouseOption })
  await inboundForm.getByLabel('Product for inbound').selectOption({ label: productOption })
  await inboundForm.getByLabel('Inbound quantity').fill('20')
  await inboundForm.getByLabel('Reference').fill(inboundReference)
  await inboundForm.getByRole('button', { name: 'Record inbound' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Inbound recorded' })).toBeVisible()
  await expectMovementRow(page.getByRole('table', { name: 'Inbound movement ledger' }), inboundReference, '20')

  await page.getByRole('link', { name: 'Outbound' }).click()
  const outboundForm = page.getByRole('form', { name: 'Outbound movement' })
  await outboundForm.getByLabel('Warehouse for outbound').selectOption({ label: warehouseOption })
  await outboundForm.getByLabel('Product for outbound').selectOption({ label: productOption })
  await outboundForm.getByLabel('Outbound quantity').fill('7')
  await outboundForm.getByLabel('Reference').fill(outboundReference)
  await outboundForm.getByRole('button', { name: 'Record outbound' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Outbound recorded' })).toBeVisible()
  await expectMovementRow(page.getByRole('table', { name: 'Outbound movement ledger' }), outboundReference, '7')

  await page.getByRole('link', { name: 'Stock' }).click()
  await filterInventory(page, productOption, warehouseOption)
  const stockRow = page.getByRole('table', { name: 'Stock quantity ledger' }).getByRole('row').filter({ hasText: names.product })
  await expect(stockRow).toHaveCount(1)
  await expect(stockRow.getByText('13', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Transactions' }).click()
  await filterInventory(page, productOption, warehouseOption)
  const transactionRows = page.getByRole('table', { name: 'Transaction history' }).getByRole('row').filter({ hasText: names.product })
  await expect(transactionRows).toHaveCount(2)
  await expect(transactionRows.filter({ hasText: 'Inbound' })).toContainText('20')
  await expect(transactionRows.filter({ hasText: 'Outbound' })).toContainText('7')

  await signOut(page)
  await signIn(page, e2eCredentials.admin)
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await expect.poll(() => dashboardMetric(page, 'Products')).toBe(initialProducts + 1)
  await expect.poll(() => dashboardMetric(page, 'Total stock')).toBe(initialStock + 13)

  await signOut(page)
  await signIn(page, e2eCredentials.seededClient)
  await page.goto('/products')
  await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible()
  const clientProductRow = page.getByRole('table', { name: 'Product ledger' }).getByRole('row').filter({ hasText: names.sku })
  await expect(clientProductRow).toHaveCount(1)
  await expect(clientProductRow).toContainText(names.product)
  await page.getByRole('link', { name: 'Stock' }).click()
  await expect(page.getByRole('heading', { name: 'Stock' })).toBeVisible()
  await filterInventory(page, productOption, warehouseOption)
  const clientStockRow = page.getByRole('table', { name: 'Stock quantity ledger' }).getByRole('row').filter({ hasText: names.product })
  await expect(clientStockRow).toHaveCount(1)
  await expect(clientStockRow.getByText('13', { exact: true })).toBeVisible()
  for (const deniedPath of ['/inbounds', '/outbounds', '/transactions']) {
    await page.goto(deniedPath)
    await expect(page).toHaveURL(/\/forbidden$/)
    await expect(page.getByRole('heading', { name: 'Permission required' })).toBeVisible()
  }
  await page.goto('/stock')
  await expect(page.getByRole('heading', { name: 'Stock' })).toBeVisible()
})
