import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './products.css'
import './products-list-remediation.css'
import searchIcon from '../shared/assets/figma/search.svg'
import editIcon from '../shared/assets/figma/edit.svg'
import deleteIcon from '../shared/assets/figma/delete.svg'
import previousIcon from '../shared/assets/figma/product-previous.svg'
import nextIcon from '../shared/assets/figma/product-next.svg'
import { filterProducts } from '../shared/lib/products'
import { Badge } from '../shared/ui/Badge'
import { Button } from '../shared/ui/Button'
import { ConfirmDialog } from '../shared/ui/ConfirmDialog'
import { DataTable, type DataTableColumn } from '../shared/ui/DataTable'
import { EmptyState } from '../shared/ui/EmptyState'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import { Select } from '../shared/ui/Select'
import type { Category, Product, Supplier } from '../types'

const message = (error: unknown) => error instanceof ApiError ? error.message : 'Không thể kết nối đến máy chủ.'
const deleteMessage = (cause: unknown) => {
  if (cause instanceof ApiError) {
    if (cause.status === 403) return 'Bạn không có quyền xóa sản phẩm.'
    if (cause.status === 404) return 'Không tìm thấy sản phẩm. Vui lòng tải lại danh sách.'
    if (cause.status === 409) return 'Không thể xóa sản phẩm vì đang được tham chiếu trong dữ liệu tồn kho.'
  }
  return 'Không thể xóa sản phẩm. Vui lòng thử lại.'
}

export function ProductsPage() {
  const { logout, token, user } = useAuth()
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [productSupplierIds, setProductSupplierIds] = useState<number[]>([])
  const [productCategoryIds, setProductCategoryIds] = useState<number[]>([])
  const [filterOptionsLoading, setFilterOptionsLoading] = useState(true)
  const [filterOptionsError, setFilterOptionsError] = useState('')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [supplierId, setSupplierId] = useState<number | null>(null)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState(100)
  const [refresh, setRefresh] = useState(0)
  const [lookupError, setLookupError] = useState('')
  const [lookupRetry, setLookupRetry] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [removing, setRemoving] = useState<Product | null>(null)
  const [removeError, setRemoveError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token) return
    let active = true
    setLookupError('')
    void api.categories(token).then((result) => { if (active) setCategories(result.items) }).catch((cause) => { if (active) setLookupError(message(cause)) })
    if (token && (user?.role === 'admin' || user?.role === 'warehouse')) {
      void api.suppliers(token).then((result) => { if (active) setSuppliers(result.items) }).catch((cause) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() }
        else setLookupError('Không thể tải tên nhà cung cấp. Bạn vẫn có thể đọc và lọc sản phẩm theo mã nhà cung cấp.')
      })
    } else setSuppliers([])
    return () => { active = false }
  }, [logout, lookupRetry, token, user?.role])

  useEffect(() => {
    if (!token) return
    let active = true
    setFilterOptionsLoading(true)
    setFilterOptionsError('')
    // Lookup choices must not shrink with the current page or filtered rows.
    // Catalogue references work for roles without supplier-directory access.
    void api.productsAll(token).then((allProducts) => {
      if (!active) return
      setProductSupplierIds([...new Set(allProducts.flatMap((product) => product.supplier_id === null ? [] : [product.supplier_id]))])
      setProductCategoryIds([...new Set(allProducts.map((product) => product.category_id))])
    }).catch(() => {
      if (active) setFilterOptionsError('Không thể tải đầy đủ bộ lọc danh mục và nhà cung cấp. Vui lòng thử lại.')
    }).finally(() => { if (active) setFilterOptionsLoading(false) })
    return () => { active = false }
  }, [refresh, token])

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true); setError('')
    const filtered = search.trim() !== '' || categoryId !== null || supplierId !== null || status !== ''
    // Local combined filters evaluate every page, not just the first 100 records.
    const request = filtered ? api.productsAll(token).then((allProducts) => {
      const matching = filterProducts(allProducts, { categoryId, search }).filter((product) =>
        (supplierId === null || product.supplier_id === supplierId) &&
        (status === '' || product.is_active === (status === 'active')),
      )
      return { items: matching.slice((page - 1) * 100, page * 100), total: matching.length, page, page_size: 100 }
    }) : api.products(token, page)
    void request.then((result) => {
      if (!active) return
      const lastPage = Math.max(1, Math.ceil(result.total / result.page_size))
      if (page > lastPage) { setPage(lastPage); return }
      setProducts(result.items); setTotal(result.total); setPageSize(result.page_size)
    }).catch((cause) => { if (active) setError(message(cause)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [categoryId, page, refresh, search, status, supplierId, token])

  const remove = async () => { if (!token || !removing || busy) return; setBusy(true); setRemoveError(''); try { await api.deleteProduct(token, removing.id); setRemoving(null); setRefresh((value) => value + 1) } catch (cause) { if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() } else setRemoveError(deleteMessage(cause)) } finally { setBusy(false) } }
  const canWrite = user?.role === 'admin'
  const categoryName = (id: number) => categories.find((category) => category.id === id)?.name ?? `Danh mục #${id}`
  const supplierName = (id: number | null) => id === null ? 'Chưa có nhà cung cấp' : suppliers.find((supplier) => supplier.id === id)?.name ?? `Nhà cung cấp #${id}`
  const supplierIds = [...new Set([...suppliers.map((supplier) => supplier.id), ...productSupplierIds, ...(supplierId === null ? [] : [supplierId])])]
  const categoryIds = [...new Set([...categories.map((category) => category.id), ...productCategoryIds, ...(categoryId === null ? [] : [categoryId])])]
  const resetFilters = () => { setSearch(''); setCategoryId(null); setSupplierId(null); setStatus(''); setPage(1) }
  const columns: DataTableColumn<Product>[] = [
    { id: 'sku', header: 'SKU', render: (product) => <strong>{product.sku}</strong> },
    { id: 'name', header: 'Sản phẩm', render: (product) => <div className="products-table__name"><strong>{product.name}</strong>{product.description && <span>{product.description}</span>}</div> },
    { id: 'category', header: 'Danh mục', render: (product) => categoryName(product.category_id) },
    { id: 'supplier', header: 'Nhà cung cấp', render: (product) => supplierName(product.supplier_id) },
    { id: 'unit', header: 'Đơn vị', render: (product) => product.unit },
    { id: 'reorder', header: 'Mức tồn tối thiểu', render: (product) => product.reorder_level.toLocaleString('vi-VN') },
    { id: 'status', header: 'Trạng thái', render: (product) => <Badge variant={product.is_active ? 'success' : 'danger'}>{product.is_active ? 'Đang hoạt động' : 'Ngừng hoạt động'}</Badge> },
    { id: 'actions', header: <span className="visually-hidden">Thao tác</span>, render: (product) => canWrite ? <div className="products-table__actions">
      <Button aria-label={`Chỉnh sửa ${product.name}`} className="products-table__icon-action" onClick={() => navigate(`/products/${product.id}/edit`)} size="small" title={`Chỉnh sửa ${product.name}`} variant="secondary"><img alt="" src={editIcon} /></Button>
      <Button aria-label={`Xóa ${product.name}`} className="products-table__icon-action products-table__icon-action--danger" onClick={() => { setRemoveError(''); setRemoving(product) }} size="small" title={`Xóa ${product.name}`} variant="ghost"><img alt="" src={deleteIcon} /></Button>
    </div> : null },
  ]

  return <section className="products-page products-list-remediation">
    <PageHeader actions={canWrite ? <Button onClick={() => navigate('/products/new')}><span aria-hidden="true">+</span> Thêm sản phẩm</Button> : undefined} description="Quản lý danh mục sản phẩm và thông tin hàng hóa trong hệ thống." title="Sản phẩm" />
    {lookupError && <div><FeedbackMessage variant="warning">{lookupError}</FeedbackMessage><Button onClick={() => setLookupRetry(value => value + 1)} size="small" variant="secondary">Thử lại danh mục và nhà cung cấp</Button></div>}
    {filterOptionsError && <div><FeedbackMessage variant="warning">{filterOptionsError}</FeedbackMessage><Button onClick={() => setRefresh((value) => value + 1)} size="small" variant="secondary">Thử lại bộ lọc sản phẩm</Button></div>}
    <section aria-busy={loading} className="products-list-card">
      <div className="products-toolbar">
        <Input aria-label="Tìm kiếm sản phẩm" leadingIcon={<img alt="" src={searchIcon} />} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Tìm theo tên sản phẩm hoặc SKU..." value={search} />
        <Select aria-label="Lọc theo danh mục" aria-busy={filterOptionsLoading} onChange={(event) => { setCategoryId(event.target.value === '' ? null : Number(event.target.value)); setPage(1) }} options={categoryIds.map((id) => ({ label: categoryName(id), value: id }))} placeholder="Tất cả danh mục" value={categoryId ?? ''} />
        <Select aria-label="Lọc theo nhà cung cấp" aria-busy={filterOptionsLoading} disabled={filterOptionsLoading} onChange={(event) => { setSupplierId(event.target.value === '' ? null : Number(event.target.value)); setPage(1) }} options={supplierIds.map((id) => ({ label: supplierName(id), value: id }))} placeholder={filterOptionsLoading ? 'Đang tải nhà cung cấp...' : 'Tất cả nhà cung cấp'} value={supplierId ?? ''} />
        <Select aria-label="Lọc theo trạng thái" onChange={(event) => { setStatus(event.target.value); setPage(1) }} options={[{ label: 'Đang hoạt động', value: 'active' }, { label: 'Ngừng hoạt động', value: 'inactive' }]} placeholder="Tất cả trạng thái" value={status} />
        <Button onClick={resetFilters} variant="secondary">Đặt lại bộ lọc</Button>
      </div>
      {loading ? <FeedbackMessage>Đang tải danh sách sản phẩm...</FeedbackMessage> : error ? <div className="products-list-error"><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRefresh((value) => value + 1)} variant="secondary">Thử lại</Button></div> : <>
        {products.length === 0 ? <EmptyState description={search || categoryId !== null || supplierId !== null || status ? 'Không tìm thấy sản phẩm phù hợp với điều kiện lọc.' : 'Hãy thêm sản phẩm đầu tiên để bắt đầu quản lý hàng hóa.'} title={search || categoryId !== null || supplierId !== null || status ? 'Không có kết quả' : 'Chưa có sản phẩm'} /> : <DataTable columns={columns} getRowKey={(product) => product.id} rows={products} />}
        <div className="products-pagination"><span aria-live="polite">Hiển thị {total === 0 ? 0 : (page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} trong {total.toLocaleString('vi-VN')} sản phẩm</span><div><Button aria-label="Trang sản phẩm trước" className="ui-pagination-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} size="small" variant="secondary"><img alt="" src={previousIcon} /></Button><span>Trang {page}/{Math.max(1, Math.ceil(total / pageSize))}</span><Button aria-label="Trang sản phẩm tiếp theo" className="ui-pagination-button" disabled={page * pageSize >= total} onClick={() => setPage((value) => value + 1)} size="small" variant="secondary"><img alt="" src={nextIcon} /></Button></div></div>
      </>}
    </section>
    <ConfirmDialog busy={busy} cancelLabel="Hủy" confirmLabel={busy ? 'Đang xóa...' : 'Xóa sản phẩm'} confirmVariant="danger" description={`Sản phẩm “${removing?.name ?? ''}” sẽ bị xóa nếu chưa được tham chiếu trong tồn kho.`} onCancel={() => { if (!busy) { setRemoving(null); setRemoveError('') } }} onConfirm={() => void remove()} open={removing !== null} title="Xóa sản phẩm?">{removeError && <FeedbackMessage variant="error">{removeError}</FeedbackMessage>}</ConfirmDialog>
  </section>
}
