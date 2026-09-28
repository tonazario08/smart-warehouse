import { ApiError } from './ApiError'

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export class ApiClient {
  constructor(
    private readonly baseUrl = defaultBaseUrl,
    private readonly getToken: () => string | null = () => null,
    private readonly onUnauthorized: () => void = () => undefined,
  ) {}

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = this.getToken()
    const headers = new Headers(init.headers)
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    if (token) headers.set('Authorization', `Bearer ${token}`)

    const baseUrl = this.baseUrl.replace(/\/$/, '')
    const response = await fetch(`${baseUrl}${path.startsWith('/') ? path : `/${path}`}`, {
      ...init,
      headers,
    })
    const body = response.status === 204 ? null : await response.json().catch(() => null)

    if (!response.ok) {
      const error = ApiError.fromResponse(response.status, body)
      if (response.status === 401) this.onUnauthorized()
      throw error
    }

    return body as T
  }
}
