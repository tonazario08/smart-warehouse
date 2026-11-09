import { ApiError, api, request } from '../../api'
import type {
  GisChoices, GisStatus, Heatmap, HeatmapInput, OptionsInput, PolicyContext, PolicyInput,
  RouteInput, RouteRead, WarehouseOptions,
} from './types'

export function getGisStatus(token: string, _input: undefined, signal: AbortSignal) {
  return request<GisStatus>('/gis/status', { signal }, token)
}

export async function getGisChoices(token: string, _input: undefined, _signal: AbortSignal): Promise<GisChoices> {
  const [products, warehouses] = await Promise.all([api.productsAll(token), api.warehouses(token)])
  return { products: products.filter(product => product.is_active), warehouses }
}

export function getWarehouseOptions(token: string, input: OptionsInput, signal: AbortSignal) {
  return request<WarehouseOptions>('/gis/warehouse-options', {
    method: 'POST', body: JSON.stringify(input), signal,
  }, token)
}

export function getGisRoute(token: string, input: RouteInput, signal: AbortSignal) {
  return request<RouteRead>('/gis/route', { method: 'POST', body: JSON.stringify(input), signal }, token)
}

export function getGisHeatmap(token: string, input: HeatmapInput, signal: AbortSignal) {
  const query = new URLSearchParams({
    product_id: String(input.product_id), start_date: input.start_date, end_date: input.end_date,
  })
  return request<Heatmap>('/gis/heatmap?' + query, { signal }, token)
}

export function getGisPolicy(token: string, input: PolicyInput, signal: AbortSignal) {
  const query = new URLSearchParams({
    run_id: input.run_id, product_id: String(input.product_id), warehouse_id: String(input.warehouse_id),
  })
  return request<PolicyContext>('/gis/policy-context?' + query, { signal }, token)
}

const errorMessages: Record<string, string> = {
  GIS_PRODUCT_NOT_FOUND: 'Không tìm thấy sản phẩm đang hoạt động.',
  GIS_WAREHOUSE_NOT_FOUND: 'Không tìm thấy kho hàng.',
  GIS_WAREHOUSE_LIMIT: 'Có quá 100 kho để xếp hạng trong một lần tra cứu.',
  GIS_PURCHASE_REQUEST_MISMATCH: 'SKU hoặc số lượng chưa khớp với yêu cầu mua hàng.',
  GIS_PERIOD_INVALID: 'Chọn kỳ từ 1 đến 90 ngày.',
}

export function gisError(cause: unknown) {
  if (!(cause instanceof ApiError)) return 'Không thể tải dữ liệu. Vui lòng thử lại.'
  return errorMessages[cause.code] ?? cause.message
}

const reasons: Record<string, string> = {
  snapshot_unconfigured: 'Chưa cấu hình bản chụp đường.',
  snapshot_invalid: 'Bản chụp đường không hợp lệ.',
  snapshot_stale: 'Bản chụp đường đã quá hạn.',
  outside_coverage: 'Điểm đi hoặc điểm đến nằm ngoài vùng đường.',
  snap_too_far: 'Không có nút đường trong vòng 200 m.',
  no_route: 'Không tìm thấy đường đi trong mạng đường đã chọn.',
  budget_exceeded: 'Đã hết giới hạn tính đường cho lượt tra cứu này.',
  geometry_limit: 'Tuyến vượt giới hạn 4.000 điểm hiển thị.',
  missing_stock: 'Chưa có bản ghi tồn.',
  insufficient_stock: 'Tồn kho chưa đủ số lượng cần.',
  missing_coordinates: 'Kho chưa có tọa độ.',
  invalid_coordinates: 'Tọa độ kho không hợp lệ.',
  origin_missing_coordinates: 'Kho đi chưa có tọa độ.',
  origin_invalid_coordinates: 'Tọa độ kho đi không hợp lệ.',
  destination_missing_coordinates: 'Kho đích chưa có tọa độ.',
  destination_invalid_coordinates: 'Tọa độ kho đích không hợp lệ.',
}

export function gisReason(reason: string) {
  return reasons[reason] ?? 'Chưa có kết quả khả dụng.'
}
