import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './products.css'
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
import type { Category, Product } from '../types'

const message = (error: unknown) => error instanceof ApiError ? error.message : 'Không thể kết nối đến máy chủ.'

export function ProductsPage() {
  const { token, user } = useAuth()
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [removing, setRemoving] = useState<Product | null>(null)
  const [busy, setBusy] = useState(false)

  const load = async () => { setLoading(true); setError(''); try { const [productPage, categoryPage] = await Promise.all([api.products(), api.categories()]); setProducts(productPage.items); setCategories(categoryPage.items) } catch (cause) { setError(message(cause)) } finally { setLoading(false) } }
  useEffect(() => { void load() }, [])
  const remove = async () => { if (!token || !removing) return; setBusy(true); try { await api.deleteProduct(token, removing.id); setRemoving(null); await load() } catch (cause) { setError(message(cause)) } finally { setBusy(false) } }
  const canWrite = user?.role === 'admin'
  const filteredProducts = filterProducts(products, { categoryId, search })
  const categoryName = (id: number) => categories.find((category) => category.id === id)?.name ?? 'Chưa phân loại'
  const columns: DataTableColumn<Product>[] = [
    { id: 'sku', header: 'SKU', render: (product) => product.sku },
    { id: 'name', header: 'Sản phẩm', render: (product) => <div className="products-table__name"><strong>{product.name}</strong>{product.description && <span>{product.description}</span>}</div> },
    { id: 'category', header: 'Danh mục', render: (product) => categoryName(product.category_id) },
    { id: 'unit', header: 'Đơn vị', render: (product) => product.unit },
    { id: 'reorder', header: 'Mức tồn tối thiểu', render: (product) => product.reorder_level.toLocaleString('vi-VN') },
    { id: 'status', header: 'Trạng thái', render: (product) => <Badge variant={product.is_active ? 'success' : 'neutral'}>{product.is_active ? 'Đang hoạt động' : 'Ngừng hoạt động'}</Badge> },
    { id: 'actions', header: <span className="visually-hidden">Thao tác</span>, render: (product) => canWrite ? <div className="products-table__actions"><Button aria-label={`Chỉnh sửa ${product.name}`} onClick={() => navigate(`/products/${product.id}/edit`)} size="small" variant="secondary">Sửa</Button><Button aria-label={`Xóa ${product.name}`} onClick={() => setRemoving(product)} size="small" variant="ghost">Xóa</Button></div> : null },
  ]

  return <section className="products-page">
    <PageHeader actions={canWrite ? <Button onClick={() => navigate('/products/new')}><span aria-hidden="true">+</span> Thêm sản phẩm</Button> : undefined} description="Quản lý danh mục sản phẩm và thông tin hàng hóa trong hệ thống." title="Sản phẩm" />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải danh sách sản phẩm...</FeedbackMessage> : <section className="products-list-card">
      <div className="products-toolbar"><Input aria-label="Tìm kiếm sản phẩm" onChange={(event) => setSearch(event.target.value)} placeholder="Tìm kiếm theo SKU, tên sản phẩm..." value={search} /><Select aria-label="Lọc theo danh mục" onChange={(event) => setCategoryId(event.target.value === '' ? null : Number(event.target.value))} options={categories.map((category) => ({ label: category.name, value: category.id }))} placeholder="Tất cả danh mục" value={categoryId ?? ''} /></div>
      {filteredProducts.length === 0 ? <EmptyState description={products.length === 0 ? 'Hãy thêm sản phẩm đầu tiên để bắt đầu quản lý hàng hóa.' : 'Không tìm thấy sản phẩm phù hợp với điều kiện lọc.'} title={products.length === 0 ? 'Chưa có sản phẩm' : 'Không có kết quả'} /> : <DataTable columns={columns} getRowKey={(product) => product.id} rows={filteredProducts} />}
    </section>}
    <ConfirmDialog cancelLabel="Hủy" confirmLabel={busy ? 'Đang xóa...' : 'Xóa sản phẩm'} confirmVariant="danger" description={`Sản phẩm “${removing?.name ?? ''}” sẽ bị xóa nếu chưa được tham chiếu trong tồn kho.`} onCancel={() => !busy && setRemoving(null)} onConfirm={() => void remove()} open={removing !== null} title="Xóa sản phẩm?" />
  </section>
}
