import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import type { Product, Warehouse } from '../../types'
import { formatDateTime, formatQuantity } from '../../shared/lib/formatters'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { PageHeader } from '../../shared/ui/PageHeader'
import { getTransfer } from './api'
import type { Transfer } from './types'
import './transfers.css'

export function TransferDetailPage() {
  const { id = '' } = useParams(), { token, user } = useAuth()
  const [data, setData] = useState<Transfer | null>(null), [loading, setLoading] = useState(true)
  const [products, setProducts] = useState<Product[]>([]), [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [error, setError] = useState(''), [retry, setRetry] = useState(0)
  useEffect(() => {
    if (!token) return
    let active = true
    setData(null); setError(''); setLoading(true)
    if (!/^[1-9]\d*$/.test(id) || Number(id) > 2147483647) { setError('Mã phiếu chuyển kho không hợp lệ.'); setLoading(false); return }
    void Promise.all([getTransfer(token, Number(id)), api.productsAll(token), api.warehouses(token)])
      .then(([result, productRows, warehouseRows]) => { if (active) { setData(result); setProducts(productRows); setWarehouses(warehouseRows) } })
      .catch((cause: unknown) => { if (active && !(cause instanceof ApiError && cause.staleSession)) setError(cause instanceof ApiError && cause.status === 404 ? 'Không tìm thấy phiếu chuyển kho.' : cause instanceof ApiError ? cause.message : 'Không thể tải phiếu chuyển kho.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, token, user?.id, user?.role, retry])
  const product = products.find(row => row.id === data?.product_id)
  const name = (warehouseId: number) => warehouses.find(row => row.id === warehouseId)?.name ?? 'Kho #' + warehouseId
  return <section className="transfers-page">
    <PageHeader title="Chi tiết chuyển kho" description="Phiếu đã hoàn tất; số lượng dưới đây là lịch sử tại thời điểm giao dịch." />
    <Link to="/transfers">Về danh sách chuyển kho</Link>
    {loading ? <FeedbackMessage>Đang tải phiếu chuyển kho...</FeedbackMessage> : error ? <><FeedbackMessage variant="error">{error}</FeedbackMessage><Button onClick={() => setRetry(value => value + 1)}>Thử lại chi tiết</Button></> : data && <>
      <section className="transfer-panel"><h2>Phiếu chuyển #{data.id}</h2>
        <p className="transfer-completed">Đã hoàn tất</p>
        <dl className="transfer-facts">
          <div><dt>Sản phẩm</dt><dd>{product?.sku ?? '#' + data.product_id} · {product?.name ?? 'Sản phẩm #' + data.product_id}{product && !product.is_active && <span className="transfer-inactive">Ngừng hoạt động</span>}</dd></div>
          <div><dt>Kho nguồn → Kho đích</dt><dd>{name(data.source_warehouse_id)} → {name(data.destination_warehouse_id)}</dd></div>
          <div><dt>Số lượng chuyển</dt><dd>{formatQuantity(data.quantity, product?.unit)}</dd></div>
          <div><dt>Người thực hiện</dt><dd>Tài khoản #{data.created_by_id}</dd></div>
          <div><dt>Thời điểm hoàn tất</dt><dd>{formatDateTime(data.created_at)}</dd></div>
          <div><dt>Mã phiếu tham chiếu</dt><dd>{data.reference ?? 'Không có'}</dd></div>
          <div><dt>Ghi chú</dt><dd>{data.note ?? 'Không có'}</dd></div>
        </dl>
      </section>
      <section className="transfer-panel"><h2>Tồn kho tại thời điểm chuyển</h2><p>Đây là số lượng đã ghi nhận, không phải tồn kho hiện tại.</p>
        <DataTable rows={[
          { id: 'source', name: name(data.source_warehouse_id), before: data.source_quantity_before, after: data.source_quantity_after },
          { id: 'destination', name: name(data.destination_warehouse_id), before: data.destination_quantity_before, after: data.destination_quantity_after },
        ]} getRowKey={row => row.id} columns={[
          { id: 'warehouse', header: 'Kho hàng', render: row => row.name },
          { id: 'before', header: 'Trước khi chuyển', render: row => formatQuantity(row.before, product?.unit) },
          { id: 'after', header: 'Sau khi chuyển', render: row => formatQuantity(row.after, product?.unit) },
        ]} />
      </section>
      <section className="transfer-panel"><h2>Lịch sử liên kết</h2><p>Phiếu xuất #{data.outbound_id} · Giao dịch #{data.outbound_transaction_id}</p><p>Phiếu nhập #{data.inbound_id} · Giao dịch #{data.inbound_transaction_id}</p></section>
    </>}
  </section>
}
