import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { useAuth } from '../app/AuthProvider'
import './warehouses.css'
import { Button } from '../shared/ui/Button'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import { PageHeader } from '../shared/ui/PageHeader'
import type { WarehouseInput } from '../types'

type WarehouseFormPageProps = { mode: 'create' | 'edit' }
type FormValues = { code: string; name: string; address: string; latitude: string; longitude: string }
const emptyForm: FormValues = { code: '', name: '', address: '', latitude: '', longitude: '' }
const errorMessage = (cause: unknown) => {
  if (cause instanceof ApiError) {
    if (cause.status === 403) return 'Bạn không có quyền quản lý kho hàng.'
    if (cause.status === 404) return 'Không tìm thấy kho hàng.'
    if (cause.status === 409) return cause.message
    if (cause.status === 422) return cause.message
  }
  return 'Không thể tải hoặc lưu kho hàng. Vui lòng thử lại.'
}

function toInput(values: FormValues): WarehouseInput | null {
  const code = values.code.trim()
  const name = values.name.trim()
  const address = values.address.trim()
  const latitude = values.latitude.trim() === '' ? null : Number(values.latitude)
  const longitude = values.longitude.trim() === '' ? null : Number(values.longitude)
  if (!code || !name || !address || !Number.isFinite(latitude ?? 0) || !Number.isFinite(longitude ?? 0)) return null
  return { code, name, address, latitude, longitude }
}

export function WarehouseFormPage({ mode }: WarehouseFormPageProps) {
  const { id } = useParams()
  const warehouseId = Number(id)
  const { logout, token } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState<FormValues>(emptyForm)
  const [loading, setLoading] = useState(mode === 'edit')
  const [loaded, setLoaded] = useState(mode === 'create')
  const [retry, setRetry] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (mode === 'create') {
      setValues(emptyForm)
      setError('')
      setLoaded(true)
      setLoading(false)
      return
    }
    if (!token) return
    setLoading(true)
    setLoaded(false)
    setError('')
    if (!Number.isInteger(warehouseId) || warehouseId < 1) { setLoading(false); setError('Không tìm thấy kho hàng.'); return }
    let active = true
    void api.warehouse(token, warehouseId)
      .then((warehouse) => { if (active) { setLoaded(true); setValues({ code: warehouse.code, name: warehouse.name, address: warehouse.address, latitude: warehouse.latitude?.toString() ?? '', longitude: warehouse.longitude?.toString() ?? '' }) } })
      .catch((cause: unknown) => { if (active) { if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() } else setError(errorMessage(cause)) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [logout, mode, retry, token, warehouseId])

  const update = (field: keyof FormValues, value: string) => setValues((current) => ({ ...current, [field]: value }))
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token || saving || !loaded) return
    const input = toInput(values)
    if (!input) { setError('Vui lòng nhập mã, tên, địa chỉ và tọa độ hợp lệ.'); return }
    setSaving(true); setError('')
    try {
      const warehouse = mode === 'create' ? await api.createWarehouse(token, input) : await api.updateWarehouse(token, warehouseId, input)
      navigate(`/warehouses/${warehouse.id}`)
    } catch (cause) { if (cause instanceof ApiError && cause.status === 401) { if (!cause.staleSession) logout() } else setError(errorMessage(cause)) } finally { setSaving(false) }
  }

  const title = mode === 'create' ? 'Thêm kho hàng' : 'Chỉnh sửa kho hàng'
  return <section className="warehouse-form-page">
    <PageHeader description={mode === 'create' ? 'Nhập thông tin để tạo kho hàng mới.' : 'Cập nhật thông tin kho hàng hiện có.'} title={title} />
    {error && <FeedbackMessage variant="error">{error}</FeedbackMessage>}
    {loading ? <FeedbackMessage>Đang tải thông tin kho hàng...</FeedbackMessage> : !loaded ? <Button onClick={() => setRetry(current => current + 1)}>Thử lại</Button> :
      <form className="ui-form-card" onSubmit={(event) => void submit(event)}>
        <fieldset className="ui-form-fields ui-form-section" disabled={saving}>
          <h2>Thông tin kho hàng</h2>
          <div className="ui-form-grid"><Input label="Mã kho" onChange={(event) => update('code', event.target.value)} placeholder="Nhập mã kho" required value={values.code} /></div>
          <Input label="Tên kho" onChange={(event) => update('name', event.target.value)} placeholder="Nhập tên kho" required value={values.name} />
          <Input label="Địa chỉ" onChange={(event) => update('address', event.target.value)} placeholder="Nhập địa chỉ kho" required value={values.address} />
          <div className="ui-form-grid">
            <Input inputMode="decimal" label="Vĩ độ" onChange={(event) => update('latitude', event.target.value)} placeholder="Nhập vĩ độ" value={values.latitude} />
            <Input inputMode="decimal" label="Kinh độ" onChange={(event) => update('longitude', event.target.value)} placeholder="Nhập kinh độ" value={values.longitude} />
          </div>
        </fieldset>
        <div className="ui-form-actions"><Button disabled={saving} onClick={() => navigate('/warehouses')} variant="secondary">Hủy</Button><Button isLoading={saving} loadingLabel="Đang lưu..." type="submit">Lưu kho hàng</Button></div>
      </form>}
  </section>
}
