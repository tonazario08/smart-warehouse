import { ApiError as TransportError, request } from '../../api'
import { ApiClient } from './ApiClient'
import { ApiError } from './ApiError'

class ManagementApiClient extends ApiClient {
  constructor(private readonly readToken: () => string | null) { super() }

  override async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    try {
      return await request<T>(path, options, this.readToken() ?? undefined)
    } catch (cause) {
      if (cause instanceof TransportError) {
        const fields = cause.fields ? Object.fromEntries(Object.keys(cause.fields).map(field => [field, ['Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.']])) : null
        throw Object.assign(new ApiError(cause.status, cause.code, cause.message, fields, null), { staleSession: cause.staleSession })
      }
      throw new ApiError(0, 'NETWORK_ERROR', 'Không thể kết nối. Vui lòng thử lại.', null, null)
    }
  }
}

export function createManagementApiClient(readToken: () => string | null): ApiClient {
  return new ManagementApiClient(readToken)
}
