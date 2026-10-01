import { expect, type Locator, type Page } from '@playwright/test'

export interface Credentials {
  email: string
  password: string
}

export interface MasterDataNames {
  category: string
  supplier: string
  supplierEmail: string
  sku: string
  product: string
  warehouseCode: string
  warehouse: string
}

export const e2eCredentials = {
  admin: {
    email: process.env.E2E_ADMIN_EMAIL ?? 'e2e-admin@example.com',
    password: process.env.E2E_ADMIN_PASSWORD ?? 'e2e-admin-password-2026',
  },
  seededWarehouse: {
    email: process.env.E2E_WAREHOUSE_EMAIL ?? 'e2e-warehouse@example.com',
    password: process.env.E2E_WAREHOUSE_PASSWORD ?? 'e2e-warehouse-password-2026',
  },
  seededClient: {
    email: process.env.E2E_CLIENT_EMAIL ?? 'e2e-client@example.com',
    password: process.env.E2E_CLIENT_PASSWORD ?? 'e2e-client-password-2026',
  },
} satisfies Record<string, Credentials>

export function uniqueRunId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function selectOptionByText(select: Locator, text: string) {
  const value = await select.evaluate((element, optionText) => {
    const options = Array.from((element as HTMLSelectElement).options)
    return options.find((option) => option.text === optionText)?.value ?? null
  }, text)
  if (value === null) throw new Error(`Option "${text}" does not have a value.`)
  await select.selectOption(value)
}

export async function signIn(page: Page, credentials: Credentials) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password').fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
}

export async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

export async function createMasterData(page: Page, names: MasterDataNames) {
  await page.getByRole('link', { name: 'Categories' }).click()
  await expect(page.getByRole('heading', { name: 'Categories' })).toBeVisible()
  await page.getByRole('button', { name: 'Create category' }).click()
  const categoryForm = page.getByRole('form', { name: 'Create category' })
  await categoryForm.getByLabel('Name', { exact: true }).fill(names.category)
  await categoryForm.getByRole('button', { name: 'Save category' }).click()
  await expect(page.getByRole('status')).toContainText('Category created')
  await expect(page.getByRole('table', { name: 'Category ledger' })).toContainText(names.category)

  await page.getByRole('link', { name: 'Suppliers' }).click()
  await expect(page.getByRole('heading', { name: 'Suppliers' })).toBeVisible()
  await page.getByRole('button', { name: 'Create supplier' }).click()
  const supplierForm = page.getByRole('form', { name: 'Create supplier' })
  await supplierForm.getByLabel('Name', { exact: true }).fill(names.supplier)
  await supplierForm.getByLabel('Email', { exact: true }).fill(names.supplierEmail)
  await supplierForm.getByLabel('Phone', { exact: true }).fill('+84-28-5555-0101')
  await supplierForm.getByLabel('Address', { exact: true }).fill('19 E2E Street')
  await supplierForm.getByRole('button', { name: 'Save supplier' }).click()
  await expect(page.getByRole('status')).toContainText('Supplier created')
  await expect(page.getByRole('table', { name: 'Supplier ledger' })).toContainText(names.supplier)

  await page.getByRole('link', { name: 'Products' }).click()
  await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible()
  await page.getByRole('button', { name: 'Create product' }).click()
  const productForm = page.getByRole('form', { name: 'Create product' })
  await productForm.getByLabel('SKU', { exact: true }).fill(names.sku)
  await productForm.getByLabel('Name', { exact: true }).fill(names.product)
  await productForm.getByLabel('Description', { exact: true }).fill('Playwright critical-path item')
  await selectOptionByText(productForm.getByRole('combobox', { name: 'Category', exact: true }), names.category)
  await selectOptionByText(productForm.getByRole('combobox', { name: 'Supplier', exact: true }), names.supplier)
  await productForm.getByLabel('Unit', { exact: true }).fill('each')
  await productForm.getByLabel('Reorder level', { exact: true }).fill('5')
  await productForm.getByRole('button', { name: 'Save product' }).click()
  await expect(page.getByRole('status')).toContainText('Product created')
  await expect(page.getByRole('table', { name: 'Product ledger' })).toContainText(names.sku)

  await page.getByRole('link', { name: 'Warehouses' }).click()
  await expect(page.getByRole('heading', { name: 'Warehouses' })).toBeVisible()
  await page.getByRole('button', { name: 'Create warehouse' }).click()
  const warehouseForm = page.getByRole('form', { name: 'Create warehouse' })
  await warehouseForm.getByLabel('Code', { exact: true }).fill(names.warehouseCode)
  await warehouseForm.getByLabel('Name', { exact: true }).fill(names.warehouse)
  await warehouseForm.getByLabel('Address', { exact: true }).fill('20 E2E Avenue')
  await warehouseForm.getByLabel('Latitude', { exact: true }).fill('10.7769')
  await warehouseForm.getByLabel('Longitude', { exact: true }).fill('106.7009')
  await warehouseForm.getByRole('button', { name: 'Save warehouse' }).click()
  await expect(page.getByRole('status')).toContainText('Warehouse created')
  await expect(page.getByRole('table', { name: 'Warehouse ledger' })).toContainText(names.warehouseCode)
}

export async function createManagedUser(page: Page, credentials: Credentials, role: 'client' | 'warehouse') {
  await page.getByRole('link', { name: 'Users' }).click()
  await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible()
  const form = page.getByRole('form', { name: 'Create managed user' })
  await form.getByLabel('Email', { exact: true }).fill(credentials.email)
  await form.getByLabel('Password', { exact: true }).fill(credentials.password)
  const roleSelect = form.getByLabel('Role', { exact: true })
  await expect(roleSelect.getByRole('option', { name: 'Admin' })).toHaveCount(0)
  await roleSelect.selectOption(role)
  await form.getByRole('button', { name: 'Create user' }).click()
  await expect(page.getByRole('status')).toContainText('User created')
  const row = page.getByRole('row').filter({ hasText: credentials.email })
  await expect(row).toContainText(role)
  return row
}
