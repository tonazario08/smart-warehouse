import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { test } from 'node:test'

const require = createRequire(import.meta.url)
const sourceRoot = resolve('./node_modules/.tmp/remediation-c/src')
const settle = () => new Promise((done) => setImmediate(done))

function host(pageName, role = 'admin', props = {}) {
  const states = [], effects = [], cache = new Map()
  let cursor = 0, effectCursor = 0, params = { id: '1' }
  const navigations = []
  let logoutCount = 0
  const navigate = (...args) => navigations.push(args), logout = () => { logoutCount++ }
  const react = { ...require('react'), useState(initial) {
    const index = cursor++
    if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial
    return [states[index], (next) => { states[index] = typeof next === 'function' ? next(states[index]) : next }]
  }, useMemo: (fn) => fn(), useEffect(fn, deps) {
    const index = effectCursor++
    if (!effects[index] || deps.some((dep, i) => dep !== effects[index].deps[i])) {
      effects[index]?.cleanup?.()
      effects[index] = { deps, pending: fn }
    }
  } }
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports
    const module = { exports: {} }; cache.set(filename, module)
    const localRequire = (specifier) => {
      if (specifier === 'react') return react
      if (specifier === 'react-router-dom') return { useNavigate: () => navigate, useParams: () => params }
      if (specifier.endsWith('/app/AuthProvider')) return { useAuth: () => ({ token: 'test-token', user: { id: 1, email: 'test@example.com', role, is_active: true }, logout }) }
      if (/\.(css|svg)$/.test(specifier)) return { default: 'test-asset.svg' }
      if (!specifier.startsWith('.')) return require(specifier)
      const base = resolve(dirname(filename), specifier)
      return load([base, `${base}.js`].find((path) => existsSync(path)))
    }
    new Function('require', 'module', 'exports', readFileSync(filename, 'utf8'))(localRequire, module, module.exports)
    return module.exports
  }
  const Page = load(resolve(sourceRoot, `pages/${pageName.startsWith('Movement') ? 'MovementPages' : pageName}.js`))[pageName]
  const render = () => {
    cursor = 0; effectCursor = 0
    const tree = Page(props)
    effects.forEach((effect) => { if (effect.pending) { effect.cleanup = effect.pending(); effect.pending = null } })
    return tree
  }
  return { render, navigations, logoutCount: () => logoutCount, setParams: (next) => { params = next } }
}

const nodes = (tree, predicate) => Array.isArray(tree) ? tree.flatMap((item) => nodes(item, predicate)) : !tree || typeof tree !== 'object' ? [] : [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)]
const text = (tree) => Array.isArray(tree) ? tree.map(text).join('') : tree && typeof tree === 'object' ? text(tree.props?.children) : typeof tree === 'string' || typeof tree === 'number' ? String(tree) : ''
const control = (tree, name) => nodes(tree, (node) => node.props?.['aria-label'] === name)[0]
const field = (tree, label) => nodes(tree, node => node.props?.label === label)[0]
const rows = (tree) => nodes(tree, (node) => node.type?.name === 'DataTable')[0]?.props.rows

function server() {
  const requests = []
  const products = Array.from({ length: 101 }, (_, index) => ({ id: index + 1, sku: `SP-${index + 1}`, name: `Sản phẩm ${index + 1}`, description: null, category_id: 1, supplier_id: index === 100 ? 2 : 1, unit: 'cái', reorder_level: 10, is_active: index !== 100 }))
  const warehouses = [{ id: 1, code: 'WH-1', name: 'Kho một', address: 'Địa chỉ một', latitude: 10.7, longitude: null }, { id: 2, code: 'WH-2', name: 'Kho hai', address: 'Địa chỉ hai', latitude: null, longitude: null }]
  const stock = [{ id: 1, warehouse_id: 1, product_id: 1, quantity: 3 }, { id: 2, warehouse_id: 1, product_id: 101, quantity: 0 }]
  return { requests, products, warehouses, stock, fetch: async (input, options) => {
    const url = new URL(String(input)); requests.push(url)
    const page = Number(url.searchParams.get('page') || 1)
    const payload = url.pathname.endsWith('/products') ? { items: products.slice((page - 1) * 100, page * 100), page, page_size: 100, total: 101 }
      : /\/products\/\d+$/.test(url.pathname) ? products.find(product => product.id === Number(url.pathname.split('/').pop()))
      : url.pathname.endsWith('/categories') ? { items: [{ id: 1, name: 'Danh mục', parent_id: null }], page: 1, page_size: 100, total: 1 }
      : url.pathname.endsWith('/suppliers') ? { items: [{ id: 1, name: 'Supplier One', email: null, phone: null, address: null }, { id: 2, name: 'Supplier Two', email: null, phone: null, address: null }], page: 1, page_size: 100, total: 2 }
      : url.pathname.endsWith('/stock') ? { items: stock, total: stock.length, page, page_size: 100 } : url.pathname.endsWith('/warehouses/1') ? warehouses[0] : { items: warehouses, total: warehouses.length, page, page_size: 100 }
    assert.equal(options.headers.Authorization, 'Bearer test-token')
    return { ok: true, status: 200, json: async () => payload }
  } }
}

test('product pagination can reach record 101 and filters search all API pages', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('ProductsPage'); page.render(); await settle()
    let tree = page.render()
    const next = control(tree, 'Trang sản phẩm tiếp theo'); assert.ok(next)
    next.props.onClick(); page.render(); await settle(); tree = page.render()
    assert.equal(rows(tree)[0].id, 101)
    assert.ok(data.requests.some((url) => url.pathname.endsWith('/products') && url.searchParams.get('page') === '2'))
    control(tree, 'Tìm kiếm sản phẩm').props.onChange({ target: { value: 'Sản phẩm 101' } })
    page.render(); await settle(); tree = page.render()
    assert.deepEqual(rows(tree).map((row) => row.id), [101])
    const columns = nodes(tree, (node) => node.type?.name === 'DataTable')[0].props.columns
    assert.equal(text(columns.find((column) => column.id === 'supplier').render(rows(tree)[0])), 'Supplier Two')
    control(tree, 'Lọc theo nhà cung cấp').props.onChange({ target: { value: '1' } })
    page.render(); await settle(); tree = page.render(); assert.equal(rows(tree), undefined)
    control(tree, 'Lọc theo nhà cung cấp').props.onChange({ target: { value: '2' } })
    page.render(); await settle(); tree = page.render(); assert.deepEqual(rows(tree).map((row) => row.id), [101])
    control(tree, 'Lọc theo trạng thái').props.onChange({ target: { value: 'active' } })
    page.render(); await settle(); tree = page.render(); assert.equal(rows(tree), undefined)
    nodes(tree, (node) => node.type?.name === 'Button' && text(node) === 'Đặt lại bộ lọc')[0].props.onClick()
    page.render(); await settle(); tree = page.render(); assert.equal(rows(tree)[0].id, 1)
  } finally { globalThis.fetch = original }
})

test('supplier lookup failure preserves real product reading and shows the lookup error', async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => new URL(String(input)).pathname.endsWith('/suppliers') ? { ok: false, status: 503, json: async () => ({ detail: 'Supplier unavailable' }) } : data.fetch(input, options)
  try { const page = host('ProductsPage'); page.render(); await settle(); const tree = page.render(); assert.ok(rows(tree).length); assert.ok(nodes(tree, (node) => node.type?.name === 'FeedbackMessage' && node.props.variant === 'warning').length) }
  finally { globalThis.fetch = original }
})

for (const directory of ['categories', 'suppliers']) test(`failed ${directory} names can be retried without losing readable products`, async () => {
  const data = server(), original = globalThis.fetch
  let failed = true
  globalThis.fetch = async (input, options) => failed && new URL(String(input)).pathname.endsWith(`/${directory}`)
    ? { ok: false, status: 503, json: async () => ({ detail: 'Directory unavailable' }) } : data.fetch(input, options)
  try {
    const page = host('ProductsPage'); page.render(); await settle(); let tree = page.render()
    assert.equal(rows(tree).length, 100)
    const retry = nodes(tree, node => node.type?.name === 'Button' && text(node) === 'Thử lại danh mục và nhà cung cấp')[0]
    assert.ok(retry, 'directory lookup failures must expose an explicit retry')
    failed = false
    retry.props.onClick(); page.render(); await settle(); tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    assert.equal(rows(tree).length, 100)
    assert.equal(text(table.props.columns.find(column => column.id === (directory === 'categories' ? 'category' : 'supplier')).render(rows(tree)[0])), directory === 'categories' ? 'Danh mục' : 'Supplier One')
    assert.equal(nodes(tree, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'warning').length, 0)
  } finally { globalThis.fetch = original }
})

test('filtered products refuse incomplete results when a later API page fails', async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => {
    const url = new URL(String(input))
    return url.pathname.endsWith('/products') && url.searchParams.get('page') === '2' ? { ok: false, status: 503, json: async () => ({ detail: 'Later page unavailable' }) } : data.fetch(input, options)
  }
  try {
    const page = host('ProductsPage'); page.render(); await settle(); let tree = page.render()
    control(tree, 'Tìm kiếm sản phẩm').props.onChange({ target: { value: 'Sản phẩm' } }); page.render(); await settle(); tree = page.render()
    assert.equal(rows(tree), undefined); assert.ok(nodes(tree, (node) => node.type?.name === 'FeedbackMessage' && node.props.variant === 'error').length)
  } finally { globalThis.fetch = original }
})

test('client product reading never requires protected supplier access', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try { const page = host('ProductsPage', 'client'); page.render(); await settle(); assert.ok(rows(page.render()).length); assert.equal(data.requests.some((url) => url.pathname.endsWith('/suppliers')), false) }
  finally { globalThis.fetch = original }
})

test('client supplier filters include suppliers found only beyond the first product page and stay available after filtering', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('ProductsPage', 'client'); page.render(); await settle(); let tree = page.render()
    assert.equal(rows(tree).length, 100)
    assert.deepEqual(control(tree, 'Lọc theo nhà cung cấp').props.options.map(option => option.value), [1, 2])
    control(tree, 'Lọc theo nhà cung cấp').props.onChange({ target: { value: '2' } })
    page.render(); await settle(); tree = page.render()
    assert.deepEqual(rows(tree).map(row => row.id), [101])
    control(tree, 'Lọc theo trạng thái').props.onChange({ target: { value: 'active' } })
    page.render(); await settle(); tree = page.render()
    assert.equal(rows(tree), undefined)
    assert.equal(control(tree, 'Lọc theo nhà cung cấp').props.value, 2)
    assert.deepEqual(control(tree, 'Lọc theo nhà cung cấp').props.options.map(option => option.value), [1, 2])
    assert.equal(data.requests.some(url => url.pathname.endsWith('/suppliers')), false)
  } finally { globalThis.fetch = original }
})

test('supplier-name lookup failure still exposes IDs from every product page', async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => new URL(String(input)).pathname.endsWith('/suppliers')
    ? { ok: false, status: 503, json: async () => ({ detail: 'Supplier unavailable' }) } : data.fetch(input, options)
  try {
    const page = host('ProductsPage'); page.render(); await settle(); const tree = page.render()
    assert.deepEqual(control(tree, 'Lọc theo nhà cung cấp').props.options.map(option => ({ value: option.value, label: option.label })), [
      { value: 1, label: 'Nhà cung cấp #1' }, { value: 2, label: 'Nhà cung cấp #2' },
    ])
  } finally { globalThis.fetch = original }
})

test('a failed supplier-options page leaves products readable and retries without silently using partial choices', async () => {
  const data = server(), original = globalThis.fetch
  let failLaterPage = true
  globalThis.fetch = async (input, options) => {
    const url = new URL(String(input))
    return failLaterPage && url.pathname.endsWith('/products') && url.searchParams.get('page') === '2'
      ? { ok: false, status: 503, json: async () => ({ detail: 'Later page unavailable' }) } : data.fetch(input, options)
  }
  try {
    const page = host('ProductsPage', 'client'); page.render(); await settle(); let tree = page.render()
    assert.equal(rows(tree).length, 100)
    assert.ok(nodes(tree, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'warning').length)
    failLaterPage = false
    nodes(tree, node => node.type?.name === 'Button' && text(node) === 'Thử lại bộ lọc sản phẩm')[0].props.onClick()
    page.render(); await settle(); tree = page.render()
    assert.equal(nodes(tree, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'warning').length, 0)
    assert.deepEqual(control(tree, 'Lọc theo nhà cung cấp').props.options.map(option => option.value), [1, 2])
  } finally { globalThis.fetch = original }
})

test('editing a product retains selected category and supplier options missing from the first lookup page', async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => new URL(String(input)).pathname.endsWith('/products/1')
    ? { ok: true, status: 200, json: async () => ({ id: 1, sku: 'SP-1', name: 'Máy quét', description: 'Giữ mô tả', category_id: 101, supplier_id: 101, unit: 'cái', reorder_level: 5, is_active: false }) } : data.fetch(input, options)
  try {
    const page = host('ProductFormPage', 'admin', { mode: 'edit' }); page.render(); await settle(); const tree = page.render()
    assert.equal(field(tree, 'Danh mục').props.value, 101)
    assert.ok(field(tree, 'Danh mục').props.options.some(option => option.value === 101))
    assert.equal(field(tree, 'Nhà cung cấp').props.value, 101)
    assert.ok(field(tree, 'Nhà cung cấp').props.options.some(option => option.value === 101))
  } finally { globalThis.fetch = original }
})

test('category filters include product references missing from the first lookup page', async () => {
  const data = server(), original = globalThis.fetch
  data.products[100].category_id = 101
  globalThis.fetch = data.fetch
  try {
    const page = host('ProductsPage', 'client'); page.render(); await settle(); let tree = page.render()
    assert.deepEqual(control(tree, 'Lọc theo danh mục').props.options.map(option => option.value), [1, 101])
    control(tree, 'Lọc theo danh mục').props.onChange({ target: { value: '101' } })
    page.render(); await settle(); tree = page.render()
    assert.deepEqual(rows(tree).map(row => row.id), [101])
  } finally { globalThis.fetch = original }
})

test('product deletion cannot be confirmed twice while its request is pending', async () => {
  const data = server(), original = globalThis.fetch
  let deletionRequests = 0, finishDeletion
  globalThis.fetch = async (input, options) => {
    if (options.method === 'DELETE') {
      deletionRequests++
      return new Promise(resolveRequest => { finishDeletion = () => resolveRequest({ ok: true, status: 204 }) })
    }
    return data.fetch(input, options)
  }
  try {
    const page = host('ProductsPage'); page.render(); await settle(); let tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    const actions = table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0])
    nodes(actions, node => node.type?.name === 'Button')[1].props.onClick()
    tree = page.render()
    nodes(tree, node => node.type?.name === 'ConfirmDialog')[0].props.onConfirm()
    tree = page.render()
    const dialog = nodes(tree, node => node.type?.name === 'ConfirmDialog')[0]
    dialog.props.onConfirm()
    assert.equal(deletionRequests, 1)
    assert.equal(dialog.props.busy, true)
    finishDeletion(); await settle()
  } finally { finishDeletion?.(); await settle(); globalThis.fetch = original }
})

test('rejected product deletion reports its error inside the dialog while preserving the table and supports recovery', async () => {
  const data = server(), original = globalThis.fetch
  let rejectDeletion = true
  globalThis.fetch = async (input, options) => options.method === 'DELETE'
    ? rejectDeletion ? { ok: false, status: 409, json: async () => ({ detail: 'Product is referenced by inventory data' }) } : { ok: true, status: 204 }
    : data.fetch(input, options)
  try {
    const page = host('ProductsPage'); page.render(); await settle(); let tree = page.render()
    const openDelete = () => {
      const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
      const actions = table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0])
      nodes(actions, node => node.type?.name === 'Button')[1].props.onClick()
      tree = page.render()
    }
    openDelete()
    nodes(tree, node => node.type?.name === 'ConfirmDialog')[0].props.onConfirm()
    page.render(); await settle(); tree = page.render()
    let dialog = nodes(tree, node => node.type?.name === 'ConfirmDialog')[0]
    assert.match(text(dialog), /Không thể xóa sản phẩm vì đang được tham chiếu trong dữ liệu tồn kho/)
    assert.doesNotMatch(text(dialog), /Product is referenced by inventory data/)
    assert.equal(dialog.props.open, true)
    assert.equal(dialog.props.busy, false)
    assert.equal(rows(tree).length, 100)
    dialog.props.onCancel(); tree = page.render()
    assert.doesNotMatch(text(tree), /Không thể xóa sản phẩm vì đang được tham chiếu trong dữ liệu tồn kho/)
    openDelete()
    dialog = nodes(tree, node => node.type?.name === 'ConfirmDialog')[0]
    assert.doesNotMatch(text(dialog), /Không thể xóa sản phẩm vì đang được tham chiếu trong dữ liệu tồn kho/)
    rejectDeletion = false
    dialog.props.onConfirm(); page.render(); await settle(); tree = page.render()
    assert.equal(nodes(tree, node => node.type?.name === 'ConfirmDialog')[0].props.open, false)
  } finally { globalThis.fetch = original }
})

for (const [status, detail, expected] of [
  [403, 'Forbidden', 'Bạn không có quyền xóa sản phẩm.'],
  [404, 'Product not found', 'Không tìm thấy sản phẩm. Vui lòng tải lại danh sách.'],
  [null, 'Failed to fetch', 'Không thể xóa sản phẩm. Vui lòng thử lại.'],
]) test(`product deletion localizes ${status ?? 'network'} failures without dismissing the dialog or losing the list`, async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => {
    if (options.method !== 'DELETE') return data.fetch(input, options)
    if (status === null) throw new TypeError(detail)
    return { ok: false, status, json: async () => ({ detail }) }
  }
  try {
    const page = host('ProductsPage'); page.render(); await settle(); let tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    const actions = table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0])
    nodes(actions, node => node.type?.name === 'Button')[1].props.onClick()
    tree = page.render()
    nodes(tree, node => node.type?.name === 'ConfirmDialog')[0].props.onConfirm()
    page.render(); await settle(); tree = page.render()
    const dialog = nodes(tree, node => node.type?.name === 'ConfirmDialog')[0]
    assert.equal(text(dialog), expected)
    assert.equal(dialog.props.open, true)
    assert.equal(dialog.props.busy, false)
    assert.equal(rows(tree).length, 100)
    assert.equal(page.logoutCount(), 0)
  } finally { globalThis.fetch = original }
})

for (const mode of ['create', 'edit']) test(`product ${mode} submission preserves description and supported payload fields`, async () => {
  const data = server(), original = globalThis.fetch, writes = []
  globalThis.fetch = async (input, options) => {
    if (options.method === 'POST' || options.method === 'PUT') {
      writes.push({ url: new URL(String(input)), input: JSON.parse(options.body), token: options.headers.Authorization })
      return { ok: true, status: 200, json: async () => ({ id: 1, ...JSON.parse(options.body) }) }
    }
    return data.fetch(input, options)
  }
  try {
    const page = host('ProductFormPage', 'admin', { mode }); page.render(); await settle(); let tree = page.render()
    for (const [label, value] of [['SKU', 'NEW-1'], ['Tên sản phẩm', 'Máy quét'], ['Đơn vị tính', 'cái'], ['Mức tồn tối thiểu', '5'], ['Danh mục', '1'], ['Nhà cung cấp', '2']]) {
      field(tree, label).props.onChange({ target: { value } }); tree = page.render()
    }
    nodes(tree, node => node.type === 'textarea')[0].props.onChange({ target: { value: 'Giữ nguyên mô tả tiếng Việt' } }); tree = page.render()
    await nodes(tree, node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
    assert.equal(writes.length, 1)
    assert.equal(writes[0].url.pathname, `/api/v1/products${mode === 'edit' ? '/1' : ''}`)
    assert.equal(writes[0].token, 'Bearer test-token')
    assert.deepEqual(writes[0].input, { sku: 'NEW-1', name: 'Máy quét', description: 'Giữ nguyên mô tả tiếng Việt', unit: 'cái', reorder_level: 5, category_id: 1, supplier_id: 2, is_active: true })
    assert.equal(page.navigations[0][0], '/products')
  } finally { globalThis.fetch = original }
})

for (const type of ['inbound', 'outbound']) test(`${type} preview derives stock for the selected warehouse/product and keeps the backend authoritative`, async () => {
  const data = server(), original = globalThis.fetch, writes = []
  globalThis.fetch = async (input, options) => {
    if (options.method === 'POST') {
      writes.push({ url: new URL(String(input)), input: JSON.parse(options.body), token: options.headers.Authorization })
      return type === 'outbound' ? { ok: false, status: 409, json: async () => ({ detail: 'Insufficient stock' }) } : { ok: true, status: 200, json: async () => ({ id: 1 }) }
    }
    return data.fetch(input, options)
  }
  try {
    const page = host('MovementFormPage', 'warehouse', { type }); page.render(); await settle(); let tree = page.render()
    assert.equal(field(tree, 'Sản phẩm').props.options.length, 101)
    field(tree, 'Kho hàng').props.onChange({ target: { value: '1' } })
    field(tree, 'Sản phẩm').props.onChange({ target: { value: '1' } })
    field(tree, 'Số lượng').props.onChange({ target: { value: '4' } })
    field(tree, 'Mã phiếu').props.onChange({ target: { value: ' REF-1 ' } })
    field(tree, 'Ghi chú').props.onChange({ target: { value: ' Ghi chú ' } })
    page.render(); await settle(); tree = page.render()
    const impact = nodes(tree, node => node.props?.className === 'movement-stock-impact')[0]
    assert.match(text(impact), /Tồn hiện tại3 cái/)
    assert.ok(text(impact).includes(type === 'inbound' ? 'Sau khi nhập7 cái' : 'Sau khi xuất-1 cái'))
    if (type === 'outbound') assert.ok(nodes(impact, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'warning').length)
    await nodes(tree, node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
    assert.equal(writes.length, 1)
    assert.equal(writes[0].url.pathname, `/api/v1/${type}s`)
    assert.equal(writes[0].token, 'Bearer test-token')
    assert.deepEqual(writes[0].input, { warehouse_id: 1, product_id: 1, quantity: 4, reference: 'REF-1', note: 'Ghi chú' })
    tree = page.render(); await settle(); tree = page.render()
    if (type === 'outbound') {
      assert.equal(page.navigations.length, 0)
      assert.ok(nodes(tree, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'error').length)
    } else assert.equal(page.navigations[0][0], '/inbound')
  } finally { globalThis.fetch = original }
})

test('stock lookup failure never appears as zero stock and supports retry', async () => {
  const data = server(), original = globalThis.fetch
  let failStock = true
  globalThis.fetch = async (input, options) => failStock && new URL(String(input)).pathname.endsWith('/stock')
    ? { ok: false, status: 503, json: async () => ({ detail: 'Stock unavailable' }) } : data.fetch(input, options)
  try {
    const page = host('MovementFormPage', 'warehouse', { type: 'inbound' }); page.render(); await settle(); let tree = page.render()
    field(tree, 'Kho hàng').props.onChange({ target: { value: '1' } })
    field(tree, 'Sản phẩm').props.onChange({ target: { value: '1' } })
    page.render(); await settle(); tree = page.render()
    let impact = nodes(tree, node => node.props?.className === 'movement-stock-impact')[0]
    assert.equal(nodes(impact, node => node.type === 'dl').length, 0)
    assert.ok(nodes(impact, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'error').length)
    failStock = false
    nodes(impact, node => node.type?.name === 'Button')[0].props.onClick()
    page.render(); await settle(); tree = page.render()
    impact = nodes(tree, node => node.props?.className === 'movement-stock-impact')[0]
    assert.match(text(impact), /Tồn hiện tại3 cái/)
  } finally { globalThis.fetch = original }
})

test('movement preview ignores stale stock responses after changing the selection', async () => {
  const data = server(), original = globalThis.fetch
  let finishOldRequest, stockRequests = 0
  globalThis.fetch = async (input, options) => {
    if (new URL(String(input)).pathname.endsWith('/stock') && ++stockRequests === 1) {
      return new Promise(resolveRequest => { finishOldRequest = () => resolveRequest({ ok: true, status: 200, json: async () => ({ items: [{ id: 1, warehouse_id: 1, product_id: 1, quantity: 999 }], total: 1, page: 1, page_size: 100 }) }) })
    }
    return data.fetch(input, options)
  }
  try {
    const page = host('MovementFormPage', 'warehouse', { type: 'inbound' }); page.render(); await settle(); let tree = page.render()
    field(tree, 'Kho hàng').props.onChange({ target: { value: '1' } })
    field(tree, 'Sản phẩm').props.onChange({ target: { value: '1' } })
    page.render(); await settle(); tree = page.render()
    field(tree, 'Sản phẩm').props.onChange({ target: { value: '101' } })
    field(tree, 'Số lượng').props.onChange({ target: { value: '2' } })
    page.render(); await settle(); tree = page.render()
    finishOldRequest(); await settle(); tree = page.render()
    const impact = nodes(tree, node => node.props?.className === 'movement-stock-impact')[0]
    assert.match(text(impact), /Tồn hiện tại0 cái/)
    assert.match(text(impact), /Sau khi nhập2 cái/)
    assert.doesNotMatch(text(impact), /999/)
  } finally { globalThis.fetch = original }
})

for (const status of [401, 403, 503]) test(`protected movement load handles ${status} without a writable form`, async () => {
  const data = server(), original = globalThis.fetch
  globalThis.fetch = async (input, options) => new URL(String(input)).pathname.endsWith('/warehouses')
    ? { ok: false, status, json: async () => ({ detail: 'Unavailable' }) } : data.fetch(input, options)
  try {
    const page = host('MovementFormPage', 'warehouse', { type: 'outbound' }); page.render(); await settle(); const tree = page.render()
    assert.equal(nodes(tree, node => node.type === 'form').length, 0)
    assert.equal(page.logoutCount(), status === 401 ? 1 : 0)
    if (status !== 401) assert.ok(nodes(tree, node => node.type?.name === 'FeedbackMessage' && node.props.variant === 'error').length)
  } finally { globalThis.fetch = original }
})

for (const mode of ['create', 'edit']) test(`warehouse ${mode} submission preserves coordinates including zero and null`, async () => {
  const data = server(), original = globalThis.fetch, writes = []
  globalThis.fetch = async (input, options) => {
    if (options.method === 'POST' || options.method === 'PUT') {
      writes.push({ url: new URL(String(input)), input: JSON.parse(options.body), token: options.headers.Authorization })
      return { ok: true, status: 200, json: async () => ({ id: 1, ...JSON.parse(options.body) }) }
    }
    return data.fetch(input, options)
  }
  try {
    const page = host('WarehouseFormPage', 'admin', { mode }); page.render(); await settle(); let tree = page.render()
    for (const [label, value] of [['Mã kho', ' WH-1 '], ['Tên kho', ' Kho một '], ['Địa chỉ', ' Hà Nội '], ['Vĩ độ', '0'], ['Kinh độ', '']]) {
      field(tree, label).props.onChange({ target: { value } }); tree = page.render()
    }
    nodes(tree, node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} }); await settle()
    assert.equal(writes.length, 1)
    assert.equal(writes[0].url.pathname, `/api/v1/warehouses${mode === 'edit' ? '/1' : ''}`)
    assert.equal(writes[0].token, 'Bearer test-token')
    assert.deepEqual(writes[0].input, { code: 'WH-1', name: 'Kho một', address: 'Hà Nội', latitude: 0, longitude: null })
    assert.equal(page.navigations[0][0], '/warehouses/1')
  } finally { globalThis.fetch = original }
})

for (const role of ['client', 'warehouse']) test(`${role} product list hides administrative actions`, async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('ProductsPage', role); page.render(); await settle(); const tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    assert.equal(table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0]), null)
    assert.equal(nodes(tree, node => node.type?.name === 'PageHeader')[0].props.actions, undefined)
  } finally { globalThis.fetch = original }
})

test('compact product action buttons retain accessible names and their edit/delete behavior', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('ProductsPage'); page.render(); await settle(); const tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    const actionTree = table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0])
    const buttons = nodes(actionTree, node => node.type?.name === 'Button').map(node => node.type(node.props))
    assert.deepEqual(buttons.map(node => node.props['aria-label']), ['Chỉnh sửa Sản phẩm 1', 'Xóa Sản phẩm 1'])
    assert.deepEqual(buttons.map(node => node.props.type), ['button', 'button'])
    assert.equal(nodes(actionTree, node => node.type === 'svg').length, 0)
    const actionImages = nodes(actionTree, node => node.type === 'img')
    assert.equal(actionImages.length, 2)
    assert.ok(actionImages.every(node => node.props.alt === '' && node.props.src))
    buttons[0].props.onClick(); assert.equal(page.navigations[0][0], '/products/1/edit')
    buttons[1].props.onClick()
    assert.equal(nodes(page.render(), node => node.type?.name === 'ConfirmDialog')[0].props.open, true)
  } finally { globalThis.fetch = original }
})

for (const role of ['admin', 'client']) test(`compact warehouse actions preserve ${role} permissions and navigation`, async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('WarehousesPage', role); page.render(); await settle(); const tree = page.render()
    const table = nodes(tree, node => node.type?.name === 'DataTable')[0]
    const actionTree = table.props.columns.find(column => column.id === 'actions').render(rows(tree)[0])
    const buttons = nodes(actionTree, node => node.type?.name === 'Button').map(node => node.type(node.props))
    assert.equal(buttons.length, role === 'admin' ? 2 : 1)
    assert.equal(buttons[0].props['aria-label'], 'Xem chi tiết Kho một')
    assert.equal(buttons[0].props.type, 'button')
    const detailImage = nodes(buttons[0], node => node.type === 'img')[0]
    assert.ok(detailImage, 'warehouse details must use the approved action-slot asset')
    assert.equal(detailImage.props.alt, '')
    buttons[0].props.onClick(); assert.equal(page.navigations[0][0], '/warehouses/1')
    if (role === 'admin') {
      const editImage = nodes(buttons[1], node => node.type === 'img')[0]
      assert.ok(editImage, 'warehouse editing must use its approved local asset')
      assert.equal(editImage.props.alt, '')
      buttons[1].props.onClick(); assert.equal(page.navigations[1][0], '/warehouses/1/edit')
    }
  } finally { globalThis.fetch = original }
})

test('warehouse attention counts warehouses and includes zero-stock products', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('WarehousesPage'); page.render(); await settle(); const tree = page.render()
    const kpis = nodes(tree, (node) => node.type === 'article' && node.props.className?.includes('warehouse-kpi'))
    assert.equal(kpis.length, 4)
    assert.match(text(kpis.find((node) => text(node).includes('Kho cần chú ý'))), /Kho cần chú ý1/)
    const table = nodes(tree, (node) => node.type?.name === 'DataTable')[0]
    assert.equal(table.props.columns.find((column) => column.id === 'address').render(rows(tree)[0]), 'Địa chỉ một')
    control(tree, 'Lọc theo tồn kho').props.onChange({ target: { value: 'attention' } }); assert.deepEqual(rows(page.render()).map((row) => row.id), [1])
  } finally { globalThis.fetch = original }
})

test('warehouse detail renders zero-stock status and independent real coordinates', async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('WarehouseDetailPage'); page.render(); await settle(); const tree = page.render()
    const table = nodes(tree, (node) => node.type?.name === 'DataTable')[0]
    assert.match(text(table.props.columns.find((column) => column.id === 'status').render(rows(tree).find((row) => row.quantity === 0))), /Hết hàng/)
    assert.match(text(tree), /Vĩ độ10.7/); assert.match(text(tree), /Kinh độChưa cập nhật/)
    assert.doesNotMatch(text(tree), /Đang hoạt động|Vận hành bình thường/)
  } finally { globalThis.fetch = original }
})

for (const id of ['invalid', '0', '-1', '1.5']) test(`warehouse detail clears the previous warehouse when the route changes to invalid ID ${id}`, async () => {
  const data = server(), original = globalThis.fetch; globalThis.fetch = data.fetch
  try {
    const page = host('WarehouseDetailPage'); page.render(); await settle()
    assert.equal(nodes(page.render(), node => node.type?.name === 'PageHeader')[0].props.title, 'Kho một')
    const requestCount = data.requests.length
    page.setParams({ id }); page.render(); await settle()
    const tree = page.render()
    assert.equal(nodes(tree, node => node.type?.name === 'PageHeader').length, 0)
    assert.equal(rows(tree), undefined)
    assert.equal(nodes(tree, node => node.type?.name === 'EmptyState')[0].props.title, 'Không tìm thấy kho hàng')
    assert.equal(data.requests.length, requestCount)
  } finally { globalThis.fetch = original }
})
