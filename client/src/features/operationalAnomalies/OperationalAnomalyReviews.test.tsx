import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../app/AuthProvider'
import { router } from '../../app/router'

const path = '/api/v1/operational-anomalies/41'
const route = '/anomalies/operational/41'
const flagged = {
  transaction_id: 41, state: 'flagged', dataset_class: 'synthetic_test', reason_code: null,
  evaluated_at: '2026-11-22T09:00:00Z', score: 0.75, threshold: 0.5, model_version: 'test-model',
  feature_version: 'anomaly-features/1', base_value: 0.5, contributions: [0.25, 0, 0, 0, 0, 0],
}
type Review = {
  version: number; decision: string; note: string; actor_id: number; reviewed_at: string;
}
const first: Review = {
  version: 1, decision: 'legitimate', note: 'Đã kiểm tra phiếu gốc.', actor_id: 17,
  reviewed_at: '2026-11-22T09:22:00Z',
}
const second: Review = { ...first, version: 2, decision: 'insufficient_evidence', note: 'Thiếu chứng từ.' }
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const history = (...items: Review[]) => reply({ items, total: items.length, page: 1, page_size: 20, current_version: items[0]?.version ?? 0 })
const notFound = () => reply({ detail: { code: 'OPERATIONAL_ANOMALY_NOT_FOUND' } }, 404)
type Endpoints = { list?: () => Response; submit?: (init?: RequestInit) => Response | Promise<Response>; detail?: () => Response }

let app: ReturnType<typeof createMemoryRouter> | undefined
function mount(role: 'admin' | 'warehouse' | 'client' | null, endpoints: Endpoints = {}) {
  if (role) localStorage.setItem('smart-warehouse-token', 'review-token')
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    if (url.pathname.endsWith('/auth/me')) return reply({ id: 17, email: 'operator@example.test', role, is_active: true })
    if (url.pathname === path + '/reviews') {
      expect(url.search).toBe('?page=1&page_size=20')
      return endpoints.list ? endpoints.list() : history()
    }
    if (url.pathname === path + '/review') return endpoints.submit ? endpoints.submit(init) : notFound()
    if (url.pathname === path) return endpoints.detail ? endpoints.detail() : reply(flagged)
    if (url.pathname === path + '/outbound') return notFound()
    return reply({ items: [], total: 0, page: 1, page_size: 20 })
  })
  vi.stubGlobal('fetch', fetchMock)
  app = createMemoryRouter(router.routes, { initialEntries: [route] })
  render(<AuthProvider><RouterProvider router={app} /></AuthProvider>)
  return { app, fetchMock }
}
afterEach(() => {
  app?.dispose()
  localStorage.clear()
  vi.unstubAllGlobals()
})

async function fill(decision: string, note: string) {
  const select = await screen.findByLabelText('Nhận định')
  fireEvent.change(select, { target: { value: decision } })
  fireEvent.change(screen.getByLabelText('Lý do đối chiếu'), { target: { value: note } })
}
const save = () => fireEvent.click(screen.getByRole('button', { name: 'Lưu đánh giá' }))
const key = (init?: RequestInit) => new Headers(init?.headers).get('Idempotency-Key')

it('requires an explicit decision and nonblank reason; appends reviews with current version while retaining the original score', async () => {
  const rows: Review[] = []
  const submit = vi.fn((init?: RequestInit) => {
    expect(init?.method).toBe('PATCH')
    expect(key(init)).toMatch(/^[0-9a-f-]{36}$/i)
    const payload = JSON.parse(String(init?.body))
    expect(payload).toEqual(rows.length
      ? { expected_version: 1, decision: second.decision, note: second.note }
      : { expected_version: 0, decision: first.decision, note: first.note })
    rows.unshift(rows.length ? second : first)
    return reply(rows[0])
  })
  const { fetchMock } = mount('warehouse', { list: () => history(...rows), submit })
  expect(await screen.findByText('Chưa có đánh giá.')).toBeVisible()
  await fill('', 'Lý do')
  expect(screen.getByRole('button', { name: 'Lưu đánh giá' })).toBeDisabled()
  await fill('legitimate', '     ')
  expect(screen.getByRole('button', { name: 'Lưu đánh giá' })).toBeDisabled()
  await fill('legitimate', 'X'.repeat(1001))
  expect(screen.getByRole('button', { name: 'Lưu đánh giá' })).toBeDisabled()
  await fill('legitimate', ' ' + first.note + ' ')
  save()
  expect(await screen.findByText('Đã lưu đánh giá của nhân viên.')).toBeVisible()
  expect(await screen.findByText('Lý do: ' + first.note)).toBeVisible()
  await fill('insufficient_evidence', second.note)
  save()
  expect(await screen.findByText('Lý do: ' + second.note)).toBeVisible()
  expect(screen.getByText('Lý do: ' + first.note)).toBeVisible()
  expect(screen.getByText('0,75')).toBeVisible()
  expect(screen.getByText('Dữ liệu tổng hợp kiểm thử')).toBeVisible()
  expect(submit).toHaveBeenCalledTimes(2)
  expect(key(submit.mock.calls[0][0])).not.toBe(key(submit.mock.calls[1][0]))
  expect(fetchMock.mock.calls.filter(([url]) => new URL(String(url)).pathname === path)).toHaveLength(1)
})

it('reuses UUID and payload when response is lost, without firing twice while a save is pending', async () => {
  let reject!: () => void
  const submit = vi.fn<(init?: RequestInit) => Promise<Response>>()
  submit.mockImplementationOnce(() => new Promise((_resolve, rejectPromise) => { reject = () => rejectPromise(new Error('network error')) }))
  submit.mockResolvedValueOnce(reply(first))
  mount('admin', { submit })
  await fill(first.decision, first.note)
  const button = screen.getByRole('button', { name: 'Lưu đánh giá' })
  fireEvent.click(button)
  fireEvent.click(button)
  expect(submit).toHaveBeenCalledTimes(1)
  reject()
  const retry = await screen.findByRole('button', { name: 'Thử lưu lại cùng nội dung' })
  expect(screen.getByLabelText('Lý do đối chiếu')).toBeDisabled()
  fireEvent.click(retry)
  expect(await screen.findByText('Đã lưu đánh giá của nhân viên.')).toBeVisible()
  expect(submit).toHaveBeenCalledTimes(2)
  expect(key(submit.mock.calls[0][0])).toBe(key(submit.mock.calls[1][0]))
  expect(submit.mock.calls[0][0]?.body).toBe(submit.mock.calls[1][0]?.body)
})

it('refreshes stale history on HTTP 409 and never resubmits automatically', async () => {
  let writes = 0
  const submit = vi.fn((init?: RequestInit) => {
    const payload = JSON.parse(String(init?.body))
    if (++writes === 1) {
      expect(payload.expected_version).toBe(0)
      return reply({ detail: { code: 'OPERATIONAL_ANOMALY_REVIEW_CONFLICT' } }, 409)
    }
    expect(payload.expected_version).toBe(1)
    return reply(second)
  })
  mount('admin', { list: () => writes === 0 ? history() : writes === 1 ? history(first) : history(second, first), submit })
  await fill(second.decision, second.note)
  save()
  expect(await screen.findByText(/Đánh giá đã thay đổi/)).toBeVisible()
  expect(await screen.findByText('Lý do: ' + first.note)).toBeVisible()
  expect(submit).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('Lý do đối chiếu')).toHaveValue(second.note)
  save()
  expect(await screen.findByText('Lý do: ' + second.note)).toBeVisible()
  expect(submit).toHaveBeenCalledTimes(2)
  expect(key(submit.mock.calls[0][0])).not.toBe(key(submit.mock.calls[1][0]))
})

it('fails closed when the server will not verify a flagged transaction for review', async () => {
  mount('warehouse', { list: notFound })
  expect(await screen.findByText('Không xác minh được cảnh báo để xem đánh giá.')).toBeVisible()
  expect(screen.queryByLabelText('Nhận định')).not.toBeInTheDocument()
})

it.each(['pending', 'normal', 'unavailable', 'failed'])('does not load or display reviews for a %s result', async state => {
  const { fetchMock } = mount('warehouse', { detail: () => reply({ ...flagged, state }) })
  expect(await screen.findByRole('heading', { name: 'Kết quả chấm' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Đánh giá của nhân viên' })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/reviews'))).toBe(false)
})

it.each([['client', '/products'], [null, '/login']] as const)('does not fetch review data for %s on a direct result URL', async (role, landing) => {
  const { app: active, fetchMock } = mount(role)
  await waitFor(() => expect(active.state.location.pathname).toBe(landing))
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/operational-anomalies'))).toBe(false)
})

it('discards a late write response from a superseded route without displaying another transaction’s review', async () => {
  let resolve!: (response: Response) => void
  const submit = vi.fn<(init?: RequestInit) => Promise<Response>>(
    () => new Promise(done => { resolve = done }),
  )
  const { app: active } = mount('admin', { submit })
  await fill(first.decision, first.note)
  save()
  expect(submit).toHaveBeenCalledTimes(1)
  await act(async () => active.navigate('/anomalies/operational'))
  expect(await screen.findByRole('heading', { name: 'Chấm bất thường sau xuất B2B' })).toBeVisible()
  const signal = submit.mock.calls[0][0]?.signal
  expect(signal?.aborted).toBe(true)
  await act(async () => resolve(reply(first)))
  expect(screen.queryByText('Đã lưu đánh giá của nhân viên.')).not.toBeInTheDocument()
  expect(screen.queryByText('Lý do: ' + first.note)).not.toBeInTheDocument()
  expect(submit).toHaveBeenCalledTimes(1)
})
