import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { test } from 'node:test'

const require = createRequire(import.meta.url)
// Compile with the existing TypeScript CLI before running this Node test.
const sourceRoot = resolve(process.env.PRODUCT_PAGINATION_SOURCE_ROOT ?? './node_modules/.tmp/pagination-tests/src')
const pages = ['DashboardPage', 'InventoryPage', 'StockDetailPage', 'WarehousesPage', 'WarehouseDetailPage']

// Run the real page effects, API client and joins without a DOM dependency.
// Only the React hook host and authenticated route context are substituted.
function pageHost(pageName, productId, token = 'test-token') {
  const state = []
  const effects = []
  const cache = new Map()
  let cursor = 0
  let mounted = false
  let logoutCount = 0
  const react = {
    ...require('react'),
    useState(initial) {
      const index = cursor++
      if (!(index in state)) state[index] = typeof initial === 'function' ? initial() : initial
      return [state[index], (value) => { state[index] = typeof value === 'function' ? value(state[index]) : value }]
    },
    useEffect(effect) { if (!mounted) effects.push(effect) },
    useMemo: (compute) => compute(),
  }
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports
    const module = { exports: {} }
    cache.set(filename, module)
    const compiled = readFileSync(filename, 'utf8')
    const localRequire = (specifier) => {
      if (specifier === 'react') return react
      if (specifier === 'react-router-dom') return { useNavigate: () => () => {}, useParams: () => ({ id: '1', warehouseId: '1', productId: String(productId) }) }
      if (specifier.endsWith('/app/AuthProvider')) return { useAuth: () => ({ token, user: { id: 1, email: 'test@example.com', role: 'client', is_active: true }, logout: () => { logoutCount++ } }) }
      if (specifier.endsWith('.css')) return {}
      if (specifier.endsWith('.svg')) return { default: specifier }
      if (!specifier.startsWith('.')) return require(specifier)
      const base = resolve(dirname(filename), specifier)
      const dependency = [base, `${base}.js`].find((candidate) => existsSync(candidate))
      assert.ok(dependency, `Cannot resolve ${specifier} from ${filename}`)
      return load(dependency)
    }
    new Function('require', 'module', 'exports', compiled)(localRequire, module, module.exports)
    return module.exports
  }
  const Page = load(resolve(sourceRoot, `pages/${pageName}.js`))[pageName]
  const render = () => { cursor = 0; return Page() }
  const initial = render()
  mounted = true
  const cleanups = effects.map((effect) => effect())
  return { initial, render, logoutCount: () => logoutCount, unmount: () => cleanups.forEach((cleanup) => cleanup?.()) }
}

function nodes(tree, predicate) {
  if (Array.isArray(tree)) return tree.flatMap((child) => nodes(child, predicate))
  if (!tree || typeof tree !== 'object') return []
  return [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)]
}

function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join('')
  if (tree && typeof tree === 'object') return text(tree.props?.children)
  return typeof tree === 'string' || typeof tree === 'number' ? String(tree) : ''
}

const tableRows = (tree) => nodes(tree, (node) => node.type?.name === 'DataTable')[0]?.props.rows
const settle = () => new Promise((resolvePromise) => setImmediate(resolvePromise))

function fixture(total) {
  const products = Array.from({ length: total }, (_, index) => ({ id: index + 1, sku: `SP-${index + 1}`, name: `Sản phẩm ${index + 1}`, description: null, category_id: 1, supplier_id: null, unit: 'cái', reorder_level: index + 1 === total ? 10 : 5, is_active: true }))
  const warehouses = [{ id: 1, code: 'HN-01', name: 'Kho Hà Nội', address: 'Hà Nội', latitude: null, longitude: null }]
  const stock = total === 1 ? [{ id: 2, product_id: 1, warehouse_id: 1, quantity: 3 }] : [{ id: 1, product_id: 1, warehouse_id: 1, quantity: 20 }, { id: 2, product_id: total, warehouse_id: 1, quantity: 3 }]
  return { products, warehouses, stock, stats: { product_count: total, total_stock: total === 1 ? 3 : 23, low_stock_count: 1 }, transactions: [{ id: 1, transaction_type: 'outbound', product_id: total, warehouse_id: 1, quantity: 2 }] }
}

function fakeServer(data, { failPage = 0, gate = null } = {}) {
  const requests = []
  return {
    requests,
    fetch: async (input, options) => {
      const url = new URL(String(input))
      requests.push({ url, options })
      assert.equal(url.origin, 'http://localhost:8000')
      if (url.pathname === '/api/v1/products') {
        const page = Number(url.searchParams.get('page'))
        assert.equal(url.searchParams.get('page_size'), '100')
        if (page === failPage) return { ok: false, status: 503, json: async () => ({ detail: 'Product page unavailable' }) }
        if (page === 2 && gate) await gate
        return { ok: true, status: 200, json: async () => ({ items: data.products.slice((page - 1) * 100, page * 100), total: data.products.length, page, page_size: 100 }) }
      }
      assert.equal(options.headers.Authorization, 'Bearer test-token')
      const payload = { '/api/v1/stock': data.stock, '/api/v1/warehouses': data.warehouses, '/api/v1/warehouses/1': data.warehouses[0], '/api/v1/dashboard/stats': data.stats, '/api/v1/transactions': data.transactions }[url.pathname]
      assert.ok(payload, `Unexpected request: ${url}`)
      return { ok: true, status: 200, json: async () => payload }
    },
  }
}

for (const total of [1, 101]) {
  for (const pageName of pages) {
    test(`${pageName} resolves inventory, thresholds and labels with ${total} products`, async () => {
      const data = fixture(total)
      const server = fakeServer(data)
      const originalFetch = globalThis.fetch
      globalThis.fetch = server.fetch
      const host = pageHost(pageName, total)
      try {
        assert.match(text(host.initial), /Đang tải/)
        await settle()
        const tree = host.render()
        const rows = tableRows(tree)
        const label = `Sản phẩm ${total}`
        if (pageName === 'StockDetailPage') {
          assert.match(text(tree), new RegExp(label))
          assert.match(text(tree), /Sắp hết hàng/)
          assert.match(text(tree), /Mức tồn tối thiểu10 cái/)
        } else if (pageName === 'WarehousesPage') {
          assert.deepEqual(rows.map(({ productCount, totalQuantity, lowStockCount }) => ({ productCount, totalQuantity, lowStockCount })), [{ productCount: total === 1 ? 1 : 2, totalQuantity: total === 1 ? 3 : 23, lowStockCount: 1 }])
        } else {
          const laterRow = rows.find((row) => row.id === 2)
          assert.ok(laterRow, 'Stock for the final product must remain visible')
          assert.equal(laterRow.productName, label)
          assert.equal(laterRow.reorderLevel, 10)
          assert.equal(laterRow.quantity, 3)
          assert.equal(laterRow.status, 'low')
          if (pageName === 'DashboardPage') {
            const alerts = nodes(tree, (node) => node.props?.className === 'dashboard-alert-list')[0]
            assert.ok(alerts, 'Backend low-stock count 1 must have a visible alert')
            assert.equal(nodes(alerts, (node) => node.type === 'li').length, 1)
            assert.match(text(alerts), new RegExp(label))
            const transactions = nodes(tree, (node) => node.props?.className === 'dashboard-transaction-list')[0]
            assert.match(text(transactions), new RegExp(label))
            assert.doesNotMatch(text(tree), /Sản phẩm không xác định|Tồn kho đang ổn định/)
          }
          if (pageName === 'WarehouseDetailPage') assert.match(text(tree), new RegExp(`Tổng tồn kho${total === 1 ? 3 : 23}`))
        }
        assert.deepEqual(server.requests.filter(({ url }) => url.pathname.endsWith('/products')).map(({ url }) => Number(url.searchParams.get('page'))), total === 1 ? [1] : [1, 2])
        assert.equal(host.logoutCount(), 0)
      } finally {
        host.unmount()
        globalThis.fetch = originalFetch
      }
    })
  }
}

test('productsAll returns all 201 records across three API pages while products remains paginated', async () => {
  const data = fixture(201)
  const server = fakeServer(data)
  const originalFetch = globalThis.fetch
  globalThis.fetch = server.fetch
  try {
    const compiled = readFileSync(resolve(sourceRoot, 'api.js'), 'utf8')
    const module = { exports: {} }
    new Function('require', 'module', 'exports', compiled)(require, module, module.exports)
    const { api } = module.exports
    const products = await api.productsAll()
    assert.equal(products.length, 201)
    assert.equal(products[100].id, 101)
    assert.equal(products[200].id, 201)
    assert.deepEqual(server.requests.map(({ url }) => Number(url.searchParams.get('page'))), [1, 2, 3])
    const page = await api.products()
    assert.equal(page.items.length, 100)
    assert.equal(page.total, 201)
  } finally { globalThis.fetch = originalFetch }
})

for (const pageName of pages) {
  test(`${pageName} reports a failed later product page instead of publishing incomplete joins`, async () => {
    const server = fakeServer(fixture(101), { failPage: 2 })
    const originalFetch = globalThis.fetch
    globalThis.fetch = server.fetch
    const host = pageHost(pageName, 101)
    try {
      await settle()
      const tree = host.render()
      assert.equal(nodes(tree, (node) => node.type?.name === 'FeedbackMessage' && node.props.variant === 'error').length, 1)
      assert.equal(tableRows(tree), undefined)
      assert.equal(host.logoutCount(), 0)
    } finally { host.unmount(); globalThis.fetch = originalFetch }
  })
}

test('InventoryPage keeps loading until the second product page is available', async () => {
  let release
  const gate = new Promise((resolvePromise) => { release = resolvePromise })
  const server = fakeServer(fixture(101), { gate })
  const originalFetch = globalThis.fetch
  globalThis.fetch = server.fetch
  const host = pageHost('InventoryPage', 101)
  try {
    await settle()
    assert.match(text(host.render()), /Đang tải/)
    assert.equal(tableRows(host.render()), undefined)
    release()
    await settle()
    assert.equal(tableRows(host.render()).find((row) => row.productId === 101)?.productName, 'Sản phẩm 101')
  } finally { release(); host.unmount(); globalThis.fetch = originalFetch }
})
