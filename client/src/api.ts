import type { Category, DashboardStats, Movement, MovementInput, MovementRead, Page, Product, ProductInput, Stock, Supplier, Transaction, User, Warehouse, WarehouseInput } from './types'
import { collectAllPages } from './shared/api/collectAllPages'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
type FieldErrors = Record<string, string[] | string> | null
let sessionGeneration = 0
const unauthorizedListeners = new Set<(token: string, generation: number) => void>()
export function advanceApiSession() { return ++sessionGeneration }
export function onApiUnauthorized(listener: (token: string, generation: number) => void) {
  unauthorizedListeners.add(listener)
  return () => { unauthorizedListeners.delete(listener) }
}

const errorMessages: Record<string, string> = {
  INVALID_CREDENTIALS: 'Email hoặc mật khẩu không chính xác. Vui lòng kiểm tra và thử lại.',
  PRODUCT_IN_USE: 'Không thể xóa sản phẩm vì đang được tham chiếu trong dữ liệu tồn kho.',
  PRODUCT_NOT_FOUND: 'Không tìm thấy sản phẩm.',
  CATEGORY_NOT_FOUND: 'Không tìm thấy danh mục. Vui lòng chọn lại.',
  SUPPLIER_NOT_FOUND: 'Không tìm thấy nhà cung cấp. Vui lòng chọn lại.',
  WAREHOUSE_NOT_FOUND: 'Không tìm thấy kho hàng.',
  STOCK_NOT_FOUND: 'Không tìm thấy bản ghi tồn kho.',
  INSUFFICIENT_STOCK: 'Số lượng tồn kho không đủ để xuất. Vui lòng kiểm tra lại.',
  STOCK_QUANTITY_LIMIT_EXCEEDED: 'Số lượng tồn kho vượt giới hạn cho phép.',
  STOCK_CONFLICT: 'Tồn kho vừa thay đổi. Vui lòng tải lại và thử lại.',
  PRODUCT_SKU_CONFLICT: 'Mã SKU đã tồn tại. Vui lòng chọn mã khác.',
  WAREHOUSE_CONFLICT: 'Mã hoặc tên kho đã tồn tại. Vui lòng chọn thông tin khác.',
}
const fieldLabels: Record<string, string> = { sku: 'mã SKU', name: 'tên', category_id: 'danh mục', supplier_id: 'nhà cung cấp', unit: 'đơn vị', reorder_level: 'mức tồn tối thiểu', is_active: 'trạng thái', code: 'mã kho', address: 'địa chỉ', latitude: 'vĩ độ', longitude: 'kinh độ', quantity: 'số lượng', reference: 'mã phiếu', note: 'ghi chú', warehouse_id: 'kho hàng', product_id: 'sản phẩm' }
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
function safeMessage(status: number, code: string, fields: FieldErrors) {
  if (errorMessages[code]) return errorMessages[code]
  if (status === 401) return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
  if (status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
  if (status === 404) return 'Không tìm thấy dữ liệu được yêu cầu.'
  if (status === 409) return 'Dữ liệu bị trùng hoặc đang được sử dụng. Vui lòng kiểm tra lại.'
  if (status === 422) {
    const labels = [...new Set(Object.keys(fields ?? {}).flatMap(key => fieldLabels[key] ? [fieldLabels[key]] : []))]
    return 'Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.' + (labels.length ? ' Trường cần kiểm tra: ' + labels.join(', ') + '.' : '')
  }
  return 'Không thể hoàn tất yêu cầu. Vui lòng thử lại sau.'
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code = 'UNEXPECTED_RESPONSE', readonly fields: FieldErrors = null, readonly staleSession = false, readonly serverMessage?: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const generation = sessionGeneration
  const response = await fetch(apiBaseUrl + path, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}), ...options.headers } })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = isRecord(body) && isRecord(body.detail) ? body.detail : null
    const code = typeof detail?.code === 'string' ? detail.code : 'UNEXPECTED_RESPONSE'
    const fields = isRecord(detail?.fields) ? detail.fields as FieldErrors : null
    const staleSession = generation !== sessionGeneration
    if (response.status === 401 && token && !staleSession) unauthorizedListeners.forEach(listener => listener(token, generation))
    const serverMessage = typeof detail?.message === 'string' ? detail.message : isRecord(body) && typeof body.detail === 'string' ? body.detail : undefined
    throw new ApiError(safeMessage(response.status, code, fields), response.status, code, fields, staleSession, serverMessage)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const pagePath = (path: string, page: number) => path + (path.includes('?') ? '&' : '?') + 'page=' + page + '&page_size=100'
async function readPage<T>(path: string, token: string, page = 1): Promise<Page<T>> {
  const result = await request<Page<T>>(pagePath(path, page), {}, token)
  if (!result || !Array.isArray(result.items) || !Number.isInteger(result.page_size) || result.page_size < 1 || !Number.isInteger(result.total) || result.total < 0) {
    throw new ApiError('Không thể đọc đầy đủ dữ liệu. Vui lòng thử lại.', 502)
  }
  return result
}
const allPages = <T>(path: string, token: string) => collectAllPages(page => readPage<T>(path, token, page))
type HistoryFilters = { warehouse_id?: number; product_id?: number }
const historyPath = (path: string, filters?: HistoryFilters) => {
  const params = new URLSearchParams()
  if (filters?.warehouse_id) params.set('warehouse_id', String(filters.warehouse_id))
  if (filters?.product_id) params.set('product_id', String(filters.product_id))
  return path + (params.size ? '?' + params : '')
}

export const api = {
  login: (email: string, password: string) => request<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<User>('/auth/me', {}, token),
  products: (token: string, page = 1) => readPage<Product>('/products', token, page),
  productsAll: async (token: string) => (await allPages<Product>('/products', token)).items,
  product: (token: string, id: number) => request<Product>('/products/' + id, {}, token),
  categories: (token: string) => allPages<Category>('/categories', token),
  suppliers: (token: string) => allPages<Supplier>('/suppliers', token),
  warehouses: async (token: string) => (await allPages<Warehouse>('/warehouses', token)).items,
  warehouse: (token: string, id: number) => request<Warehouse>('/warehouses/' + id, {}, token),
  stock: async (token: string) => (await allPages<Stock>('/stock', token)).items,
  dashboardStats: (token: string) => request<DashboardStats>('/dashboard/stats', {}, token),
  transactions: async (token: string, filters?: HistoryFilters) => (await allPages<Transaction>(historyPath('/transactions', filters), token)).items,
  inbounds: async (token: string, filters?: HistoryFilters) => (await allPages<MovementRead>(historyPath('/inbounds', filters), token)).items,
  outbounds: async (token: string, filters?: HistoryFilters) => (await allPages<MovementRead>(historyPath('/outbounds', filters), token)).items,
  createInbound: (token: string, input: MovementInput) => request<Movement>('/inbounds', { method: 'POST', body: JSON.stringify(input) }, token),
  createOutbound: (token: string, input: MovementInput) => request<Movement>('/outbounds', { method: 'POST', body: JSON.stringify(input) }, token),
  createProduct: (token: string, input: ProductInput) => request<Product>('/products', { method: 'POST', body: JSON.stringify(input) }, token),
  updateProduct: (token: string, id: number, input: ProductInput) => request<Product>('/products/' + id, { method: 'PUT', body: JSON.stringify(input) }, token),
  deleteProduct: (token: string, id: number) => request<void>('/products/' + id, { method: 'DELETE' }, token),
  createWarehouse: (token: string, input: WarehouseInput) => request<Warehouse>('/warehouses', { method: 'POST', body: JSON.stringify(input) }, token),
  updateWarehouse: (token: string, id: number, input: WarehouseInput) => request<Warehouse>('/warehouses/' + id, { method: 'PUT', body: JSON.stringify(input) }, token),
}
