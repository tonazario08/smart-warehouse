import { expect, type Locator, type Page } from '@playwright/test'
// Only this Node environment surface is used; avoid adding a dependency for the test helpers.
declare const process: { env: Record<string, string | undefined> }
export interface Credentials { email: string; password: string }
export interface MasterDataNames { category: string; supplier: string; supplierEmail: string; sku: string; product: string; warehouseCode: string; warehouse: string }
export const e2eCredentials = {
  admin: { email: process.env.E2E_ADMIN_EMAIL ?? 'e2e-admin@example.com', password: process.env.E2E_ADMIN_PASSWORD ?? 'e2e-admin-password-2026' },
  seededWarehouse: { email: process.env.E2E_WAREHOUSE_EMAIL ?? 'e2e-warehouse@example.com', password: process.env.E2E_WAREHOUSE_PASSWORD ?? 'e2e-warehouse-password-2026' },
  seededClient: { email: process.env.E2E_CLIENT_EMAIL ?? 'e2e-client@example.com', password: process.env.E2E_CLIENT_PASSWORD ?? 'e2e-client-password-2026' },
} satisfies Record<string, Credentials>
export function uniqueRunId() { return Date.now() + '-' + Math.random().toString(36).slice(2, 8) }
export function runNames(prefix: string): MasterDataNames {
  const id = uniqueRunId()
  return { category: prefix + ' category ' + id, supplier: prefix + ' supplier ' + id, supplierEmail: 'supplier-' + id + '@example.com', sku: (prefix + '-' + id).toUpperCase(), product: prefix + ' product ' + id, warehouseCode: (prefix + '-' + id).toUpperCase(), warehouse: prefix + ' warehouse ' + id }
}
export const tokenKey = 'smart-warehouse-token'
export const storedToken = (page: Page) => page.evaluate(key => localStorage.getItem(key), tokenKey)
export const apiResponse = (page: Page, path: string, method = 'GET') => page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1' + path && response.request().method() === method)
export async function apiAs<T = Record<string, unknown>>(page: Page, token: string | null, path: string, method = 'GET', data?: unknown, status = 200): Promise<T> {
  const result = await page.request.fetch('/api/v1' + path, { method, data, headers: token ? { Authorization: 'Bearer ' + token } : {} })
  expect(result.status(), 'real isolated API status').toBe(status)
  return result.status() === 204 ? undefined as T : result.json() as Promise<T>
}
export async function realApi<T = Record<string, unknown>>(page: Page, path: string, method = 'GET', data?: unknown, status = 200): Promise<T> {
  const token = await storedToken(page)
  expect(Boolean(token), 'authenticated API step has a session').toBe(true)
  return apiAs<T>(page, token, path, method, data, status)
}
export async function selectOptionByText(select: Locator, text: string) {
  await expect(select.getByRole('option', { name: text, exact: true })).toHaveCount(1)
  await select.selectOption({ label: text })
  expect(await select.locator('option:checked').textContent() === text).toBe(true)
}
export async function signIn(page: Page, credentials: Credentials) {
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(credentials.email)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(credentials.password)
  const me = apiResponse(page, '/auth/me')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  expect((await me).status()).toBe(200)
  await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toBeVisible()
  expect(Boolean(await storedToken(page))).toBe(true)
}
export async function signOut(page: Page) {
  await page.locator('.user-menu__trigger').click()
  await page.getByRole('button', { name: 'Đăng xuất', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await storedToken(page) === null).toBe(true)
}
export async function createManagedUser(page: Page, credentials: Credentials, role: 'client' | 'warehouse') {
  // API fixture/security coverage; management-ui.spec.ts separately exercises the active UI.
  const user = await realApi<{ id: number; role: string; is_active: boolean }>(page, '/users', 'POST', { ...credentials, role }, 201)
  expect(user.role === role && user.is_active).toBe(true)
  return user
}
export async function createMasterData(page: Page, names: MasterDataNames) {
  // Fixture setup through real APIs; separate management UI scenarios cover directory mutations.
  const category = await realApi<{ id: number }>(page, '/categories', 'POST', { name: names.category, parent_id: null }, 201)
  const supplier = await realApi<{ id: number }>(page, '/suppliers', 'POST', { name: names.supplier, email: names.supplierEmail, phone: '+84-28-5555-0101', address: '19 E2E Street' }, 201)
  await page.goto('/products/new')
  await page.getByLabel('SKU', { exact: true }).fill(names.sku)
  await page.getByLabel('Tên sản phẩm', { exact: true }).fill(names.product)
  await page.getByRole('textbox', { name: 'Mô tả', exact: true }).fill('Mô tả kiểm thử cần được bảo toàn')
  await selectOptionByText(page.getByRole('combobox', { name: 'Danh mục', exact: true }), names.category)
  await selectOptionByText(page.getByRole('combobox', { name: 'Nhà cung cấp', exact: true }), names.supplier)
  await page.getByLabel('Đơn vị tính', { exact: true }).fill('cái')
  await page.getByLabel('Mức tồn tối thiểu', { exact: true }).fill('5')
  const createdProduct = apiResponse(page, '/products', 'POST')
  await page.getByRole('button', { name: 'Lưu sản phẩm', exact: true }).click()
  const productResponse = await createdProduct
  expect(productResponse.status()).toBe(201)
  const product = await productResponse.json() as { id: number }
  await expect(page).toHaveURL(/\/products$/)
  await page.getByRole('textbox', { name: 'Tìm kiếm sản phẩm', exact: true }).fill(names.sku)
  await expect(page.getByRole('row').filter({ hasText: names.sku })).toHaveCount(1)

  await page.goto('/warehouses/new')
  await page.getByLabel('Mã kho', { exact: true }).fill(names.warehouseCode)
  await page.getByLabel('Tên kho', { exact: true }).fill(names.warehouse)
  await page.getByLabel('Địa chỉ', { exact: true }).fill('20 E2E Avenue')
  await page.getByLabel('Vĩ độ', { exact: true }).fill('10.7769')
  await page.getByLabel('Kinh độ', { exact: true }).fill('106.7009')
  const createdWarehouse = apiResponse(page, '/warehouses', 'POST')
  await page.getByRole('button', { name: 'Lưu kho hàng', exact: true }).click()
  const warehouseResponse = await createdWarehouse
  expect(warehouseResponse.status()).toBe(201)
  const warehouse = await warehouseResponse.json() as { id: number }
  await expect(page).toHaveURL(new RegExp('/warehouses/' + warehouse.id + '$'))
  await expect(page.getByRole('heading', { name: names.warehouse, exact: true })).toBeVisible()
  return { categoryId: category.id, supplierId: supplier.id, productId: product.id, warehouseId: warehouse.id }
}

export function assertTransferTarget(page: Page) {
  const target = new URL(page.url())
  if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || !['58080', '58081'].includes(target.port) || target.username || target.password) throw new Error('Transfer fixtures require the separately guarded M3/M4 loopback target.')
}

export function assertPurchaseRequestTarget(page: Page) {
  const target = new URL(page.url())
  if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || target.port !== '58081' || target.username || target.password) throw new Error('M4 fixtures require the separately guarded M4 loopback target.')
}

export function purchaseRequestCredentials() {
  for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) for (const field of ['EMAIL', 'PASSWORD']) {
    if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated M4 credentials are required.')
  }
  return { admin: e2eCredentials.admin, warehouse: e2eCredentials.seededWarehouse, client: e2eCredentials.seededClient }
}

export async function createPurchaseRequestFixture(page: Page) {
  assertPurchaseRequestTarget(page)
  purchaseRequestCredentials()
  const run = uniqueRunId()
  const category = await realApi<{ id: number }>(page, '/categories', 'POST', { name: 'M4 requests ' + run, parent_id: null }, 201)
  const product = await realApi<{ id: number; sku: string; name: string }>(page, '/products', 'POST', {
    sku: 'M4-' + run, name: 'Yêu cầu M4 ' + run, description: 'M4 isolated fixture', category_id: category.id, supplier_id: null, unit: 'cái', reorder_level: 0, is_active: true,
  }, 201)
  const warehouse = await realApi<{ id: number; name: string }>(page, '/warehouses', 'POST', {
    code: 'M4-' + run, name: 'Kho yêu cầu M4 ' + run, address: 'M4 isolated fixture', latitude: null, longitude: null,
  }, 201)
  await realApi(page, '/inbounds', 'POST', { warehouse_id: warehouse.id, product_id: product.id, quantity: 10, reference: 'M4 fixture ' + run, note: 'Synthetic isolated stock' }, 201)
  const clients = []
  for (const suffix of ['A', 'B']) {
    const credentials = { email: ('m4-' + suffix + '-' + run + '@example.com').toLowerCase(), password: 'M4!' + crypto.randomUUID() }
    const user = await createManagedUser(page, credentials, 'client')
    clients.push({ ...credentials, id: user.id })
  }
  return { product, warehouse, clients }
}

export async function createTransferFixture(page: Page) {
  assertTransferTarget(page)
  const run = uniqueRunId()
  const category = await realApi<{ id: number }>(page, '/categories', 'POST', { name: 'M3 transfer ' + run, parent_id: null }, 201)
  const product = await realApi<{ id: number; sku: string; name: string }>(page, '/products', 'POST', {
    sku: 'M3-' + run, name: 'Chuyển kho ' + run, description: 'M3 isolated fixture', category_id: category.id, supplier_id: null, unit: 'cái', reorder_level: 0, is_active: false,
  }, 201)
  const warehouses = []
  for (const suffix of ['A', 'B']) warehouses.push(await realApi<{ id: number; name: string }>(page, '/warehouses', 'POST', {
    code: 'M3-' + suffix + '-' + run, name: 'Kho M3 ' + suffix + ' ' + run, address: 'M3 isolated fixture', latitude: null, longitude: null,
  }, 201))
  for (const [warehouse, quantity] of [[warehouses[0], 10], [warehouses[1], 2]] as const) await realApi(page, '/inbounds', 'POST', { warehouse_id: warehouse.id, product_id: product.id, quantity, reference: 'M3 fixture ' + run, note: 'Synthetic isolated test stock' }, 201)
  return { product, source: warehouses[0], destination: warehouses[1] }
}
