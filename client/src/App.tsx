import { FormEvent, useEffect, useMemo, useState } from 'react'
import { ApiError, api } from './api'
import type { Category, Product, ProductInput, Stock, User, Warehouse } from './types'

const tokenKey = 'smart-warehouse-token'
const blank: ProductInput = { sku: '', name: '', description: null, category_id: 0, supplier_id: null, unit: 'each', reorder_level: 0, is_active: true }
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Unable to reach the API.'

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey))
  const [user, setUser] = useState<User | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [stock, setStock] = useState<Stock[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function logout() { localStorage.removeItem(tokenKey); setToken(null); setUser(null); setProducts([]); setCategories([]); setWarehouses([]); setStock([]) }
  async function load(activeToken: string) {
    setLoading(true); setError('')
    try {
      const [me, productPage, categoryPage, warehouseItems, stockItems] = await Promise.all([api.me(activeToken), api.products(), api.categories(), api.warehouses(activeToken), api.stock(activeToken)])
      setUser(me); setProducts(productPage.items); setCategories(categoryPage.items); setWarehouses(warehouseItems); setStock(stockItems)
    } catch (cause) { setError(message(cause)); if (cause instanceof ApiError && /token|auth|user/i.test(cause.message)) logout() } finally { setLoading(false) }
  }
  useEffect(() => { if (token) void load(token) }, [])
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError('')
    try { const result = await api.login(email, password); localStorage.setItem(tokenKey, result.access_token); setToken(result.access_token); setPassword(''); await load(result.access_token) }
    catch (cause) { setError(message(cause)); setLoading(false) }
  }
  const balances = useMemo(() => stock.map((item) => ({ ...item, product: products.find((value) => value.id === item.product_id), warehouse: warehouses.find((value) => value.id === item.warehouse_id) })), [stock, products, warehouses])

  if (!user) return <main className="app-shell login-shell"><section className="signin-panel"><p className="kicker">Smart Warehouse</p><h1>Run the floor with a clear view.</h1><p>Sign in to see the inventory and warehouse records assigned to your role.</p><form className="login-form" onSubmit={login}><label>Work email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label><button disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>{error && <p className="message" role="alert">{error}</p>}</form></section></main>

  return <main className="app-shell workspace"><header><div><p className="kicker">Smart Warehouse</p><h1>Operations desk</h1></div><div className="account"><span>{user.email}</span><b>{user.role}</b><button className="quiet" onClick={logout}>Sign out</button></div></header>{error && <p className="banner" role="alert">{error}</p>}{loading && <p className="loading">Refreshing live records…</p>}
    <section><Heading label="Catalogue" title="Products" note={`${products.length} records`} /><ProductTable products={products} categories={categories} /></section>
    {user.role === 'admin' && token && <ProductManager token={token} categories={categories} products={products} refresh={() => load(token)} />}
    <section><Heading label="Live balance" title="Inventory by warehouse" note={`Read-only for ${user.role}`} /><div className="inventory">{balances.length ? balances.map((row) => <article key={row.id}><div><strong>{row.product?.name ?? `Product #${row.product_id}`}</strong><span>{row.product?.sku}</span></div><div><span>{row.warehouse?.code ?? `Warehouse #${row.warehouse_id}`}</span><small>{row.warehouse?.name}</small></div><b>{row.quantity} <small>{row.product?.unit}</small></b></article>) : <p>No stock balances yet.</p>}</div></section>
    <section className="warehouse-strip">{warehouses.map((warehouse) => <article key={warehouse.id}><span>{warehouse.code}</span><h3>{warehouse.name}</h3><p>{warehouse.address}</p></article>)}</section>
  </main>
}

function Heading({ label, title, note }: { label: string; title: string; note: string }) { return <div className="heading"><div><p className="kicker">{label}</p><h2>{title}</h2></div><span>{note}</span></div> }
function ProductTable({ products, categories }: { products: Product[]; categories: Category[] }) { const category = (id: number) => categories.find((item) => item.id === id)?.name ?? 'Unassigned'; return <div className="table-wrap"><table><thead><tr><th>SKU</th><th>Product</th><th>Category</th><th>Unit</th><th>Reorder level</th></tr></thead><tbody>{products.map((item) => <tr key={item.id}><td>{item.sku}</td><td><strong>{item.name}</strong>{item.description && <small>{item.description}</small>}</td><td>{category(item.category_id)}</td><td>{item.unit}</td><td>{item.reorder_level}</td></tr>)}</tbody></table></div> }

function ProductManager({ token, categories, products, refresh }: { token: string; categories: Category[]; products: Product[]; refresh: () => Promise<void> }) {
  const [draft, setDraft] = useState<ProductInput>(blank); const [editing, setEditing] = useState<number | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState('')
  const edit = (item: Product) => { setEditing(item.id); setDraft({ ...item }); setNotice('Editing selected product.') }
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setNotice(''); try { editing ? await api.updateProduct(token, editing, draft) : await api.createProduct(token, draft); setDraft(blank); setEditing(null); setNotice('Product saved.'); await refresh() } catch (cause) { setNotice(message(cause)) } finally { setBusy(false) } }
  async function remove() { if (!editing || !window.confirm('Delete this product?')) return; setBusy(true); try { await api.deleteProduct(token, editing); setDraft(blank); setEditing(null); setNotice('Product deleted.'); await refresh() } catch (cause) { setNotice(message(cause)) } finally { setBusy(false) } }
  return <section><Heading label="Admin control" title="Product register" note="Create, update, or remove" /><div className="manager"><div className="picker">{products.map((item) => <button type="button" key={item.id} className={editing === item.id ? 'selected' : ''} onClick={() => edit(item)}>{item.sku}<strong>{item.name}</strong></button>)}</div><form className="product-form" onSubmit={submit}><label>SKU<input value={draft.sku} onChange={(event) => setDraft({ ...draft, sku: event.target.value })} required /></label><label>Product name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required /></label><label>Category<select value={draft.category_id} onChange={(event) => setDraft({ ...draft, category_id: Number(event.target.value) })} required><option value={0} disabled>Select category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Unit<input value={draft.unit} onChange={(event) => setDraft({ ...draft, unit: event.target.value })} required /></label><label>Reorder level<input type="number" min="0" value={draft.reorder_level} onChange={(event) => setDraft({ ...draft, reorder_level: Number(event.target.value) })} required /></label><label className="wide">Description<textarea value={draft.description ?? ''} onChange={(event) => setDraft({ ...draft, description: event.target.value || null })} /></label><div className="actions"><button disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Create product'}</button>{editing && <><button type="button" className="quiet" onClick={() => { setEditing(null); setDraft(blank); setNotice('') }}>Cancel</button><button type="button" className="danger" onClick={remove} disabled={busy}>Delete</button></>}</div>{notice && <p className="message" role="status">{notice}</p>}</form></div></section>
}
