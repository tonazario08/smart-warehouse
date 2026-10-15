import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './movements.css'
import searchIcon from '../shared/assets/figma/search.svg'
import { buildMovementRows, filterMovementRows, type MovementType } from '../shared/lib/movements'
import { formatQuantity } from '../shared/lib/formatters'
import { Button } from '../shared/ui/Button'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import { Select } from '../shared/ui/Select'
import type { Product, Warehouse } from '../types'

const title = (type: MovementType) => type === 'inbound' ? 'Nhập kho' : 'Xuất kho'
const direction = (type: MovementType) => type === 'inbound' ? 'nhập' : 'xuất'
const errorMessage = (cause: unknown) => {
  if (!(cause instanceof ApiError)) return 'Không thể tải dữ liệu. Vui lòng thử lại sau.'
  if (cause.code !== 'UNEXPECTED_RESPONSE') return cause.message
  if (cause.status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
  if (cause.status === 404) return 'Không tìm thấy dữ liệu cần thiết.'
  if (cause.status === 400 || cause.status === 409) return 'Không thể hoàn tất giao dịch. Vui lòng kiểm tra kho, sản phẩm và số lượng tồn.'
  if (cause.status === 422) return 'Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.'
  return 'Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.'
}

export function MovementListPage({ type }: { type: MovementType }) {
  const { token, logout } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<ReturnType<typeof buildMovementRows>>([])
  const [products, setProducts] = useState<Product[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [search, setSearch] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [productId, setProductId] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [retry, setRetry] = useState(0)
  const pageSize = 5

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    setMessage('')
    void Promise.all([api.transactions(token), api.productsAll(token), api.warehouses(token)])
      .then(([transactions, productList, warehouseList]) => {
        if (!active) return
        setProducts(productList)
        setWarehouses(warehouseList)
        setRows(buildMovementRows({ transactions, products: productList, warehouses: warehouseList }))
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setMessage(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, retry, token])

  const filtered = useMemo(() => filterMovementRows(rows, { search, type }).filter(row =>
    (!warehouseId || row.warehouseId === Number(warehouseId)) &&
    (!productId || row.productId === Number(productId))), [rows, search, type, warehouseId, productId])
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const offset = (currentPage - 1) * pageSize
  const warehouseById = new Map(warehouses.map(warehouse => [warehouse.id, warehouse]))
  const resetFilters = () => { setSearch(''); setWarehouseId(''); setProductId(''); setPage(1) }
  useEffect(() => { setPage(1) }, [search, warehouseId, productId, type])

  const columns: DataTableColumn<(typeof rows)[number]>[] = [
    { id: 'id', header: 'ID giao dịch', render: row => <strong>{row.id}</strong> },
    { id: 'product', header: 'Sản phẩm', render: row => <div className="movement-product"><strong>{row.productName}</strong><span>{row.sku}</span></div> },
    { id: 'warehouse', header: 'Kho hàng', render: row => <div className="movement-product"><strong>{warehouseById.get(row.warehouseId)?.code}</strong><span>{row.warehouseName}</span></div> },
    { id: 'quantity', header: 'Số lượng', render: row => <span className={type === 'inbound' ? 'movement-value--inbound' : 'movement-value--outbound'}>{type === 'inbound' ? '+' : '−'}{formatQuantity(row.quantity, row.unit)}</span> },
  ]
  const hasFilters = Boolean(search || warehouseId || productId)

  return <section className="movements-page">
    <PageHeader title={title(type)} description={type === 'inbound' ? 'Theo dõi các phiếu nhập và biến động hàng vào kho.' : 'Theo dõi các phiếu xuất và biến động hàng ra khỏi kho.'} actions={<Button onClick={() => navigate('/' + type + '/new')}><span aria-hidden="true">+</span> Tạo phiếu {direction(type)}</Button>} />
    <section className="movement-card">
      <div className="movement-toolbar">
        <div className="movement-toolbar__filters">
          <Input aria-label="Tìm sản phẩm hoặc kho hàng" leadingIcon={<img alt="" src={searchIcon} />} value={search} onChange={event => setSearch(event.target.value)} placeholder="Tìm sản phẩm, kho hàng..." />
          <Select aria-label="Lọc theo kho hàng" placeholder="Tất cả kho hàng" value={warehouseId} onChange={event => setWarehouseId(event.target.value)} options={warehouses.map(item => ({ value: item.id, label: item.name }))} />
          <Select aria-label="Lọc theo sản phẩm" placeholder="Tất cả sản phẩm" value={productId} onChange={event => setProductId(event.target.value)} options={products.map(item => ({ value: item.id, label: item.name }))} />
        </div>
        <Button onClick={resetFilters} variant="secondary">Đặt lại bộ lọc</Button>
      </div>
      {message ? <><FeedbackMessage variant="error">{message}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button></> : loading ? <FeedbackMessage>Đang tải danh sách phiếu {direction(type)}...</FeedbackMessage> : filtered.length ? <>
        <DataTable columns={columns} rows={filtered.slice(offset, offset + pageSize)} getRowKey={row => row.id} />
        <div className="movement-pagination"><span>Hiển thị {offset + 1}–{Math.min(offset + pageSize, filtered.length)} trong {filtered.length} phiếu {direction(type)}</span><div>
          <Button aria-label="Trang trước" disabled={currentPage === 1} size="small" variant="secondary" onClick={() => setPage(currentPage - 1)}>Trước</Button>
          <Button aria-label="Trang sau" disabled={currentPage === pageCount} size="small" variant="secondary" onClick={() => setPage(currentPage + 1)}>Sau</Button>
        </div></div>
      </> : <EmptyState title={hasFilters ? 'Không tìm thấy phiếu phù hợp' : 'Chưa có phiếu ' + direction(type)} description={hasFilters ? 'Thử thay đổi hoặc đặt lại bộ lọc.' : type === 'inbound' ? 'Tạo phiếu nhập đầu tiên để ghi nhận hàng vào kho.' : 'Tạo phiếu xuất đầu tiên để ghi nhận hàng ra khỏi kho.'} />}
    </section>
  </section>
}

export function MovementFormPage({ type }: { type: MovementType }) {
  const { token, logout, user } = useAuth()
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [warehouseId, setWarehouseId] = useState('')
  const [productId, setProductId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [retry, setRetry] = useState(0)
  const [stock, setStock] = useState<{ warehouseId: string; productId: string; quantity: number } | null>(null)
  const [stockLoading, setStockLoading] = useState(false)
  const [stockError, setStockError] = useState('')
  const [stockRetry, setStockRetry] = useState(0)

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    setLoaded(false)
    setMessage('')
    void Promise.all([api.productsAll(token), api.warehouses(token)])
      .then(([productList, warehouseList]) => {
        if (!active) return
        setProducts(productList)
        setWarehouses(warehouseList)
        setLoaded(true)
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setMessage(errorMessage(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, retry, token])

  useEffect(() => {
    if (!token || !warehouseId || !productId) { setStock(null); setStockLoading(false); setStockError(''); return }
    let active = true
    setStockLoading(true)
    setStock(null)
    setStockError('')
    void api.stock(token)
      .then(stockRows => {
        if (!active) return
        const row = stockRows.find(item => item.warehouse_id === Number(warehouseId) && item.product_id === Number(productId))
        setStock({ warehouseId, productId, quantity: row?.quantity ?? 0 })
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setStockError('Không thể kiểm tra tồn kho. Vui lòng thử lại.')
      })
      .finally(() => { if (active) setStockLoading(false) })
    return () => { active = false }
  }, [logout, productId, stockRetry, token, warehouseId])

  const currentStock = stock?.warehouseId === warehouseId && stock?.productId === productId ? stock.quantity : null
  const amount = Number(quantity)
  const validAmount = quantity.trim() !== '' && Number.isSafeInteger(amount) && amount > 0 && amount <= 2_147_483_647
  const afterStock = currentStock !== null && validAmount ? currentStock + (type === 'inbound' ? amount : -amount) : null
  const selectedProduct = products.find(product => product.id === Number(productId))
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token || saving || !loaded) return
    if (!warehouseId || !productId || !validAmount) { setMessage('Vui lòng chọn kho, sản phẩm và nhập số lượng nguyên dương hợp lệ.'); return }
    if (reference.trim().length > 120) { setMessage('Mã phiếu không được vượt quá 120 ký tự.'); return }
    setSaving(true)
    setMessage('')
    try {
      const input = { warehouse_id: Number(warehouseId), product_id: Number(productId), quantity: amount, reference: reference.trim() || null, note: note.trim() || null }
      if (type === 'inbound') await api.createInbound(token, input)
      else await api.createOutbound(token, input)
      navigate('/' + type)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
      else setMessage(errorMessage(cause))
      setStockRetry(value => value + 1)
    } finally { setSaving(false) }
  }

  return <section className="movement-form-page">
    <PageHeader title={'Tạo phiếu ' + direction(type)} description={type === 'inbound' ? 'Ghi nhận hàng hóa nhập vào kho.' : 'Ghi nhận hàng hóa xuất khỏi kho.'} />
    {message && <FeedbackMessage variant="error">{message}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải dữ liệu biểu mẫu...</FeedbackMessage> : !loaded ? <Button onClick={() => setRetry(value => value + 1)}>Thử lại</Button> :
      <form className="ui-form-card" onSubmit={submit}>
        <fieldset className="ui-form-fields ui-form-section" disabled={saving}>
          <h2>Thông tin phiếu {direction(type)}</h2>
          <div className="ui-form-grid">
            <Input label="Mã phiếu" maxLength={120} value={reference} onChange={event => setReference(event.target.value)} placeholder="Nhập mã tham chiếu (không bắt buộc)" />
            <Select label="Kho hàng" placeholder="Chọn kho" required value={warehouseId} onChange={event => setWarehouseId(event.target.value)} options={warehouses.map(item => ({ value: item.id, label: item.name }))} />
          </div>
          <Select label="Sản phẩm" placeholder="Chọn sản phẩm" required value={productId} onChange={event => setProductId(event.target.value)} options={products.map(item => ({ value: item.id, label: item.sku + ' · ' + item.name }))} />
          <div className="ui-form-grid">
            <Input label="Số lượng" min="1" max={2_147_483_647} step="1" required type="number" value={quantity} onChange={event => setQuantity(event.target.value)} placeholder="Nhập số lượng" />
            <Input label="Tài khoản thực hiện" readOnly value={user?.email ?? ''} />
          </div>
          <Input label="Ghi chú" value={note} onChange={event => setNote(event.target.value)} placeholder="Nhập ghi chú (không bắt buộc)" />
        </fieldset>
        <div className="ui-form-actions"><Button disabled={saving} onClick={() => navigate('/' + type)} variant="secondary">Hủy</Button><Button isLoading={saving} type="submit">Xác nhận {type === 'inbound' ? 'nhập kho' : 'xuất kho'}</Button></div>
        <section className="movement-stock-impact" aria-live="polite">
          <h2>{type === 'inbound' ? 'Ảnh hưởng tồn kho' : 'Kiểm tra tồn kho'}</h2>
          {!warehouseId || !productId ? <p>Chọn kho và sản phẩm để xem ảnh hưởng tồn kho.</p> : stockLoading ? <p>Đang kiểm tra tồn kho...</p> : stockError ? <><FeedbackMessage variant="error">{stockError}</FeedbackMessage><Button onClick={() => setStockRetry(value => value + 1)} size="small" variant="secondary">Thử lại</Button></> : <dl>
            <div><dt>Tồn hiện tại</dt><dd>{currentStock === null ? '—' : formatQuantity(currentStock, selectedProduct?.unit)}</dd></div>
            <div><dt>Số lượng {direction(type)}</dt><dd className={type === 'inbound' ? 'movement-value--inbound' : 'movement-value--outbound'}>{validAmount ? (type === 'inbound' ? '+' : '−') + formatQuantity(amount, selectedProduct?.unit) : '—'}</dd></div>
            <div><dt>Sau khi {direction(type)}</dt><dd>{afterStock === null ? '—' : formatQuantity(afterStock, selectedProduct?.unit)}</dd></div>
          </dl>}
          {afterStock !== null && afterStock < 0 && <FeedbackMessage variant="warning">Số lượng xuất vượt tồn kho hiện tại. Vui lòng điều chỉnh số lượng.</FeedbackMessage>}
        </section>
      </form>}
  </section>
}
