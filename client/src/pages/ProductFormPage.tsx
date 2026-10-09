import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './products.css'
import { Button } from '../shared/ui/Button'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import { Select } from '../shared/ui/Select'
import type { Category, ProductInput, Supplier } from '../types'

const blank: ProductInput = { sku: '', name: '', description: null, category_id: 0, supplier_id: null, unit: '', reorder_level: 0, is_active: true }
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Không thể kết nối đến máy chủ.'

export function ProductFormPage({ mode }: { mode: 'create' | 'edit' }) {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [draft, setDraft] = useState<ProductInput>(blank)
  const [categories, setCategories] = useState<Category[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { if (!token) return; let active = true; void Promise.all([api.categories(), api.suppliers(token), mode === 'edit' && id ? api.product(Number(id)) : Promise.resolve(null)]).then(([categoryPage, supplierPage, product]) => { if (!active) return; setCategories(categoryPage.items); setSuppliers(supplierPage.items); if (product) setDraft(product) }).catch((cause) => { if (active) setError(message(cause)) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [id, mode, token])
  const submit = async (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!token) return; if (!draft.category_id) { setError('Vui lòng chọn danh mục sản phẩm.'); return } setBusy(true); setError(''); try { if (mode === 'create') await api.createProduct(token, draft); else await api.updateProduct(token, Number(id), draft); navigate('/products', { replace: true }) } catch (cause) { setError(message(cause)) } finally { setBusy(false) } }
  const setNumber = (key: 'category_id' | 'supplier_id' | 'reorder_level', value: string) => setDraft((current) => ({ ...current, [key]: value === '' ? (key === 'supplier_id' ? null : 0) : Number(value) }))

  const title = mode === 'create' ? 'Thêm sản phẩm' : 'Chỉnh sửa sản phẩm'
  const description = mode === 'create' ? 'Tạo mới sản phẩm để bắt đầu quản lý hàng hóa trong hệ thống.' : 'Cập nhật thông tin sản phẩm trong hệ thống.'
  if (loading) return <FeedbackMessage>Đang tải thông tin sản phẩm...</FeedbackMessage>
  return <section className="products-page"><PageHeader description={description} title={title} />{error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}<form className="product-form-card" onSubmit={submit}>
    <section className="product-form-card__section"><h2>Thông tin cơ bản</h2><div className="product-form-card__grid"><Input label="SKU" onChange={(event) => setDraft({ ...draft, sku: event.target.value })} required value={draft.sku} /><div className="ui-field"><span className="ui-field__label">Trạng thái</span><div className="product-status-options"><Button aria-pressed={draft.is_active} onClick={() => setDraft({ ...draft, is_active: true })} size="small" type="button" variant={draft.is_active ? 'primary' : 'secondary'}>Đang hoạt động</Button><Button aria-pressed={!draft.is_active} onClick={() => setDraft({ ...draft, is_active: false })} size="small" type="button" variant={!draft.is_active ? 'primary' : 'secondary'}>Ngừng hoạt động</Button></div></div></div><Input label="Tên sản phẩm" onChange={(event) => setDraft({ ...draft, name: event.target.value })} required value={draft.name} /><div className="product-form-card__grid"><Select label="Danh mục" onChange={(event) => setNumber('category_id', event.target.value)} options={categories.map((category) => ({ label: category.name, value: category.id }))} required value={draft.category_id || ''} /><Select label="Nhà cung cấp" onChange={(event) => setNumber('supplier_id', event.target.value)} options={suppliers.map((supplier) => ({ label: supplier.name, value: supplier.id }))} placeholder="Chưa chọn nhà cung cấp" value={draft.supplier_id ?? ''} /></div><div className="product-form-card__grid"><Input label="Đơn vị tính" onChange={(event) => setDraft({ ...draft, unit: event.target.value })} required value={draft.unit} /><Input label="Mức tồn tối thiểu" min="0" onChange={(event) => setNumber('reorder_level', event.target.value)} required type="number" value={draft.reorder_level} /></div><label className="product-description"><span>Mô tả</span><textarea onChange={(event) => setDraft({ ...draft, description: event.target.value || null })} value={draft.description ?? ''} /></label></section><div className="product-form-card__actions"><Button onClick={() => navigate('/products')} type="button" variant="secondary">Hủy</Button><Button isLoading={busy} type="submit">{mode === 'create' ? 'Tạo sản phẩm' : 'Lưu thay đổi'}</Button></div>
  </form></section>
}
