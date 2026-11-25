import { expect, test, type Page } from '@playwright/test'
import { apiResponse, createMasterData, e2eCredentials, realApi, runNames, signIn, signOut, uniqueRunId } from './helpers'

// All records are disposable M2 fixtures in the separately guarded project.
// User/audit and movement history are intentionally retained, never reset or deleted.
async function findRecord(page: Page, text: string, path: string) {
  const table = page.getByRole('table')
  await expect(table).toBeVisible()
  for (let attempt = 0; attempt < 100; attempt++) {
    const row = table.getByRole('row').filter({ has: page.locator('td:first-child').filter({ hasText: text }) })
    if (await row.count()) return row
    const next = page.getByRole('button', { name: 'Trang sau', exact: true })
    if (!(await next.isEnabled())) break
    const read = apiResponse(page, path)
    await next.click()
    expect((await read).status()).toBe(200)
    await expect(table).toBeVisible()
  }
  throw new Error('Disposable management record was not found in server pages')
}
async function confirm(page: Page, label: string, path: string, method: string, status: number) {
  const response = apiResponse(page, path, method)
  await page.getByRole('dialog').getByRole('button', { name: label, exact: true }).click()
  const result = await response
  expect(result.status()).toBe(status)
  return result
}

test('M2 users UI creates a managed account, confirms role/status and displays safe audit history', async ({ page }) => {
  const email = 'm2-ui-' + uniqueRunId() + '@example.com'
  const password = 'synthetic-m2-password-2026'
  await signIn(page, e2eCredentials.admin)
  await page.getByRole('link', { name: 'Người dùng', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Người dùng', exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Vai trò', exact: true }).getByRole('option', { name: 'Quản trị viên' })).toHaveCount(0)
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  const created = apiResponse(page, '/users', 'POST')
  await page.getByRole('button', { name: 'Tạo người dùng', exact: true }).click()
  const result = await created
  expect(result.status()).toBe(201)
  const account = await result.json() as { id: number; role: string }
  expect(account.role === 'client').toBe(true)
  await expect(page.getByLabel('Mật khẩu', { exact: true })).toHaveValue('')
  let row = await findRecord(page, email, '/users')
  const trigger = row.getByRole('button', { name: 'Đổi vai trò cho ' + email, exact: true })
  await trigger.click()
  const cancel = page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true })
  await expect(cancel).toBeFocused()
  await cancel.click()
  await expect(trigger).toBeFocused()
  await trigger.click()
  await page.getByRole('combobox', { name: 'Vai trò mới', exact: true }).selectOption('warehouse')
  await confirm(page, 'Xác nhận đổi vai trò', '/users/' + account.id + '/role', 'PATCH', 200)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  row = await findRecord(page, email, '/users')
  await expect(row).toContainText('Nhân viên kho')
  await row.getByRole('button', { name: 'Vô hiệu hóa ' + email, exact: true }).click()
  await confirm(page, 'Xác nhận vô hiệu hóa', '/users/' + account.id + '/status', 'PATCH', 200)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  row = await findRecord(page, email, '/users')
  await expect(row).toContainText('Đã vô hiệu hóa')
  await page.getByRole('link', { name: 'Nhật ký quản trị', exact: true }).click()
  await page.getByLabel('Loại đối tượng', { exact: true }).fill('user')
  await page.getByLabel('Mã đối tượng', { exact: true }).fill(String(account.id))
  const audit = apiResponse(page, '/audit-logs')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  expect((await audit).status()).toBe(200)
  const table = page.getByRole('table', { name: 'Nhật ký thay đổi quản trị' })
  for (const action of ['Tạo người dùng', 'Đổi vai trò', 'Đổi trạng thái']) await expect(table.getByRole('cell', { name: action, exact: true })).toBeVisible()
  expect((await table.innerText()).includes(password)).toBe(false)
  expect(/password|password_hash/i.test(await table.innerText())).toBe(false)
  await expect(table.getByRole('button')).toHaveCount(0)
  await page.getByLabel('Mã đối tượng', { exact: true }).fill('-2')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Mã đối tượng phải là số nguyên dương hợp lệ.')
  await signOut(page)
})

test('M2 category UI preserves hierarchy, rejects referenced deletion and removes only its own fixtures', async ({ page }) => {
  const parent = 'M2 cha ' + uniqueRunId(), child = 'M2 con ' + uniqueRunId()
  await signIn(page, e2eCredentials.admin)
  await page.goto('/categories')
  await page.getByRole('button', { name: 'Tạo danh mục', exact: true }).click()
  await page.getByLabel('Tên danh mục', { exact: true }).fill(parent)
  let created = apiResponse(page, '/categories', 'POST')
  await page.getByRole('button', { name: 'Lưu danh mục', exact: true }).click()
  const parentResult = await created
  expect(parentResult.status()).toBe(201)
  const parentId = (await parentResult.json() as { id: number }).id
  await expect(page.getByRole('form', { name: 'Tạo danh mục' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Tạo danh mục', exact: true }).click()
  await page.getByLabel('Tên danh mục', { exact: true }).fill(child)
  await page.getByRole('combobox', { name: 'Danh mục cha', exact: true }).selectOption({ label: parent })
  created = apiResponse(page, '/categories', 'POST')
  await page.getByRole('button', { name: 'Lưu danh mục', exact: true }).click()
  const childResult = await created
  expect(childResult.status()).toBe(201)
  const childId = (await childResult.json() as { id: number }).id
  await expect(page.getByRole('form', { name: 'Tạo danh mục' })).toHaveCount(0)
  let row = await findRecord(page, child, '/categories')
  await expect(row).toContainText(parent)
  await row.getByRole('button', { name: 'Sửa danh mục ' + child, exact: true }).click()
  await expect(page.getByRole('combobox', { name: 'Danh mục cha' }).getByRole('option', { name: child, exact: true })).toHaveCount(0)
  await page.getByLabel('Tên danh mục', { exact: true }).fill(child + ' sửa')
  const updated = apiResponse(page, '/categories/' + childId, 'PUT')
  await page.getByRole('button', { name: 'Lưu danh mục', exact: true }).click()
  const childUpdate = await updated
  expect(childUpdate.status()).toBe(200)
  expect((await childUpdate.json() as { parent_id: number }).parent_id).toBe(parentId)
  // A child link is SET NULL by the backend on parent deletion. A product FK is
  // the actual in-use restriction, so exercise it with this test-owned fixture.
  const referenceProduct = await realApi<{ id: number }>(page, '/products', 'POST', { sku: 'M2CAT-' + uniqueRunId(), name: 'M2 category reference', description: null, category_id: parentId, supplier_id: null, unit: 'cái', reorder_level: 0, is_active: true }, 201)
  row = await findRecord(page, parent, '/categories')
  // Parent name also appears as a label in the child row; choose its own row by action.
  await page.getByRole('button', { name: 'Xóa danh mục ' + parent, exact: true }).click()
  await confirm(page, 'Xác nhận xóa danh mục', '/categories/' + parentId, 'DELETE', 409)
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('đang được sử dụng')
  await page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true }).click()
  await page.goto('/categories')
  row = await findRecord(page, child + ' sửa', '/categories')
  await row.getByRole('button', { name: 'Xóa danh mục ' + child + ' sửa', exact: true }).click()
  await confirm(page, 'Xác nhận xóa danh mục', '/categories/' + childId, 'DELETE', 204)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.goto('/categories')
  await findRecord(page, parent, '/categories')
  await realApi(page, '/products/' + referenceProduct.id, 'DELETE', undefined, 204)
  await page.getByRole('button', { name: 'Xóa danh mục ' + parent, exact: true }).click()
  await confirm(page, 'Xác nhận xóa danh mục', '/categories/' + parentId, 'DELETE', 204)
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('M2 suppliers UI creates, searches, preserves fields on edit and confirms deletion', async ({ page }) => {
  const name = 'M2 cung ứng ' + uniqueRunId(), email = 'm2-supplier-' + uniqueRunId() + '@example.com'
  await signIn(page, e2eCredentials.admin)
  await page.goto('/suppliers')
  await page.getByRole('button', { name: 'Tạo nhà cung cấp', exact: true }).click()
  await page.getByLabel('Tên nhà cung cấp', { exact: true }).fill(name)
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Số điện thoại', { exact: true }).fill('0901234567')
  await page.getByLabel('Địa chỉ', { exact: true }).fill('Địa chỉ kiểm thử')
  const created = apiResponse(page, '/suppliers', 'POST')
  await page.getByRole('button', { name: 'Lưu nhà cung cấp', exact: true }).click()
  const result = await created
  expect(result.status()).toBe(201)
  const id = (await result.json() as { id: number }).id
  await expect(page.getByRole('form', { name: 'Tạo nhà cung cấp' })).toHaveCount(0)
  await page.getByLabel('Tìm nhà cung cấp', { exact: true }).fill(name)
  const searched = apiResponse(page, '/suppliers')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  expect((await searched).status()).toBe(200)
  let row = await findRecord(page, name, '/suppliers')
  await row.getByRole('button', { name: 'Sửa nhà cung cấp ' + name, exact: true }).click()
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue(email)
  await expect(page.getByLabel('Số điện thoại', { exact: true })).toHaveValue('0901234567')
  await page.getByLabel('Địa chỉ', { exact: true }).fill('Địa chỉ đã cập nhật')
  const updated = apiResponse(page, '/suppliers/' + id, 'PUT')
  await page.getByRole('button', { name: 'Lưu nhà cung cấp', exact: true }).click()
  expect((await updated).status()).toBe(200)
  row = await findRecord(page, name, '/suppliers')
  await expect(row).toContainText('Địa chỉ đã cập nhật')
  await row.getByRole('button', { name: 'Xóa nhà cung cấp ' + name, exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Hủy', exact: true }).click()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Xóa nhà cung cấp ' + name, exact: true }).click()
  await confirm(page, 'Xác nhận xóa nhà cung cấp', '/suppliers/' + id, 'DELETE', 204)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByText('Không có nhà cung cấp phù hợp.', { exact: true })).toBeVisible()
})

test('M2 history UI reads real linked movements with supported filters and client route guards', async ({ page }) => {
  const names = runNames('M2H')
  await signIn(page, e2eCredentials.admin)
  const ids = await createMasterData(page, names)
  // API fixture setup only; history remains a genuinely read-only UI.
  const inbound = await realApi<{ id: number }>(page, '/inbounds', 'POST', { warehouse_id: ids.warehouseId, product_id: ids.productId, quantity: 3, reference: 'M2-' + uniqueRunId(), note: 'Fixture lịch sử' }, 201)
  await realApi(page, '/outbounds', 'POST', { warehouse_id: ids.warehouseId, product_id: ids.productId, quantity: 1, reference: 'M2-' + uniqueRunId(), note: 'Fixture xuất' }, 201)
  await page.goto('/transactions')
  await page.getByRole('combobox', { name: 'Kho hàng', exact: true }).selectOption(String(ids.warehouseId))
  await page.getByRole('combobox', { name: 'Sản phẩm', exact: true }).selectOption(String(ids.productId))
  await page.getByRole('combobox', { name: 'Loại giao dịch', exact: true }).selectOption('inbound')
  const filtered = apiResponse(page, '/transactions')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  const filteredResult = await filtered
  expect(filteredResult.status()).toBe(200)
  const actualHistory = await filteredResult.json() as { items: { created_by_id: number }[] }
  expect(actualHistory.items).toHaveLength(1)
  const table = page.getByRole('table', { name: 'Lịch sử giao dịch' })
  const row = table.getByRole('row').filter({ hasText: names.sku })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('Phiếu nhập #' + inbound.id)
  await expect(row).toContainText('Tài khoản #' + actualHistory.items[0].created_by_id)
  await expect(table.getByRole('link')).toHaveCount(0)
  await expect(table.getByRole('button')).toHaveCount(0)
  await page.getByLabel('Từ thời điểm', { exact: true }).fill('2026-10-18T12:00')
  await page.getByLabel('Đến thời điểm', { exact: true }).fill('2026-10-17T12:00')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Thời điểm bắt đầu phải trước thời điểm kết thúc.')
  await signOut(page)
  await signIn(page, e2eCredentials.seededWarehouse)
  for (const [path, heading, create] of [['/categories', 'Danh mục', 'Tạo danh mục'], ['/suppliers', 'Nhà cung cấp', 'Tạo nhà cung cấp']] as const) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    await expect(page.getByRole('table')).toBeVisible()
    await expect(page.getByRole('button', { name: create, exact: true })).toHaveCount(0)
  }
  await page.goto('/transactions')
  await page.getByRole('combobox', { name: 'Kho hàng', exact: true }).selectOption(String(ids.warehouseId))
  await page.getByRole('combobox', { name: 'Sản phẩm', exact: true }).selectOption(String(ids.productId))
  const warehouseRead = apiResponse(page, '/transactions')
  await page.getByRole('button', { name: 'Áp dụng bộ lọc', exact: true }).click()
  expect((await warehouseRead).status()).toBe(200)
  await expect(page.getByRole('table').getByRole('row').filter({ hasText: names.sku })).toHaveCount(2)
  await signOut(page)
  await signIn(page, e2eCredentials.seededClient)
  await page.getByRole('link', { name: 'Danh mục', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Danh mục', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tạo danh mục', exact: true })).toHaveCount(0)
  for (const path of ['/users', '/suppliers', '/transactions', '/audit']) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/products$/)
  }
  // Referenced test-only records and their real stock/history are retained.
})
