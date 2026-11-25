import type { ApiClient } from '../../shared/api/ApiClient'
import type { AuditFilters, AuditPageResponse } from './types'

export const createAuditApi = (client: ApiClient) => ({
  list: (filters: AuditFilters) => {
    const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.pageSize) })
    if (filters.action) params.set('action', filters.action)
    if (filters.targetType) params.set('target_type', filters.targetType)
    if (filters.targetId) params.set('target_id', filters.targetId)
    return client.request<AuditPageResponse>(`/audit-logs?${params}`)
  },
})
