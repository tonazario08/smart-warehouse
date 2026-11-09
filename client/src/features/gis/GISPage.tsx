import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api'
import { useAuth } from '../../app/AuthProvider'
import { formatNumber, formatQuantity } from '../../shared/lib/formatters'
import { can } from '../../shared/lib/permissions'
import { Button } from '../../shared/ui/Button'
import { DataTable } from '../../shared/ui/DataTable'
import { EmptyState } from '../../shared/ui/EmptyState'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { Input } from '../../shared/ui/Input'
import { PageHeader } from '../../shared/ui/PageHeader'
import { Select } from '../../shared/ui/Select'
import {
  getGisChoices, getGisHeatmap, getGisPolicy, getGisRoute, getGisStatus,
  getWarehouseOptions, gisError, gisReason,
} from './api'
import { HeatmapMap, RouteMap } from './GisMap'
import type {
  Coordinate, Destination, Exclusion, Heatmap, Place, RouteRead,
  SnapshotMetadata, WarehouseOptions, WarehouseRead,
} from './types'
import '../../shared/styles/management.css'
import './gis.css'

const MAX_QUANTITY = 2_147_483_647
const destinationModes = [
  { value: 'coordinate', label: 'Tọa độ' },
  { value: 'warehouse', label: 'Kho hàng' },
  { value: 'purchase_request', label: 'Yêu cầu mua hàng' },
]
const exclusionLabels: Record<Exclusion, string> = {
  transfer_in: 'Chân nhập chuyển kho',
  transfer_out: 'Chân xuất chuyển kho',
  standard_outbound: 'Xuất kho thông thường',
  unclassified_outbound: 'Xuất chưa phân loại',
}

type RequestState<InputType, Result> = { scope: object; input: InputType } & (
  | { phase: 'loading' }
  | { phase: 'success'; data: Result }
  | { phase: 'error'; message: string; retryable: boolean }
)

function useGisAction<InputType, Result>(
  token: string,
  scope: object,
  load: (token: string, input: InputType, signal: AbortSignal) => Promise<Result>,
) {
  const active = useRef<AbortController | null>(null)
  const [result, setResult] = useState<RequestState<InputType, Result> | null>(null)

  useEffect(() => () => active.current?.abort(), [scope])

  const clear = useCallback(() => {
    active.current?.abort()
    active.current = null
    setResult(null)
  }, [])

  const run = useCallback((input: InputType) => {
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    setResult({ scope, input, phase: 'loading' })
    void load(token, input, controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ scope, input, phase: 'success', data })
    }).catch((cause: unknown) => {
      if (controller.signal.aborted || (cause instanceof ApiError && cause.staleSession)) return
      const retryable = !(cause instanceof ApiError && (cause.status === 401 || cause.status === 403))
      setResult({ scope, input, phase: 'error', message: gisError(cause), retryable })
    })
  }, [load, scope, token])

  const current = result?.scope === scope ? result : null
  return {
    current,
    data: current?.phase === 'success' ? current.data : null,
    loading: current?.phase === 'loading',
    error: current?.phase === 'error' ? current : null,
    run,
    clear,
  }
}

function Problem({ message, label, retry }: { message: string; label: string; retry?: () => void }) {
  return <div className="gis-problem">
    <FeedbackMessage variant="error">{message}</FeedbackMessage>
    {retry && <Button variant="secondary" onClick={retry}>{label}</Button>}
  </div>
}

function positiveInteger(value: string) {
  const parsed = /^[0-9]{1,10}$/.test(value) ? Number(value) : 0
  return parsed >= 1 && parsed <= MAX_QUANTITY ? parsed : null
}

function distance(value: number) {
  return value >= 1_000_000
    ? `${formatNumber(value / 1_000_000, 3)} km`
    : `${formatNumber(value / 1_000, 2)} m`
}

function utcStamp(value: string) {
  return value.replace('T', ' ').replace(/(?:Z|\+00:00)$/, ' UTC')
}

function pointText(point: Coordinate | null) {
  return point === null ? 'Chưa có vị trí' : `${point.latitude}, ${point.longitude}`
}

function warehouseName(warehouse: WarehouseRead) {
  return <><strong>{warehouse.name}</strong><small>{warehouse.code}</small></>
}

function placeText(place: Place) {
  return place.warehouse ? place.warehouse.name : pointText(place.coordinate)
}

function vietnamDate(offset: number) {
  const date = new Date(Date.now() + offset * 86_400_000)
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date)
}

function SnapshotInfo({ snapshot }: { snapshot: SnapshotMetadata }) {
  const [west, south, east, north] = snapshot.bounds
  return <dl className="gis-source__facts">
    <div><dt>Nguồn đường</dt><dd>{snapshot.dataset_class === 'public_osm'
      ? 'Đường công cộng OpenStreetMap' : 'Mạng đường kiểm thử'}</dd></div>
    <div><dt>Thời điểm bản chụp</dt><dd>{utcStamp(snapshot.snapshot_at)}</dd></div>
    <div><dt>Vùng phủ WGS84</dt><dd>{west}, {south} đến {east}, {north}</dd></div>
    <div><dt>Phiên bản bản chụp</dt><dd><code>{snapshot.snapshot_id}</code></dd></div>
    <div><dt>Giấy phép</dt><dd>{snapshot.dataset_class === 'public_osm' ? snapshot.license : 'Dữ liệu kiểm thử'}
      {snapshot.source_url && <> · <a href={snapshot.source_url} target="_blank" rel="noreferrer">Nguồn Geofabrik</a></>}
    </dd></div>
  </dl>
}

function RouteEvidence({ route }: { route: RouteRead }) {
  return <>
    {route.transfer && <FeedbackMessage>
      Chuyển kho tức thời. Sơ đồ là tuyến tham khảo cho phiếu {route.transfer.transfer_id}.
    </FeedbackMessage>}
    {route.reason && <FeedbackMessage variant="warning">{gisReason(route.reason)}</FeedbackMessage>}
    <figure className="gis-figure">
      <RouteMap route={route} />
      <figcaption>
        {route.geometry && <span className="gis-route-key">
          <strong>Tuyến ô tô tham khảo</strong>
          {route.geometry.type === 'LineString' ? <span>Nét liền là đường đi</span> : <span>Hai điểm cùng nút đường</span>}
          {(route.origin_snap?.connector || route.destination_snap?.connector) && <span>Nét đứt là đoạn nối đến đường</span>}
        </span>}
        {route.snapshot?.attribution && (route.snapshot.license_url
          ? <a href={route.snapshot.license_url} target="_blank" rel="noreferrer">{route.snapshot.attribution}</a>
          : <span>{route.snapshot.attribution}</span>)}
      </figcaption>
    </figure>
    <dl className="gis-route-facts">
      <div><dt>Điểm đi</dt><dd>{placeText(route.origin)}</dd></div>
      <div><dt>Điểm đến</dt><dd>{placeText(route.destination)}</dd></div>
      {route.destination.request_id !== null && <div><dt>Yêu cầu mua hàng</dt><dd>{route.destination.request_id}</dd></div>}
      {route.distance_mm !== null && <div><dt>Chiều dài đường</dt><dd><strong>{distance(route.distance_mm)}</strong></dd></div>}
      {route.origin_snap && <div><dt>Đoạn nối tại điểm đi</dt><dd>{distance(route.origin_snap.distance_mm)}</dd></div>}
      {route.destination_snap && <div><dt>Đoạn nối tại điểm đến</dt><dd>{distance(route.destination_snap.distance_mm)}</dd></div>}
      {route.snapshot && <div><dt>Phiên bản tuyến</dt><dd><code>{route.snapshot.snapshot_id}</code></dd></div>}
    </dl>
  </>
}

function WarehouseResults({ result, selected, select }: {
  result: WarehouseOptions; selected: number | null; select: (id: number) => void;
}) {
  const unit = result.product.unit
  return <>
    <p className="gis-muted">Tồn ghi nhận lúc {utcStamp(result.stock_as_of)}. Số liệu dùng để tham khảo khi chọn kho.</p>
    {result.ranking_state === 'budget_exceeded' && <FeedbackMessage variant="warning">{gisReason('budget_exceeded')}</FeedbackMessage>}
    {result.ranked.length > 0 ? <ol className="gis-warehouse-list" aria-label="Xếp hạng kho theo chiều dài đường">
      {result.ranked.map(row => <li key={row.warehouse.warehouse_id}>
        <div>{warehouseName(row.warehouse)}
          <span>Tồn {formatQuantity(row.available_quantity, unit)}</span>
        </div>
        <div><strong>{distance(row.distance_mm)}</strong>
          <Button
            variant="secondary" size="small"
            aria-label={`Xem tuyến từ ${row.warehouse.name}`}
            aria-pressed={selected === row.warehouse.warehouse_id}
            onClick={() => select(row.warehouse.warehouse_id)}
          >Xem tuyến</Button>
        </div>
      </li>)}
    </ol> : <EmptyState
      title="Chưa có kho đủ tồn với tuyến đường"
      description="Xem khoảng cách địa lý hoặc lý do loại ở bên dưới."
    />}
    {result.geographic_only.length > 0 && <section className="gis-results-group" aria-label="Khoảng cách địa lý">
      <h3>Khoảng cách địa lý</h3>
      <p className="gis-muted">Khoảng cách thẳng giữa hai tọa độ.</p>
      <ul className="gis-warehouse-list">
        {result.geographic_only.map(row => <li key={row.warehouse.warehouse_id}>
          <div>{warehouseName(row.warehouse)}<small>{gisReason(row.reason)}</small></div>
          <div><strong>{distance(row.distance_mm)}</strong><span>Tồn {formatQuantity(row.available_quantity, unit)}</span></div>
        </li>)}
      </ul>
    </section>}
    {result.excluded.length > 0 && <details className="gis-excluded">
      <summary>Kho chưa đủ điều kiện ({result.excluded.length})</summary>
      <ul className="gis-warehouse-list">
        {result.excluded.map(row => <li key={row.warehouse.warehouse_id}>
          <div>{warehouseName(row.warehouse)}<small>{gisReason(row.reason)}</small></div>
          {row.available_quantity !== null && <span>Tồn {formatQuantity(row.available_quantity, unit)}</span>}
        </li>)}
      </ul>
    </details>}
  </>
}

function HeatmapResults({ data }: { data: Heatmap }) {
  const rows = [...data.points, ...data.unlocated]
  const unit = data.product.unit
  const total = rows.reduce((quantity, row) => quantity + row.fulfilled_quantity, 0)
  return <>
    <p className="gis-muted">
      {data.product.sku} · {data.timezone} · {data.start_date} đến đầu ngày {data.end_date}.
    </p>
    <p className="gis-muted">Biên truy vấn {utcStamp(data.start_utc)} đến {utcStamp(data.end_utc)}. Đọc lúc {utcStamp(data.queried_at)}.</p>
    {total === 0 && <FeedbackMessage>Chưa ghi nhận lượng xuất đáp ứng yêu cầu mua hàng trong kỳ.</FeedbackMessage>}
    <div className="gis-heat-results">
      <div className="gis-heat-viewport"><HeatmapMap points={data.points} unit={unit} /></div>
      <div className="gis-table-scroll" role="region" aria-label="Cuộn bảng lượng xuất theo kho" tabIndex={0}>
        <DataTable rows={rows} getRowKey={row => row.warehouse.warehouse_id} caption="Lượng xuất theo kho"
          emptyMessage="Chưa có kho hàng để hiển thị." columns={[
            { id: 'warehouse', header: 'Kho', render: row => warehouseName(row.warehouse) },
            { id: 'quantity', header: 'Lượng xuất', render: row => formatQuantity(row.fulfilled_quantity, unit) },
            { id: 'count', header: 'Giao dịch', render: row => formatNumber(row.transaction_count) },
            { id: 'position', header: 'Vị trí', render: row => {
              const { latitude, longitude } = row.warehouse
              return pointText(latitude === null || longitude === null ? null : { latitude, longitude })
            } },
          ]} />
      </div>
    </div>
    <dl className="gis-heat-exclusions" aria-label="Nghiệp vụ tách khỏi lượng xuất">
      {(Object.keys(exclusionLabels) as Exclusion[]).map(key => <div key={key}>
        <dt>{exclusionLabels[key]}</dt>
        <dd>{formatQuantity(data.excluded[key].quantity, unit)} · {formatNumber(data.excluded[key].transaction_count)} giao dịch</dd>
      </div>)}
    </dl>
  </>
}

function GISWorkspace({ token, mayRoute }: { token: string; mayRoute: boolean }) {
  const scope = useMemo(() => ({}), [token])
  const status = useGisAction(token, scope, getGisStatus)
  const choices = useGisAction(token, scope, getGisChoices)
  const options = useGisAction(token, scope, getWarehouseOptions)
  const route = useGisAction(token, scope, getGisRoute)
  const heatmap = useGisAction(token, scope, getGisHeatmap)
  const policy = useGisAction(token, scope, getGisPolicy)
  const loadStatus = status.run
  const loadChoices = choices.run
  useEffect(() => { loadStatus(undefined); loadChoices(undefined) }, [loadStatus, loadChoices])

  const [mode, setMode] = useState<'stock' | 'transfer'>('stock')
  const [product, setProduct] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [destinationKind, setDestinationKind] = useState<Destination['kind']>('coordinate')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [destinationWarehouse, setDestinationWarehouse] = useState('')
  const [purchaseId, setPurchaseId] = useState('')
  const [transferId, setTransferId] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [startDate, setStartDate] = useState(() => vietnamDate(-7))
  const [endDate, setEndDate] = useState(() => vietnamDate(0))
  const [runId, setRunId] = useState('')
  const [formError, setFormError] = useState('')
  const [heatError, setHeatError] = useState('')
  const [policyError, setPolicyError] = useState('')

  function clearRoute() {
    setSelected(null)
    setPolicyError('')
    route.clear()
    policy.clear()
  }

  function clearOptions() {
    setFormError('')
    options.clear()
    clearRoute()
  }

  function readDestination(): Destination | null {
    if (destinationKind === 'warehouse') {
      const id = positiveInteger(destinationWarehouse)
      return id === null ? null : { kind: 'warehouse', warehouse_id: id }
    }
    if (destinationKind === 'purchase_request') {
      const id = positiveInteger(purchaseId)
      return id === null ? null : { kind: 'purchase_request', request_id: id }
    }
    if (!latitude.trim() || !longitude.trim()) return null
    const lat = Number(latitude), lon = Number(longitude)
    return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180
      ? { kind: 'coordinate', latitude: lat, longitude: lon } : null
  }

  function submitOptions(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    clearRoute()
    const destination = readDestination()
    const product_id = positiveInteger(product)
    const amount = positiveInteger(quantity)
    if (!product_id || !amount || !destination) {
      setFormError('Chọn SKU, số lượng dương và điểm đến hợp lệ.')
      return
    }
    setFormError('')
    options.run({ product_id, quantity: amount, destination })
  }

  function selectWarehouse(warehouse_id: number) {
    if (options.current?.phase !== 'success') return
    setSelected(warehouse_id)
    setPolicyError('')
    policy.clear()
    route.run({ kind: 'warehouse_to_target', warehouse_id, destination: options.current.input.destination })
  }

  function submitTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = positiveInteger(transferId)
    if (!id) {
      setFormError('Nhập ID phiếu chuyển kho là số nguyên dương.')
      return
    }
    setFormError('')
    route.run({ kind: 'transfer', transfer_id: id })
  }

  function submitHeatmap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const product_id = positiveInteger(product)
    const duration = (Date.parse(endDate) - Date.parse(startDate)) / 86_400_000
    if (!product_id || !Number.isFinite(duration) || duration < 1 || duration > 90) {
      setHeatError('Chọn SKU và kỳ từ 1 đến 90 ngày.')
      return
    }
    setHeatError('')
    heatmap.run({ product_id, start_date: startDate, end_date: endDate })
  }

  function submitPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const product_id = positiveInteger(product)
    const id = runId.trim()
    if (!product_id || !selected || !/^rrv1-[0-9a-f]{64}$/.test(id)) {
      setPolicyError('Nhập mã kết quả bổ sung hàng hợp lệ.')
      return
    }
    setPolicyError('')
    policy.run({ product_id, warehouse_id: selected, run_id: id })
  }

  const stockLabel = status.data?.stock_fixture_label ?? options.data?.stock_fixture_label
    ?? route.data?.stock_fixture_label ?? heatmap.data?.stock_fixture_label
  const selectedProduct = choices.data?.products.find(item => String(item.id) === product)
  return <section className="gis-page management-workspace">
    <PageHeader title="Bản đồ kho" description="Tìm kho đủ tồn, xem đường đi và đối chiếu lượng xuất theo vị trí kho." />
    <section className="gis-source" aria-label="Dữ liệu đường và tồn kho">
      {status.error ? <Problem message={status.error.message} label="Thử lại dữ liệu đường"
        retry={status.error.retryable ? () => status.run(undefined) : undefined} />
        : !status.data ? <FeedbackMessage>Đang tải dữ liệu đường…</FeedbackMessage>
        : <>
          {status.data.state !== 'available' && <FeedbackMessage variant="warning">{gisReason(`snapshot_${status.data.state}`)}</FeedbackMessage>}
          {status.data.snapshot && <SnapshotInfo snapshot={status.data.snapshot} />}
        </>}
      {stockLabel && <span className="gis-fixture-label">{stockLabel}</span>}
    </section>

    <section className="management-panel gis-controls" aria-labelledby="gis-controls">
      <div className="gis-section-heading">
        <h2 id="gis-controls">Điều kiện tra cứu</h2>
        {mayRoute && <div className="gis-mode" role="group" aria-label="Kiểu tra cứu">
          <Button size="small" variant={mode === 'stock' ? 'primary' : 'secondary'} aria-pressed={mode === 'stock'}
            onClick={() => { if (mode !== 'stock') { setMode('stock'); clearOptions() } }}>Tìm theo tồn kho</Button>
          <Button size="small" variant={mode === 'transfer' ? 'primary' : 'secondary'} aria-pressed={mode === 'transfer'}
            onClick={() => { if (mode !== 'transfer') { setMode('transfer'); clearOptions() } }}>Tra phiếu chuyển kho</Button>
        </div>}
      </div>
      {choices.error ? <Problem message={choices.error.message} label="Thử lại danh sách sản phẩm và kho"
        retry={choices.error.retryable ? () => choices.run(undefined) : undefined} />
        : !choices.data ? <FeedbackMessage>Đang tải sản phẩm và kho…</FeedbackMessage>
        : choices.data.products.length === 0 && <FeedbackMessage variant="warning">Chưa có sản phẩm đang hoạt động.</FeedbackMessage>}
      <Select label="Sản phẩm (SKU)" placeholder="Chọn sản phẩm" value={product} disabled={!choices.data?.products.length}
        options={choices.data?.products.map(item => ({ value: item.id, label: item.sku + ' · ' + item.name })) ?? []}
        onChange={event => { setProduct(event.target.value); clearOptions(); heatmap.clear(); setHeatError('') }} />

      {mayRoute && (mode === 'stock' ? <form className="gis-form" onSubmit={submitOptions}>
        <div className="gis-fields">
          <Input label="Số lượng cần" type="number" min="1" max={MAX_QUANTITY} step="1" value={quantity} required
            onChange={event => { setQuantity(event.target.value); clearOptions() }} />
          <Select label="Loại điểm đến" placeholder="Chọn loại điểm đến" value={destinationKind} options={destinationModes} required
            onChange={event => { setDestinationKind(event.target.value as Destination['kind']); clearOptions() }} />
          {destinationKind === 'coordinate' && <>
            <Input label="Vĩ độ" type="number" step="any" min="-90" max="90" value={latitude} required
              onChange={event => { setLatitude(event.target.value); clearOptions() }} />
            <Input label="Kinh độ" type="number" step="any" min="-180" max="180" value={longitude} required
              onChange={event => { setLongitude(event.target.value); clearOptions() }} />
          </>}
          {destinationKind === 'warehouse' && <Select label="Kho đích" value={destinationWarehouse} required
            options={choices.data?.warehouses.map(warehouse => ({ value: warehouse.id, label: warehouse.code + ' · ' + warehouse.name })) ?? []}
            onChange={event => { setDestinationWarehouse(event.target.value); clearOptions() }} />}
          {destinationKind === 'purchase_request' && <Input label="ID yêu cầu mua hàng" type="number" min="1" max={MAX_QUANTITY}
            step="1" value={purchaseId} required onChange={event => { setPurchaseId(event.target.value); clearOptions() }} />}
        </div>
        <Button type="submit" disabled={options.loading || !choices.data?.products.length}>Tìm kho đủ tồn</Button>
      </form> : <form className="gis-form" onSubmit={submitTransfer}>
        <Input label="ID phiếu chuyển kho" type="number" min="1" max={MAX_QUANTITY} step="1" value={transferId} required
          onChange={event => { setTransferId(event.target.value); setFormError(''); clearRoute() }} />
        <Button type="submit" disabled={route.loading}>Xem tuyến chuyển kho</Button>
      </form>)}
      {formError && <FeedbackMessage variant="error">{formError}</FeedbackMessage>}
    </section>

    {mayRoute && <div className="gis-route-layout">
      <section className="management-panel gis-panel" aria-label="Kết quả kho">
        <h2>Kết quả kho</h2>
        {mode === 'transfer' ? <EmptyState title="Đang tra theo phiếu chuyển kho" description="Thông tin tuyến nằm ở khung bên cạnh." />
          : options.loading ? <FeedbackMessage>Đang tìm kho đủ tồn…</FeedbackMessage>
          : options.error ? <Problem message={options.error.message} label="Thử lại tìm kho"
            retry={options.error.retryable ? () => options.run(options.error!.input) : undefined} />
          : options.data ? <WarehouseResults result={options.data} selected={selected} select={selectWarehouse} />
          : <EmptyState title="Chưa có kết quả kho" description="Chọn SKU và điểm đến để xem các kho đủ tồn." />}
      </section>

      <section className="management-panel gis-panel gis-route-viewport" aria-label="Tuyến đường">
        <h2>Tuyến đường</h2>
        <p className="visually-hidden" role="status">{route.data?.geometry ? 'Đã hiển thị tuyến đường.' : ''}</p>
        {route.loading ? <FeedbackMessage>Đang tính tuyến đường…</FeedbackMessage>
          : route.error ? <Problem message={route.error.message} label="Thử lại tính tuyến"
            retry={route.error.retryable ? () => route.run(route.error!.input) : undefined} />
          : route.data ? <RouteEvidence route={route.data} />
          : <EmptyState title="Chưa chọn tuyến" description="Chọn một kho có tuyến hoặc tra ID phiếu chuyển kho." />}
        {selected !== null && <details className="gis-policy">
          <summary>Tham khảo bổ sung hàng</summary>
          <form className="gis-form" onSubmit={submitPolicy}>
            <Input label="Mã kết quả bổ sung hàng" value={runId} maxLength={69} required
              onChange={event => { setRunId(event.target.value); setPolicyError(''); policy.clear() }} />
            <Button variant="secondary" type="submit" disabled={policy.loading}>Kiểm tra phạm vi áp dụng</Button>
          </form>
          {policyError && <FeedbackMessage variant="error">{policyError}</FeedbackMessage>}
          {policy.loading && <FeedbackMessage>Đang kiểm tra phạm vi áp dụng…</FeedbackMessage>}
          {policy.error && <Problem message={policy.error.message} label="Thử lại kiểm tra bổ sung hàng"
            retry={policy.error.retryable ? () => policy.run(policy.error!.input) : undefined} />}
          {policy.data?.run ? <div className="gis-policy-result">
            <span>{policy.data.run.fixture_label}</span>
            <span>Thời điểm tạo {utcStamp(policy.data.run.created_at)}</span>
            <span>Phiên bản dữ liệu <code>{policy.data.run.data_version}</code></span>
            <Link to={policy.data.run.href}>Xem kết quả bổ sung hàng</Link>
          </div> : policy.data && <FeedbackMessage>Chưa có kết quả phù hợp với SKU và kho đã chọn.</FeedbackMessage>}
        </details>}
      </section>
    </div>}

    <section className="management-panel gis-panel" aria-labelledby="gis-heat-title">
      <div className="gis-section-heading">
        <div><h2 id="gis-heat-title">Lượng xuất theo vị trí kho</h2>
          <p className="gis-muted">Lượng xuất đáp ứng yêu cầu mua hàng{selectedProduct ? ` của ${selectedProduct.sku}` : ''}.</p></div>
      </div>
      <form className="gis-form gis-period-form" onSubmit={submitHeatmap}>
        <Input label="Từ ngày" type="date" value={startDate} required
          onChange={event => { setStartDate(event.target.value); setHeatError(''); heatmap.clear() }} />
        <Input label="Đến đầu ngày" type="date" value={endDate} required
          onChange={event => { setEndDate(event.target.value); setHeatError(''); heatmap.clear() }} />
        <Button type="submit" disabled={heatmap.loading || !choices.data?.products.length}>Xem lượng xuất</Button>
      </form>
      {heatError && <FeedbackMessage variant="error">{heatError}</FeedbackMessage>}
      {heatmap.loading ? <FeedbackMessage>Đang tải lượng xuất theo kho…</FeedbackMessage>
        : heatmap.error ? <Problem message={heatmap.error.message} label="Thử lại lượng xuất"
          retry={heatmap.error.retryable ? () => heatmap.run(heatmap.error!.input) : undefined} />
        : heatmap.data ? <HeatmapResults data={heatmap.data} />
        : <EmptyState title="Chưa có số liệu theo kỳ" description="Chọn SKU và khoảng ngày để xem lượng xuất từng kho." />}
    </section>
  </section>
}

export function GISPage() {
  const { token, user } = useAuth()
  if (!token || !user || !can(user.role, 'gis:read')) {
    return <FeedbackMessage variant="error">Bạn không có quyền xem bản đồ kho.</FeedbackMessage>
  }
  return <GISWorkspace key={`${user.id}:${user.role}`} token={token} mayRoute={can(user.role, 'gis:route')} />
}
