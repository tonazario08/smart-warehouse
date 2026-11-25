export interface AuditRecord {
  id: number
  actor_user_id: number
  action: string
  target_type: string
  target_id: number
  before_data: Record<string, unknown> | null
  after_data: Record<string, unknown> | null
  created_at: string
}

export interface AuditPageResponse {
  items: AuditRecord[]
  total: number
  page: number
  page_size: number
}

export interface AuditFilters {
  page: number
  pageSize: number
  action: string
  targetType: string
  targetId: string
}
