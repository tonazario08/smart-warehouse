import { expect, test } from '@playwright/test'
import { createManagedUser, createMasterData, e2eCredentials, signIn, uniqueRunId } from './helpers'

test('seeded admin manages warehouse data and sees password-safe user audit evidence', async ({ page }) => {
  const runId = uniqueRunId()
  const operator = {
    email: `managed-${runId}@example.com`,
    password: 'managed-user-password-2026',
  }
  const names = {
    category: `E2E Category ${runId}`,
    supplier: `E2E Supplier ${runId}`,
    supplierEmail: `supplier-${runId}@example.com`,
    sku: `E2E-${runId}`.toUpperCase(),
    product: `E2E Product ${runId}`,
    warehouseCode: `E2E-${runId}`.toUpperCase(),
    warehouse: `E2E Warehouse ${runId}`,
  }

  await signIn(page, e2eCredentials.admin)
  await expect(page).toHaveURL(/\/dashboard$/)
  await createMasterData(page, names)
  let row = await createManagedUser(page, operator, 'warehouse')

  await row.getByRole('button', { name: `Change role for ${operator.email}` }).click()
  const roleSelect = row.getByLabel(`Confirm role change for ${operator.email}`)
  await expect(roleSelect.getByRole('option', { name: 'Admin' })).toHaveCount(0)
  await roleSelect.selectOption('client')
  await row.getByRole('button', { name: 'Confirm role change' }).click()
  await expect(page.getByRole('status')).toContainText('Role updated')
  row = page.getByRole('row').filter({ hasText: operator.email })
  await expect(row).toContainText('client')

  await row.getByRole('button', { name: `Deactivate ${operator.email}` }).click()
  await row.getByRole('button', { name: 'Confirm deactivation' }).click()
  await expect(page.getByRole('status')).toContainText('Status updated')
  row = page.getByRole('row').filter({ hasText: operator.email })
  await expect(row).toContainText('Inactive')

  await page.getByRole('link', { name: 'Audit' }).click()
  await expect(page.getByRole('heading', { name: 'Audit' })).toBeVisible()
  const audit = page.getByRole('table', { name: 'Administrative audit ledger' })
  await expect(audit).toContainText('user.created')
  await expect(audit).toContainText('user.role_changed')
  await expect(audit).toContainText('user.status_changed')
  await expect(audit).toContainText(operator.email)
  await expect(audit).not.toContainText(operator.password)
  await expect(page.getByText(/password/i)).toHaveCount(0)
})
