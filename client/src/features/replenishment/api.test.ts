import { afterEach, expect, it, vi } from 'vitest'
import { getReplenishmentStatus, getReplenishmentDays, listReplenishmentRuns, replenishmentError } from './api'

afterEach(() => vi.unstubAllGlobals())
it('uses shared bearer transport and exact read filters', async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => new Response('{}'))
  vi.stubGlobal('fetch', fetcher)
  await getReplenishmentStatus('token', 'research')
  await listReplenishmentRuns('token', 'operational', 2)
  await getReplenishmentDays('token', 'rrv1-' + 'a'.repeat(64), 'xgboost', 7, '0.80', 'proposed', 3)
  expect(fetcher.mock.calls[0][0]).toContain('/replenishment/status?mode=research')
  expect(fetcher.mock.calls[1][0]).toContain('mode=operational&page=2&page_size=20')
  expect(fetcher.mock.calls[2][0]).toContain('algorithm=xgboost&lead_time=7&service=0.80&policy=proposed&page=3&page_size=20')
  expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({ Authorization: 'Bearer token' })
})
it('maps safe error messages without exposing server text', () => {
  expect(replenishmentError({ code: 'REPLENISHMENT_BINDING_UNAVAILABLE', message: 'secret' })).toMatch(/Sản phẩm hoặc kho/)
  expect(replenishmentError({ code: 'unknown', message: 'secret' })).not.toContain('secret')
})
