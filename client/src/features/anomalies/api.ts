import { request } from '../../api'
import type { AlertPage, Detail, Review, ReviewRequest, ReviewResult, StatusResponse } from './types'
export const getStatus = (token: string) => request<StatusResponse>('/anomalies/status', {}, token)
export const getAlerts = (token: string, page: number, status: string) => request<AlertPage>('/anomalies?' + new URLSearchParams({ page: String(page), page_size: '20', ...(status ? { status } : {}) }), {}, token)
export const getAlert = (token: string, id: string) => request<Detail>('/anomalies/' + encodeURIComponent(id), {}, token)
export const getReviews = (token: string, id: string) => request<{ items: Review[] }>('/anomalies/' + encodeURIComponent(id) + '/reviews', {}, token)
export const submitReview = (token: string, id: string, key: string, body: ReviewRequest) => request<ReviewResult>('/anomalies/' + encodeURIComponent(id) + '/review', { method: 'PATCH', headers: { 'Idempotency-Key': key }, body: JSON.stringify(body) }, token)
