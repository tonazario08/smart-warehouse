import { expect, test } from '@playwright/test'
import { apiAs, apiResponse, createManagedUser, e2eCredentials, realApi, signIn, signOut, storedToken, tokenKey, uniqueRunId } from './helpers'

test('API registration stays client-only; Figma login refreshes the authenticated read-only catalogue', async ({ page }) => {
  const credentials = { email: 'client-' + uniqueRunId() + '@example.com', password: 'client-password-2026' }
  await page.goto('/login')
  await apiAs(page, null, '/products', 'GET', undefined, 401)
  await apiAs(page, null, '/auth/register', 'POST', { ...credentials, role: 'admin' }, 422)
  const registered = await apiAs<{ role: string; is_active: boolean }>(page, null, '/auth/register', 'POST', credentials, 201)
  expect(registered.role === 'client' && registered.is_active).toBe(true)
  await signIn(page, credentials)
  await expect(page).toHaveURL(/\/products$/)
  const me = apiResponse(page, '/auth/me')
  const products = apiResponse(page, '/products')
  await page.reload()
  expect((await me).status()).toBe(200)
  expect((await products).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Sản phẩm', exact: true })).toBeVisible()
  expect(Boolean(await storedToken(page))).toBe(true)
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Thêm sản phẩm', exact: true })).toHaveCount(0)
  for (const name of ['Sản phẩm', 'Tồn kho', 'Kho hàng']) await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  for (const name of ['Bảng điều khiển', 'Nhập kho', 'Xuất kho']) await expect(page.getByRole('link', { name, exact: true })).toHaveCount(0)
  const stock = apiResponse(page, '/stock')
  await page.getByRole('link', { name: 'Tồn kho', exact: true }).click()
  expect((await stock).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Tồn kho', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await signOut(page)
})

for (const role of ['admin', 'warehouse', 'client'] as const) {
  test('Figma navigation and direct-route guards for ' + role, async ({ page }) => {
    const credentials = role === 'admin' ? e2eCredentials.admin : role === 'warehouse' ? e2eCredentials.seededWarehouse : e2eCredentials.seededClient
    await signIn(page, credentials)
    const allowed = role === 'admin' ? ['Bảng điều khiển', 'Sản phẩm', 'Tồn kho', 'Kho hàng', 'Nhập kho', 'Xuất kho'] : role === 'warehouse' ? ['Tồn kho', 'Kho hàng', 'Nhập kho', 'Xuất kho'] : ['Sản phẩm', 'Tồn kho', 'Kho hàng']
    const nav = page.getByRole('navigation', { name: 'Điều hướng chính' })
    await expect(nav.getByRole('link')).toHaveCount(allowed.length)
    for (const name of allowed) await expect(nav.getByRole('link', { name, exact: true })).toBeVisible()
    await expect(nav.getByRole('link', { name: /Users|Audit|Register|Categories|Suppliers/ })).toHaveCount(0)
    if (role === 'admin') {
      await page.goto('/products/new')
      await expect(page.getByRole('heading', { name: 'Thêm sản phẩm', exact: true })).toBeVisible()
      await page.goto('/warehouses/new')
      await expect(page.getByRole('heading', { name: 'Thêm kho hàng', exact: true })).toBeVisible()
    } else {
      const denied = role === 'client' ? ['/dashboard', '/products/new', '/warehouses/new', '/inbound', '/outbound/new'] : ['/dashboard', '/products/new', '/warehouses/new']
      for (const path of denied) {
        await page.goto(path)
        await expect(page).toHaveURL(role === 'client' ? /\/products$/ : /\/inventory$/)
        await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toBeVisible()
      }
    }
    await signOut(page)
  })
}

test('Figma protected refresh clears an actually invalid token on backend 401', async ({ page }) => {
  await signIn(page, e2eCredentials.seededClient)
  await page.evaluate(key => localStorage.setItem(key, 'e2e-invalid-token'), tokenKey)
  const me = apiResponse(page, '/auth/me')
  await page.reload()
  expect((await me).status()).toBe(401)
  await expect(page).toHaveURL(/\/login$/)
  expect(await storedToken(page) === null).toBe(true)
  await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toHaveCount(0)
})

test('real role-change 403 retains the Figma session; refresh applies authoritative database role', async ({ page }) => {
  const credentials = { email: 'role-change-' + uniqueRunId() + '@example.com', password: 'managed-role-password-2026' }
  await signIn(page, e2eCredentials.admin)
  const adminToken = await storedToken(page)
  const managed = await createManagedUser(page, credentials, 'warehouse')
  await signOut(page)
  await signIn(page, credentials)
  const token = await storedToken(page)
  await apiAs(page, adminToken, '/users/' + managed.id + '/role', 'PATCH', { role: 'client' })
  const denied = apiResponse(page, '/transactions')
  await page.getByRole('link', { name: 'Nhập kho', exact: true }).click()
  expect((await denied).status()).toBe(403)
  await expect(page.getByRole('alert')).toContainText('không có quyền')
  expect(await storedToken(page) === token).toBe(true)
  await expect(page.getByRole('navigation', { name: 'Điều hướng chính' })).toBeVisible()
  const me = apiResponse(page, '/auth/me')
  await page.reload()
  const currentUser = await (await me).json() as { role: string }
  expect(currentUser.role === 'client').toBe(true)
  await expect(page).toHaveURL(/\/products$/)
  await expect(page.getByRole('link', { name: 'Nhập kho', exact: true })).toHaveCount(0)
  await realApi(page, '/stock?page_size=100')
  await signOut(page)
})
