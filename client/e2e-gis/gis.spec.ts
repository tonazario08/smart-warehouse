import { lstat, realpath } from 'node:fs/promises'
import { dirname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'
import {
  apiResponse, e2eCredentials, signIn, signOut, storedToken, tokenKey,
  type Credentials,
} from '../e2e/helpers'
import type { GisStatus, Heatmap, RouteRead, WarehouseOptions } from '../src/features/gis/types'

const scenario = process.env.E2E_GIS_SCENARIO
const expectedSnapshot = process.env.E2E_GIS_SNAPSHOT_ID
const stockLabel = 'Kho và tồn kiểm thử'
const names = {
  source: 'Kho kiểm thử M10 Đường',
  detour: 'Kho kiểm thử M10 Vòng',
  near: 'Kho kiểm thử M10 Gần',
  disconnected: 'Kho kiểm thử M10 Rời',
  unlocated: 'Kho kiểm thử M10 Thiếu vị trí',
  outside: 'Kho kiểm thử M10 Ngoài vùng',
}
const skuLabel = 'M10-GIS-SKU · Hàng kiểm thử M10'
const target = { latitude: 10.78077, longitude: 106.70042 }

type PageResult<T> = { items: T[] }

async function signInSafely(page: Page, credentials: Credentials) {
  try {
    await signIn(page, credentials)
  } catch {
    throw new Error('Unable to sign in to the isolated M10 browser.')
  }
}

async function readAPI<T>(
  page: Page, path: string, { auth = 'current', expected = 200, body }: {
    auth?: 'current' | 'missing' | 'invalid'; expected?: number; body?: object;
  } = {},
): Promise<T> {
  const result = await page.evaluate(async ({ path, auth, body, key }) => {
    const token = auth === 'current' ? localStorage.getItem(key)
      : auth === 'invalid' ? 'invalid-m10-session' : null
    try {
      const response = await fetch('/api/v1' + path, {
        method: body ? 'POST' : 'GET',
        headers: {
          ...(token ? { Authorization: 'Bearer ' + token } : {}),
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      })
      return { status: response.status, data: response.ok ? await response.json() : null }
    } catch {
      return { status: 0, data: null }
    }
  }, { path, auth, body, key: tokenKey })
  expect(result.status, 'isolated GIS API status').toBe(expected)
  return result.data as T
}

async function openGIS(page: Page, credentials: Credentials) {
  await signInSafely(page, credentials)
  if (new URL(page.url()).pathname !== '/gis') await page.goto('/gis')
  await expect(page.getByRole('heading', { name: 'Bản đồ kho', exact: true })).toBeVisible()

  const body = await readAPI<GisStatus>(page, '/gis/status')
  expect(body.state).toBe('available')
  expect(body.snapshot?.snapshot_id).toBe(expectedSnapshot)
  expect(body.snapshot?.dataset_class).toBe(scenario === 'public' ? 'public_osm' : 'synthetic_fixture')
  expect(body.snapshot?.crs).toBe('EPSG:4326')
  expect(body.snapshot?.weight_unit).toBe('mm')
  expect(body.stock_data_class).toBe('synthetic_fixture')
  await expect(page.getByText(stockLabel, { exact: true })).toBeVisible()
  await expect(page.getByText('Vùng phủ WGS84', { exact: true })).toBeVisible()
  return body
}

async function pickSKU(page: Page) {
  const picker = page.getByLabel('Sản phẩm (SKU)')
  const option = picker.getByRole('option', { name: skuLabel, exact: true })
  await expect(option).toBeAttached()
  await picker.selectOption({ label: skuLabel })
  await page.getByLabel('Số lượng cần').fill('5')
  return Number(await picker.inputValue())
}

async function fillCoordinate(page: Page) {
  await page.getByLabel('Vĩ độ', { exact: true }).fill(String(target.latitude))
  await page.getByLabel('Kinh độ', { exact: true }).fill(String(target.longitude))
}

async function lookup(page: Page) {
  const response = apiResponse(page, '/gis/warehouse-options', 'POST')
  await page.getByRole('button', { name: 'Tìm kho đủ tồn', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  return await result.json() as WarehouseOptions
}

async function transfers(page: Page, productId: number) {
  const data = await readAPI<PageResult<{ id: number; reference: string }>>(
    page, '/transfers?product_id=' + productId,
  )
  return data.items
}

async function lookupTransfer(page: Page, transferId: number) {
  await page.getByRole('button', { name: 'Tra phiếu chuyển kho', exact: true }).click()
  await page.getByLabel('ID phiếu chuyển kho', { exact: true }).fill(String(transferId))
  const response = apiResponse(page, '/gis/route', 'POST')
  await page.getByRole('button', { name: 'Xem tuyến chuyển kho', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  return await result.json() as RouteRead
}

async function heatmap(page: Page, start: string, end: string) {
  await page.getByLabel('Từ ngày', { exact: true }).fill(start)
  await page.getByLabel('Đến đầu ngày', { exact: true }).fill(end)
  const response = apiResponse(page, '/gis/heatmap')
  await page.getByRole('button', { name: 'Xem lượng xuất', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  return await result.json() as Heatmap
}

async function captureEvidence(page: Page, project: string) {
  const requested = process.env.E2E_GIS_EVIDENCE_DIR
  if (!requested) return
  if (!isAbsolute(requested)) throw new Error('Use an absolute external M10 evidence directory.')
  const directory = await realpath(requested)
  const repository = await realpath(resolve(dirname(fileURLToPath(import.meta.url)), '..', '..'))
  const fromRepository = relative(repository, directory)
  if (!fromRepository || (!isAbsolute(fromRepository) && !/^\.\.(?:[\\/]|$)/.test(fromRepository))) {
    throw new Error('M10 browser evidence must stay outside Git.')
  }
  const output = join(directory, `m10-gis-${scenario}-${project}.png`)
  const existing = await lstat(output).catch((error: NodeJS.ErrnoException) => {
    if (error.code !== 'ENOENT') throw error
    return null
  })
  if (existing && !existing.isFile()) throw new Error('Unsafe M10 screenshot destination.')
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }))
  await page.screenshot({
    path: output, fullPage: true, scale: 'css',
    mask: [page.locator('.user-menu')], maskColor: '#0B121F',
  })
}

test('real roles, protected reload and server denial for unauthorized requests', async ({ page }) => {
  await openGIS(page, e2eCredentials.admin)
  const nav = page.getByRole('navigation', { name: 'Điều hướng chính' })
  await expect(nav.getByRole('link', { name: 'Bản đồ kho', exact: true })).toBeVisible()
  const reload = apiResponse(page, '/gis/status')
  await page.reload()
  expect((await reload).status()).toBe(200)
  expect(Boolean(await storedToken(page))).toBe(true)

  await signOut(page)
  await openGIS(page, e2eCredentials.seededWarehouse)
  await expect(nav.getByRole('link', { name: 'Bản đồ kho', exact: true })).toBeVisible()
  await signOut(page)

  await signInSafely(page, e2eCredentials.seededClient)
  await expect(nav.getByRole('link', { name: 'Bản đồ kho', exact: true })).toHaveCount(0)
  expect(Boolean(await storedToken(page))).toBe(true)
  await readAPI(page, '/gis/status', { auth: 'missing', expected: 401 })
  await readAPI(page, '/gis/status', { auth: 'invalid', expected: 401 })
  await readAPI(page, '/gis/status', { expected: 403 })
  await readAPI(page, '/gis/route', {
    expected: 403, body: { kind: 'transfer', transfer_id: 2147483647 },
  })
  await page.goto('/gis')
  await expect(page).toHaveURL(/\/products$/)
})

test('stock-feasible route, keyboard, period totals and two responsive views', async ({ page }, info) => {
  const status = await openGIS(page, e2eCredentials.admin)
  const productId = await pickSKU(page)
  await fillCoordinate(page)
  await page.evaluate(() => {
    const observer = new MutationObserver(records => {
      if (records.some(record => [...record.addedNodes].some(node => node.textContent?.includes('Đang tìm kho đủ tồn…')))) {
        document.body.dataset.m10GisLoading = 'true'
        observer.disconnect()
      }
    })
    observer.observe(document.body, { childList: true, subtree: true })
  })
  const options = await lookup(page)
  expect(await page.locator('body').getAttribute('data-m10-gis-loading')).toBe('true')
  expect(options.product.product_id).toBe(productId)
  expect(options.snapshot?.snapshot_id).toBe(expectedSnapshot)
  expect(options.ranking_state).toBe('available')
  const nearest = options.excluded.find(row => row.warehouse.name === names.near)
  expect(nearest?.reason).toBe('insufficient_stock')
  expect(nearest?.available_quantity).toBe(2)
  expect(options.excluded.some(row => row.warehouse.name === names.unlocated && row.reason === 'missing_coordinates')).toBe(true)
  const source = options.ranked.find(row => row.warehouse.name === names.source)
  expect(Boolean(source)).toBe(true)
  if (scenario === 'synthetic') {
    const detour = options.ranked.find(row => row.warehouse.name === names.detour)
    expect(Boolean(detour)).toBe(true)
    expect(source!.distance_mm).toBeLessThan(detour!.distance_mm)
    const straightLine = (row: NonNullable<typeof source>) => Math.hypot(
      row.warehouse.longitude! - target.longitude, row.warehouse.latitude! - target.latitude,
    )
    expect(straightLine(detour!)).toBeLessThan(straightLine(source!))
    expect(options.geographic_only.some(row => row.warehouse.name === names.disconnected && row.reason === 'no_route')).toBe(true)
  }

  const show = page.getByRole('button', { name: 'Xem tuyến từ ' + names.source, exact: true })
  await show.focus()
  await expect(show).toBeFocused()
  const routeResponse = apiResponse(page, '/gis/route', 'POST')
  await show.press('Enter')
  const response = await routeResponse
  expect(response.status()).toBe(200)
  const route = await response.json() as RouteRead
  expect(route.reason).toBeNull()
  expect(route.snapshot?.snapshot_id).toBe(expectedSnapshot)
  expect(route.distance_mm).toBe(source!.distance_mm)
  expect(route.geometry?.type).toBe('LineString')
  if (scenario === 'public') {
    expect(route.distance_mm).toBe(4_088_267)
    expect(route.geometry?.coordinates).toHaveLength(124)
    expect(route.origin_snap?.node_id).toBe(14_118_824_113)
    expect(route.destination_snap?.node_id).toBe(7_501_051_433)
    const attribution = page.getByRole('link', { name: '© OpenStreetMap contributors' })
    await expect(attribution).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright')
    expect(status.snapshot?.license).toBe('ODbL 1.0')
  }
  await expect(page.getByRole('img', { name: 'Sơ đồ tuyến đường' })).toBeVisible()
  await expect(page.getByText('Tuyến ô tô tham khảo', { exact: true })).toBeVisible()

  const volume = await heatmap(page, '2026-11-02', '2026-11-03')
  expect(volume.start_utc).toBe('2026-11-01T17:00:00Z')
  expect(volume.end_utc).toBe('2026-11-02T17:00:00Z')
  expect(volume.timezone).toBe('Asia/Ho_Chi_Minh')
  expect(volume.product.unit).toBe('hộp')
  expect(volume.points.find(row => row.warehouse.name === names.source)?.fulfilled_quantity).toBe(4)
  expect(volume.points.some(row => row.warehouse.name === names.outside)).toBe(true)
  expect(volume.unlocated.find(row => row.warehouse.name === names.unlocated)?.fulfilled_quantity).toBe(2)
  expect(volume.excluded.transfer_out).toEqual({ quantity: 2, transaction_count: 2 })
  expect(volume.excluded.transfer_in).toEqual({ quantity: 2, transaction_count: 2 })
  const table = page.getByRole('table', { name: 'Lượng xuất theo kho' })
  await expect(table.getByRole('row').filter({ hasText: names.unlocated })).toContainText('Chưa có vị trí')
  await expect(page.getByRole('img', { name: 'Bản đồ lượng xuất theo kho' })).toBeVisible()
  const viewport = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth }))
  expect(viewport.width).toBe(info.project.name === 'desktop' ? 1440 : 390)
  expect(viewport.content).toBeLessThanOrEqual(viewport.width + 1)
  await captureEvidence(page, info.project.name)

  const empty = await heatmap(page, '2026-11-04', '2026-11-05')
  expect([...empty.points, ...empty.unlocated].every(row => row.fulfilled_quantity === 0)).toBe(true)
  await expect(page.getByText('Chưa ghi nhận lượng xuất đáp ứng yêu cầu mua hàng trong kỳ.', { exact: true })).toBeVisible()
})

test('purchase and warehouse context, real offline retry and transfer directions', async ({ page }) => {
  await openGIS(page, e2eCredentials.seededWarehouse)
  const productId = await pickSKU(page)
  const requests = await readAPI<PageResult<{ id: number; note: string }>>(
    page, '/purchase-requests?product_id=' + productId,
  )
  const requestId = requests.items.find(row => row.note === 'M10-GIS-DESTINATION')?.id
  expect(Boolean(requestId)).toBe(true)
  await page.getByLabel('Loại điểm đến').selectOption('purchase_request')
  await page.getByLabel('ID yêu cầu mua hàng').fill(String(requestId))

  await page.context().setOffline(true)
  try {
    await page.getByRole('button', { name: 'Tìm kho đủ tồn', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('Không thể tải dữ liệu')
  } finally {
    await page.context().setOffline(false)
  }
  const retry = apiResponse(page, '/gis/warehouse-options', 'POST')
  await page.getByRole('button', { name: 'Thử lại tìm kho', exact: true }).click()
  const retryResult = await retry
  expect(retryResult.status()).toBe(200)
  const purchase = await retryResult.json() as WarehouseOptions
  expect(purchase.destination.request_id).toBe(requestId)
  expect(purchase.destination.warehouse?.name).toBe(names.near)

  await page.getByLabel('Loại điểm đến').selectOption('warehouse')
  await page.getByLabel('Kho đích').selectOption({ label: 'M10-GIS-NEAR · ' + names.near })
  const warehouse = await lookup(page)
  expect(warehouse.destination.kind).toBe('warehouse')
  expect(warehouse.destination.warehouse?.name).toBe(names.near)

  const records = await transfers(page, productId)
  const connected = records.find(row => row.reference === 'M10-GIS-TRANSFER')?.id
  expect(Boolean(connected)).toBe(true)
  const route = await lookupTransfer(page, connected!)
  expect(route.transfer).toEqual({ transfer_id: connected, mode: 'immediate' })
  expect(route.reason).toBeNull()
  await expect(page.getByText(/Chuyển kho tức thời/)).toBeVisible()

  if (scenario === 'synthetic') {
    const disconnected = records.find(row => row.reference === 'M10-GIS-TRANSFER-LOST')?.id
    expect(Boolean(disconnected)).toBe(true)
    const missing = await lookupTransfer(page, disconnected!)
    expect(missing.reason).toBe('no_route')
    expect(missing.geometry).toBeNull()
    await expect(page.getByText('Không tìm thấy đường đi trong mạng đường đã chọn.', { exact: true })).toBeVisible()
    await expect(page.getByRole('img', { name: 'Sơ đồ tuyến đường' }).locator('polyline')).toHaveCount(0)
  }
})
