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
const message = (cause: unknown) => {
  if (cause instanceof ApiError) {
    if (cause.status === 403) return 'Bạn không có quyền quản lý sản phẩm.'
    if (cause.status === 404) return 'Không tìm thấy sản phẩm.'
    if (cause.status === 409) return 'Mã SKU đã tồn tại. Vui lòng chọn mã khác.'
    if (cause.status === 422) return 'Thông tin sản phẩm chưa hợp lệ. Vui lòng kiểm tra lại.'
  }
  return 'Không thể tải hoặc lưu sản phẩm. Vui lòng thử lại.'
}

export function ProductFormPage({ mode }: { mode: 'create' | 'edit' }) {
  const { id } = useParams()
  const { token, logout } = useAuth()
  const navigate = useNavigate()
  const [draft, setDraft] = useState<ProductInput>(blank)
  const [categories, setCategories] = useState<Category[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    setLoaded(false)
    setError('')
    setDraft(blank)
    if (mode === 'edit' && (!id || !Number.isInteger(Number(id)) || Number(id) < 1)) {
      setError('Không tìm thấy sản phẩm.')
      setLoading(false)
      return
    }
    void Promise.all([api.categories(), api.suppliers(token), mode === 'edit' ? api.product(Number(id)) : Promise.resolve(null)])
      .then(([categoryPage, supplierPage, product]) => {
        if (!active) return
        setCategories(categoryPage.items)
        setSuppliers(supplierPage.items)
        if (product) {
          const { id: productId, ...input } = product
          void productId
          setDraft(input)
        }
        setLoaded(true)
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 401) logout()
        else setError(message(cause))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, logout, mode, retry, token])

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token || busy || !loaded) return
    if (!draft.category_id || !draft.sku.trim() || !draft.name.trim() || !draft.unit.trim() || !Number.isInteger(draft.reorder_level) || draft.reorder_level < 0) {
      setError('Vui lòng nhập đầy đủ thông tin và mức tồn tối thiểu là số nguyên không âm.')
      return
    }
    setBusy(true)
    setError('')
    try {
      if (mode === 'create') await api.createProduct(token, draft)
      else await api.updateProduct(token, Number(id), draft)
      navigate('/products', { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) logout()
      else setError(message(cause))
    } finally { setBusy(false) }
  }
  const update = <K extends keyof ProductInput>(key: K, value: ProductInput[K]) => setDraft(current => ({ ...current, [key]: value }))
  const setNumber = (key: 'category_id' | 'supplier_id' | 'reorder_level', value: string) => update(key, value === '' ? (key === 'supplier_id' ? null : 0) : Number(value))
  // A product may reference a lookup record beyond the directory's first API page.
  const categoryOptions = categories.map(category => ({ label: category.name, value: category.id }))
  if (draft.category_id && !categories.some(category => category.id === draft.category_id)) categoryOptions.push({ label: `Danh mục #${draft.category_id}`, value: draft.category_id })
  const supplierOptions = suppliers.map(supplier => ({ label: supplier.name, value: supplier.id }))
  if (draft.supplier_id !== null && !suppliers.some(supplier => supplier.id === draft.supplier_id)) supplierOptions.push({ label: `Nhà cung cấp #${draft.supplier_id}`, value: draft.supplier_id })

  return <section className="products-page">
    <PageHeader title={mode === 'create' ? 'Thêm sản phẩm' : 'Chỉnh sửa sản phẩm'} description={mode === 'create' ? 'Nhập thông tin sản phẩm để thêm vào hệ thống.' : 'Cập nhật thông tin sản phẩm trong hệ thống.'} />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải thông tin sản phẩm...</FeedbackMessage> : !loaded ? <Button onClick={() => setRetry(current => current + 1)}>Thử lại</Button> :
      <form className="ui-form-card" onSubmit={submit}>
        <fieldset className="ui-form-fields ui-form-section" disabled={busy}>
          <h2>Thông tin cơ bản</h2>
          <div className="ui-form-grid">
            <Input label="SKU" placeholder="Nhập mã SKU" onChange={event => update('sku', event.target.value)} required value={draft.sku} />
            <div className="ui-field"><span className="ui-field__label" id="product-status-label">Trạng thái</span><div aria-labelledby="product-status-label" className="product-status-options" role="group">
              <Button aria-pressed={draft.is_active} onClick={() => update('is_active', true)} variant={draft.is_active ? 'primary' : 'secondary'}>Đang hoạt động</Button>
              <Button aria-pressed={!draft.is_active} onClick={() => update('is_active', false)} variant={!draft.is_active ? 'primary' : 'secondary'}>Ngừng hoạt động</Button>
            </div></div>
          </div>
          <Input label="Tên sản phẩm" placeholder="Nhập tên sản phẩm" onChange={event => update('name', event.target.value)} required value={draft.name} />
          <div className="ui-form-grid">
            <Select label="Danh mục" placeholder="Chọn danh mục" onChange={event => setNumber('category_id', event.target.value)} options={categoryOptions} required value={draft.category_id || ''} />
            <Select label="Nhà cung cấp" placeholder="Chọn nhà cung cấp" onChange={event => setNumber('supplier_id', event.target.value)} options={supplierOptions} value={draft.supplier_id ?? ''} />
          </div>
          <div className="ui-form-grid">
            <Input label="Đơn vị tính" placeholder="Ví dụ: cái, hộp, cuộn" onChange={event => update('unit', event.target.value)} required value={draft.unit} />
            <Input label="Mức tồn tối thiểu" min="0" step="1" onChange={event => setNumber('reorder_level', event.target.value)} required type="number" value={draft.reorder_level} />
          </div>
          <label className="product-description"><span className="ui-field__label">Mô tả</span><textarea className="ui-input" onChange={event => update('description', event.target.value || null)} value={draft.description ?? ''} /></label>
        </fieldset>
        <div className="ui-form-actions"><Button disabled={busy} onClick={() => navigate('/products')} variant="secondary">Hủy</Button><Button isLoading={busy} type="submit">{mode === 'create' ? 'Lưu sản phẩm' : 'Lưu thay đổi'}</Button></div>
      </form>}
  </section>
}
