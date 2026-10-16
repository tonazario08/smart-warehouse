import { expect, test } from '@playwright/test'
import { apiResponse, createManagedUser, createMasterData, e2eCredentials, realApi, runNames, signIn, uniqueRunId } from './helpers'

test('Figma product/warehouse CRUD plus real API directory, managed-user and password-safe audit coverage', async ({ page }) => {
  const names = runNames('CRUD')
  const operator = { email: 'managed-' + uniqueRunId() + '@example.com', password: 'managed-user-password-2026' }
  await signIn(page, e2eCredentials.admin)
  await expect(page).toHaveURL(/\/dashboard$/)
  const ids = await createMasterData(page, names)

  // Management and audit have no approved Figma screens: prove the real API, not a legacy UI.
  const managed = await createManagedUser(page, operator, 'warehouse')
  await realApi(page, '/users', 'POST', { email: 'denied-' + uniqueRunId() + '@example.com', password: operator.password, role: 'admin' }, 422)
  const role = await realApi<{ role: string }>(page, '/users/' + managed.id + '/role', 'PATCH', { role: 'client' })
  expect(role.role === 'client').toBe(true)
  const inactive = await realApi<{ is_active: boolean }>(page, '/users/' + managed.id + '/status', 'PATCH', { is_active: false })
  expect(inactive.is_active).toBe(false)
  const audit = await realApi<{ items: { action: string; before_data: unknown; after_data: unknown }[] }>(page, '/audit-logs?target_type=user&target_id=' + managed.id + '&page_size=100')
  for (const action of ['user.created', 'user.role_changed', 'user.status_changed']) {
    expect(audit.items.filter(item => item.action === action).length).toBe(1)
  }
  expect(JSON.stringify(audit).includes(operator.password)).toBe(false)
  expect(/password|password_hash/i.test(JSON.stringify(audit))).toBe(false)

  // Real supported warehouse read/edit UI. Delete is intentionally API-only, no new UI invented.
  await page.goto('/warehouses')
  await page.getByRole('textbox', { name: 'Tìm kiếm kho hàng', exact: true }).fill(names.warehouseCode)
  await page.getByRole('button', { name: 'Xem chi tiết ' + names.warehouse, exact: true }).click()
  await page.getByRole('button', { name: 'Chỉnh sửa kho', exact: true }).click()
  await page.getByLabel('Địa chỉ', { exact: true }).fill('Địa chỉ đã cập nhật')
  await page.getByLabel('Vĩ độ', { exact: true }).fill('0')
  await page.getByLabel('Kinh độ', { exact: true }).fill('0')
  const warehouseUpdate = apiResponse(page, '/warehouses/' + ids.warehouseId, 'PUT')
  await page.getByRole('button', { name: 'Lưu kho hàng', exact: true }).click()
  expect((await warehouseUpdate).status()).toBe(200)
  const savedWarehouse = await realApi<{ latitude: number; longitude: number; address: string }>(page, '/warehouses/' + ids.warehouseId)
  expect(savedWarehouse.latitude === 0 && savedWarehouse.longitude === 0 && savedWarehouse.address === 'Địa chỉ đã cập nhật').toBe(true)

  // Duplicate-SKU rejection must leave the real edit form/draft usable.
  const savedProduct = await realApi<Record<string, unknown>>(page, '/products/' + ids.productId)
  const { id: ignoredId, ...input } = savedProduct
  void ignoredId
  const alternate = await realApi<{ id: number }>(page, '/products', 'POST', { ...input, sku: names.sku + '-ALT', name: names.product + ' alternate' }, 201)
  await page.goto('/products/' + ids.productId + '/edit')
  await page.getByLabel('SKU', { exact: true }).fill(names.sku + '-ALT')
  const conflict = apiResponse(page, '/products/' + ids.productId, 'PUT')
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click()
  expect((await conflict).status()).toBe(409)
  await expect(page.getByRole('alert')).toContainText('Mã SKU')
  await expect(page.getByRole('button', { name: 'Lưu thay đổi', exact: true })).toBeEnabled()
  await page.getByLabel('SKU', { exact: true }).fill(names.sku)
  await page.getByLabel('Tên sản phẩm', { exact: true }).fill(names.product + ' updated')
  await page.getByRole('textbox', { name: 'Mô tả', exact: true }).fill('Mô tả mới không bị mất')
  await page.getByRole('button', { name: 'Ngừng hoạt động', exact: true }).click()
  const update = apiResponse(page, '/products/' + ids.productId, 'PUT')
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click()
  expect((await update).status()).toBe(200)
  const updated = await realApi<Record<string, unknown>>(page, '/products/' + ids.productId)
  expect(updated.description === 'Mô tả mới không bị mất' && updated.is_active === false && updated.category_id === ids.categoryId && updated.supplier_id === ids.supplierId && updated.reorder_level === 5 && updated.unit === 'cái').toBe(true)
  await page.getByRole('textbox', { name: 'Tìm kiếm sản phẩm', exact: true }).fill(names.sku)
  await page.getByRole('button', { name: 'Xóa ' + names.product + ' updated', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Xóa sản phẩm?' })
  await expect(dialog).toBeVisible()
  const deletion = apiResponse(page, '/products/' + ids.productId, 'DELETE')
  await dialog.getByRole('button', { name: 'Xóa sản phẩm', exact: true }).click()
  expect((await deletion).status()).toBe(204)
  await expect(dialog).not.toBeVisible()
  await realApi(page, '/products/' + ids.productId, 'GET', undefined, 404)

  // Only test-created, unreferenced rows are removed. Managed-user/audit history remains.
  await realApi(page, '/products/' + alternate.id, 'DELETE', undefined, 204)
  await realApi(page, '/warehouses/' + ids.warehouseId, 'DELETE', undefined, 204)
  await realApi(page, '/warehouses/' + ids.warehouseId, 'GET', undefined, 404)
  await realApi(page, '/suppliers/' + ids.supplierId, 'DELETE', undefined, 204)
  await realApi(page, '/categories/' + ids.categoryId, 'DELETE', undefined, 204)
})
