import { afterEach, expect, it, vi } from 'vitest'
import { advanceApiSession, onApiUnauthorized } from '../../api'
import { forecastError, getForecastStatus, getForecastPredictions, listForecastRuns } from './api'

afterEach(() => vi.unstubAllGlobals())
it('uses bearer transport and exact scoped filters', async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => new Response('{}'))
  vi.stubGlobal('fetch', fetcher)
  await getForecastStatus('token', 'research')
  await listForecastRuns('token', 'operational', 2)
  await getForecastPredictions('token', 'frv1-' + 'a'.repeat(64), 7, 'xgboost', 3)
  expect(fetcher.mock.calls[0][0]).toContain('/forecasts/status?mode=research')
  expect(fetcher.mock.calls[1][0]).toContain('mode=operational&page=2&page_size=20')
  expect(fetcher.mock.calls[2][0]).toContain('horizon=7&algorithm=xgboost&page=3&page_size=20')
  expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({ Authorization: 'Bearer token' })
})
it('keeps 403 sessions and invalidates current 401 using shared transport', async () => {
  const listener = vi.fn(), stop = onApiUnauthorized(listener)
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 403 })))
  await expect(getForecastStatus('token', 'research')).rejects.toMatchObject({ status: 403 })
  expect(listener).not.toHaveBeenCalled()
  advanceApiSession()
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })))
  await expect(getForecastStatus('token', 'research')).rejects.toMatchObject({ status: 401 })
  expect(listener).toHaveBeenCalledOnce()
  stop()
})
it('translates unsupported and corrupt artifacts without exposing server text', () => {
  expect(forecastError({ code: 'FORECAST_SCHEMA_UNSUPPORTED' })).toMatch(/không tương thích/i)
  expect(forecastError({ code: 'FORECAST_ARTIFACT_INVALID', message: 'secret' })).not.toContain('secret')
})
it.each([
  ['FORECAST_FORBIDDEN', 'quyền'], ['FORECAST_NOT_FOUND', 'Không tìm thấy'],
  ['FORECAST_ARTIFACT_INVALID', 'không hợp lệ'], ['FORECAST_CATALOG_UNAVAILABLE', 'không khả dụng'],
  ['UNKNOWN', 'Không thể tải'],
])('uses a safe translation for %s', (code, expected) => {
  expect(forecastError({ code, message: 'private server text' })).toContain(expected)
})
