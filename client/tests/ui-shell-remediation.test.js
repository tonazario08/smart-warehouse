import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { test } from 'node:test'

const require = createRequire(import.meta.url)
const sourceRoot = resolve('./node_modules/.tmp/remediation-c/src')
const nodes = (tree, predicate) => Array.isArray(tree) ? tree.flatMap(child => nodes(child, predicate)) : !tree || typeof tree !== 'object' ? [] : [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)]
const text = tree => Array.isArray(tree) ? tree.map(text).join('') : tree && typeof tree === 'object' ? text(tree.props?.children) : typeof tree === 'string' ? tree : ''

// Run real component handlers/effects. Only framework hooks, route/auth context,
// and the browser's dialog/focus boundary are hosted without a DOM dependency.
function componentHost(path, exportName, initialProps = {}, authOverrides = {}, pathname = '/login') {
  const slots = [], effects = [], cache = new Map(), navigations = [], loginCalls = []
  let cursor = 0, effectCursor = 0, props = initialProps
  const auth = { user: null, error: '', loading: false, clearError() {}, login: async (...args) => { loginCalls.push(args); return true }, ...authOverrides }
  const react = { ...require('react'), useState(initial) {
    const index = cursor++
    if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial
    return [slots[index], next => { slots[index] = typeof next === 'function' ? next(slots[index]) : next }]
  }, useRef(initial) {
    const index = cursor++
    return slots[index] ??= { current: initial }
  }, useId() {
    const index = cursor++
    return slots[index] ??= `test-id-${index}`
  }, useEffect(fn, deps) {
    const index = effectCursor++
    if (!effects[index] || deps.some((dep, i) => dep !== effects[index].deps[i])) {
      effects[index]?.cleanup?.()
      effects[index] = { deps, pending: fn, run: fn }
    }
  } }
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports
    const module = { exports: {} }; cache.set(filename, module)
    const localRequire = specifier => {
      if (specifier === 'react') return react
      if (specifier === 'react-router-dom') return { useNavigate: () => (...args) => navigations.push(args), useLocation: () => ({ pathname, state: { from: { pathname: '/inventory' } } }), Link: 'a', NavLink: 'a', Navigate: 'navigate' }
      if (specifier.endsWith('/app/AuthProvider')) return { useAuth: () => auth }
      if (/\.(css|svg)$/.test(specifier)) return { default: 'test-asset.svg' }
      if (!specifier.startsWith('.')) return require(specifier)
      const base = resolve(dirname(filename), specifier)
      return load([base, `${base}.js`].find(existsSync))
    }
    new Function('require', 'module', 'exports', readFileSync(filename, 'utf8'))(localRequire, module, module.exports)
    return module.exports
  }
  const Component = load(resolve(sourceRoot, path))[exportName]
  return { render(nextProps = props, element) {
    props = nextProps; cursor = 0; effectCursor = 0
    const tree = Component(props)
    if (element && tree.props.ref) tree.props.ref.current = element
    effects.forEach(effect => { if (effect.pending) { effect.cleanup = effect.pending(); effect.pending = null } })
    return tree
  }, replayEffects() {
    effects.forEach(effect => effect.cleanup?.())
    effects.forEach(effect => { effect.cleanup = effect.run() })
  }, unmount() { effects.forEach(effect => effect.cleanup?.()) }, navigations, loginCalls }
}

function nativeDialog() {
  const doc = { activeElement: null }
  const focusable = name => ({ name, isConnected: true, focus() { doc.activeElement = this } })
  const trigger = focusable('trigger'), cancel = focusable('cancel'), confirm = focusable('confirm')
  doc.activeElement = trigger
  const calls = { showModal: 0, close: 0 }
  const dialog = { ...focusable('dialog'), ownerDocument: doc, open: false,
    showModal() { calls.showModal++; this.open = true; doc.activeElement = confirm },
    close() { calls.close++; this.open = false },
    querySelector(selector) { assert.equal(selector, '[data-dialog-cancel]'); return cancel },
    getBoundingClientRect() { return { left: 100, right: 500, top: 100, bottom: 400 } },
  }
  const pointer = (x, y, target = dialog) => ({ target, currentTarget: dialog, clientX: x, clientY: y })
  return { dialog, doc, trigger, cancel, calls, pointer }
}

test('controlled confirmation uses showModal, starts with cancel focus and restores the trigger on close', () => {
  const browser = nativeDialog(), props = { open: true, onConfirm() {}, onCancel() {} }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  const tree = host.render(props, browser.dialog)
  assert.equal(browser.calls.showModal, 1)
  assert.equal(browser.doc.activeElement, browser.cancel)
  assert.equal(tree.props.open, undefined)
  assert.ok(tree.props['aria-describedby'])
  assert.ok('data-dialog-cancel' in nodes(tree, node => node.type?.name === 'Button')[0].props)
  host.render({ ...props, open: false }, browser.dialog)
  assert.equal(browser.calls.close, 1)
  assert.equal(browser.doc.activeElement, browser.trigger)
})

test('Strict Mode effect replay restores and reopens the modal without reporting cancellation', () => {
  const browser = nativeDialog(); let cancelled = 0
  const props = { open: true, onConfirm() {}, onCancel() { cancelled++ } }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  const tree = host.render(props, browser.dialog)
  host.replayEffects()
  assert.equal(browser.calls.showModal, 2)
  assert.equal(browser.doc.activeElement, browser.cancel)
  tree.props.onClose({ currentTarget: browser.dialog })
  assert.equal(cancelled, 0)
  host.unmount()
  assert.equal(browser.dialog.open, false)
  assert.equal(browser.doc.activeElement, browser.trigger)
})

test('closing the dialog does not focus a trigger that was removed after the confirmed action', () => {
  const browser = nativeDialog(), props = { open: true, onConfirm() {}, onCancel() {} }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  host.render(props, browser.dialog)
  browser.trigger.isConnected = false
  host.render({ ...props, open: false }, browser.dialog)
  assert.notEqual(browser.doc.activeElement, browser.trigger)
})

test('Escape requests controlled cancellation once and never closes the busy dialog', () => {
  const browser = nativeDialog(); let cancelled = 0, prevented = 0
  const props = { open: true, onConfirm() {}, onCancel() { cancelled++ } }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  let tree = host.render({ ...props, busy: true }, browser.dialog)
  tree.props.onCancel({ preventDefault() { prevented++ } })
  assert.equal(cancelled, 0)
  assert.equal(browser.dialog.open, true)
  tree = host.render({ ...props, busy: false }, browser.dialog)
  tree.props.onCancel({ preventDefault() { prevented++ } })
  tree.props.onCancel({ preventDefault() { prevented++ } })
  assert.equal(prevented, 3)
  assert.equal(cancelled, 1)
  assert.equal(browser.dialog.open, true)
})

test('an external native close remains controlled, including while busy', () => {
  const browser = nativeDialog(); let cancelled = 0
  const props = { open: true, onConfirm() {}, onCancel() { cancelled++ } }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  let tree = host.render({ ...props, busy: true }, browser.dialog)
  browser.dialog.close(); tree.props.onClose({ currentTarget: browser.dialog })
  assert.equal(browser.dialog.open, true)
  assert.equal(cancelled, 0)
  tree = host.render({ ...props, busy: false }, browser.dialog)
  browser.dialog.close(); tree.props.onClose({ currentTarget: browser.dialog })
  assert.equal(cancelled, 1)
})

test('only a press and release outside the dialog cancels, and busy blocks backdrop cancellation', () => {
  const browser = nativeDialog(); let cancelled = 0
  const props = { open: true, onConfirm() {}, onCancel() { cancelled++ } }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  let tree = host.render(props, browser.dialog)
  tree.props.onPointerDown(browser.pointer(200, 200))
  tree.props.onClick(browser.pointer(50, 50))
  assert.equal(cancelled, 0)
  tree = host.render({ ...props, busy: true }, browser.dialog)
  tree.props.onPointerDown(browser.pointer(50, 50)); tree.props.onClick(browser.pointer(50, 50))
  assert.equal(cancelled, 0)
  tree = host.render({ ...props, busy: false }, browser.dialog)
  tree.props.onPointerDown(browser.pointer(50, 50)); tree.props.onClick(browser.pointer(50, 50))
  assert.equal(cancelled, 1)
})

test('confirmation is locked synchronously until a pending request finishes', () => {
  const browser = nativeDialog(); let confirmed = 0
  const props = { open: true, onConfirm() { confirmed++ }, onCancel() {} }
  const host = componentHost('shared/ui/ConfirmDialog.js', 'ConfirmDialog', props)
  let tree = host.render(props, browser.dialog)
  let buttons = nodes(tree, node => node.type?.name === 'Button')
  buttons[1].props.onClick(); buttons[1].props.onClick()
  assert.equal(confirmed, 1)
  tree = host.render({ ...props, busy: true }, browser.dialog)
  buttons = nodes(tree, node => node.type?.name === 'Button').map(node => node.type(node.props))
  assert.deepEqual(buttons.map(node => node.props.disabled), [true, true])
  tree = host.render({ ...props, busy: false }, browser.dialog)
  nodes(tree, node => node.type?.name === 'Button')[1].props.onClick()
  assert.equal(confirmed, 2)
})

for (const page of ['ForgotPasswordPage', 'ResetPasswordPage']) test(`${page} explains unavailable recovery upfront without soliciting credentials`, () => {
  const host = componentHost('pages/AuthPages.js', page)
  const tree = host.render()
  assert.equal(nodes(tree, node => node.type === 'form' || node.type === 'input' || node.type?.name === 'Input').length, 0)
  assert.match(text(tree), /chưa hỗ trợ/)
  assert.match(text(tree), /quản trị viên/)
  assert.ok(nodes(tree, node => node.type === 'a' && node.props.to === '/login').length)
})

test('real login keeps its credentials and return route without a decorative remember checkbox', async () => {
  const host = componentHost('pages/AuthPages.js', 'LoginPage')
  let tree = host.render()
  assert.equal(nodes(tree, node => node.props?.className === 'auth-form__checkbox' || node.type === 'input' && node.props.type === 'checkbox').length, 0)
  nodes(tree, node => node.props?.label === 'Email')[0].props.onChange({ target: { value: 'user@example.com' } })
  nodes(tree, node => node.props?.label === 'Mật khẩu')[0].props.onChange({ target: { value: 'test-only-password' } })
  tree = host.render()
  await nodes(tree, node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
  assert.deepEqual(host.loginCalls, [['user@example.com', 'test-only-password']])
  assert.deepEqual(host.navigations, [['/inventory', { replace: true }]])
})

test('Topbar presents unsupported search and notifications as explicitly unavailable controls', () => {
  const host = componentHost('shared/layout/Topbar.js', 'Topbar')
  const tree = host.render()
  const search = nodes(tree, node => node.type === 'input' && node.props.type === 'search')[0]
  assert.ok(search)
  assert.equal(search.props.disabled, true)
  assert.match(search.props['aria-label'], /chưa khả dụng/)
  const notification = nodes(tree, node => node.type === 'button')[0]
  assert.equal(notification.props.disabled, true)
  assert.match(notification.props['aria-label'], /chưa khả dụng/)
})

for (const [role, expectedLinks] of [
  ['admin', [['/dashboard', 'Bảng điều khiển'], ['/products', 'Sản phẩm'], ['/inventory', 'Tồn kho'], ['/warehouses', 'Kho hàng'], ['/inbound', 'Nhập kho'], ['/outbound', 'Xuất kho']]],
  ['warehouse', [['/inventory', 'Tồn kho'], ['/warehouses', 'Kho hàng'], ['/inbound', 'Nhập kho'], ['/outbound', 'Xuất kho']]],
  ['client', [['/products', 'Sản phẩm'], ['/inventory', 'Tồn kho'], ['/warehouses', 'Kho hàng']]],
]) test(`${role} sidebar destinations retain accessible names when responsive CSS hides visible labels`, () => {
  const user = { id: 1, email: `${role}@example.com`, role, is_active: true }
  const host = componentHost('shared/layout/Sidebar.js', 'Sidebar', { user, onLogout() {} })
  const links = nodes(host.render(), node => node.type === 'a')
  assert.deepEqual(links.map(link => [link.props.to, link.props['aria-label']]), expectedLinks)
  assert.deepEqual(links.map(link => link.props.title), expectedLinks.map(([, label]) => label))
})

for (const [role, roleLabel] of [['admin', 'Quản trị viên'], ['warehouse', 'Nhân viên kho'], ['client', 'Khách hàng']]) test(`${role} account summary identifies the account without its responsive text and still logs out`, () => {
  const user = { id: 1, email: `${role}@example.com`, role, is_active: true }
  let loggedOut = 0
  const host = componentHost('shared/layout/UserMenu.js', 'UserMenu', { user, onLogout() { loggedOut++ } })
  const tree = host.render(), summary = nodes(tree, node => node.type === 'summary')[0]
  assert.equal(tree.type, 'details')
  assert.ok(summary.props['aria-label']?.includes(roleLabel))
  assert.ok(summary.props['aria-label']?.includes(user.email))
  assert.equal(summary.props.title, summary.props['aria-label'])
  nodes(tree, node => node.type?.name === 'Button')[0].props.onClick()
  assert.equal(loggedOut, 1)
})

test('breadcrumbs keep the resource area on create, edit and detail routes with a safe unknown-route fallback', () => {
  for (const [pathname, expected] of [
    ['/products/new', 'Sản phẩm'], ['/products/17/edit', 'Sản phẩm'],
    ['/inventory/1/2', 'Tồn kho'], ['/warehouses/new', 'Kho hàng'],
    ['/warehouses/3', 'Kho hàng'], ['/warehouses/3/edit', 'Kho hàng'],
    ['/inbound/new', 'Nhập kho'], ['/outbound/new', 'Xuất kho'],
    ['/dashboard', 'Bảng điều khiển'], ['/', 'Bảng điều khiển'], ['/unknown/thing', 'Chi tiết'],
  ]) {
    const host = componentHost('shared/layout/Breadcrumbs.js', 'Breadcrumbs', {}, {}, pathname)
    assert.equal(text(nodes(host.render(), node => node.type === 'strong')[0]), expected, pathname)
  }
})
