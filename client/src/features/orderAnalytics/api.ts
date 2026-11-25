import { request } from '../../api'
import type { Page } from '../../types'
import type { Warehouse } from '../warehouses/types'
import type { AnalyticsTarget, OpenDemand, OrderCheck, ReplenishmentPosition, SimulationSelection } from './types'

export async function getOrderWarehouses(token: string, signal: AbortSignal) {
  const pageSize = 100
  const getPage = (page: number) => request<Page<Warehouse>>(
    '/warehouses?' + new URLSearchParams({ page: String(page), page_size: String(pageSize) }),
    { signal }, token,
  )
  const first = await getPage(1)
  const options = new Map(first.items.map(item => [item.id, item]))
  const pages = Math.ceil(first.total / pageSize)
  for (let page = 2; page <= pages; page++) {
    const result = await getPage(page)
    for (const item of result.items) options.set(item.id, item)
  }
  return [...options.values()]
}

function targetParams(target: AnalyticsTarget) {
  return new URLSearchParams({ warehouse_id: String(target.warehouse_id), product_id: String(target.product_id) })
}

export function getOpenDemand(token: string, target: AnalyticsTarget, signal: AbortSignal) {
  return request<OpenDemand>('/order-analytics/open-demand?' + targetParams(target), { signal }, token)
}

export function getReplenishmentPosition(token: string, target: AnalyticsTarget, view: 'operational' | 'demo', selection: SimulationSelection, signal: AbortSignal) {
  const params = targetParams(target)
  params.set('view', view)
  params.set('algorithm', selection.algorithm)
  params.set('lead_time', String(selection.lead_time))
  params.set('service', selection.service)
  params.set('policy', selection.policy)
  if (selection.reference_date) params.set('reference_date', selection.reference_date)
  if (view === 'demo' && selection.run_id) params.set('run_id', selection.run_id)
  return request<ReplenishmentPosition>('/order-analytics/replenishment-position?' + params, { signal }, token)
}

export function getOrderChecks(token: string, target: AnalyticsTarget, page: number, signal: AbortSignal) {
  const params = targetParams(target)
  params.set('page', String(page))
  params.set('page_size', '20')
  return request<Page<OrderCheck>>('/order-analytics/order-checks?' + params, { signal }, token)
}
