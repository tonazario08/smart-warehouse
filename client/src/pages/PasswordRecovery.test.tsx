import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { request } from '../api'
import { AuthProvider } from '../app/AuthProvider'
import { router } from '../app/router'

const response = (body: unknown, status = 200) => new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
it('submits the recovery email and shows a generic confirmation', async () => {
  let payload: unknown
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => { payload = JSON.parse(String(init.body)); return response({ message: 'generic' }, 202) }))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/forgot-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: /Gửi liên kết/ }))
  expect(await screen.findByRole('status')).toHaveTextContent(/nếu.*tài khoản/i)
  expect(payload).toEqual({ email: 'person@example.com' })
})
it('submits a fragment token and returns to login after resetting', async () => {
  let payload: unknown
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => { payload = JSON.parse(String(init.body)); return response(null, 204) }))
  window.history.replaceState(null, '', '/reset-password#token=sample-token')
  const active = createMemoryRouter(router.routes, { initialEntries: ['/reset-password#token=sample-token'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đặt lại mật khẩu' }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  expect(payload).toEqual({ token: 'sample-token', new_password: 'a-strong-password', confirm_password: 'a-strong-password' })
  expect(window.location.hash).toBe('')
  expect(await screen.findByRole('status')).toHaveTextContent(/thành công/i)
})
it('keeps the current session when the current password is wrong', async () => {
  localStorage.setItem('smart-warehouse-token', 'old-token')
  vi.stubGlobal('fetch', vi.fn(async (url) => String(url).endsWith('/auth/me')
    ? response({ id: 1, email: 'person@example.com', role: 'client', is_active: true })
    : response({ detail: { code: 'CURRENT_PASSWORD_INVALID', message: 'bad', fields: null } }, 400)))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/change-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(await screen.findByLabelText('Mật khẩu hiện tại'), { target: { value: 'wrong-password' } })
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/hiện tại không chính xác/i)
  expect(localStorage.getItem('smart-warehouse-token')).toBe('old-token')
  expect(active.state.location.pathname).toBe('/change-password')
})
it('shows unavailable service without revealing account status', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ detail: { code: 'PASSWORD_RECOVERY_UNAVAILABLE', message: 'unavailable', fields: null } }, 503)))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/forgot-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: /Gửi liên kết/ }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/chưa khả dụng/i)
})

it('does not erase a replacement session after an in-flight reset', async () => {
  let finish!: (response: Response) => void
  const pending = new Promise<Response>(resolve => { finish = resolve })
  localStorage.setItem('smart-warehouse-token', 'old-token')
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (String(url).endsWith('/auth/me')) return response({ id: 1, email: 'person@example.com', role: 'client', is_active: true })
    return pending
  }))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/reset-password#token=sample-token'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'a-strong-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đặt lại mật khẩu' }))
  localStorage.setItem('smart-warehouse-token', 'replacement-token')
  finish(response(null, 204))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Đặt lại mật khẩu' })).toBeEnabled())
  expect(localStorage.getItem('smart-warehouse-token')).toBe('replacement-token')
  expect(active.state.location.pathname).toBe('/reset-password')
})

it('shows success if a parallel request has already cleared the same old session', async () => {
  let finish!: (response: Response) => void
  const pending = new Promise<Response>(resolve => { finish = resolve })
  localStorage.setItem('smart-warehouse-token', 'old-token')
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (String(url).endsWith('/auth/me')) return response({ id: 1, email: 'person@example.com', role: 'client', is_active: true })
    if (String(url).endsWith('/auth/change-password')) return pending
    return response(null, 401)
  }))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/change-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(await screen.findByLabelText('Mật khẩu hiện tại'), { target: { value: 'initial-password' } })
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'replacement-password' } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'replacement-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }))
  await act(async () => { await request('/products', {}, 'old-token').catch(() => undefined) })
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  finish(response(null, 204))
  expect(await screen.findByRole('status')).toHaveTextContent(/thành công/i)
})
it('explains when the new password repeats the current password', async () => {
  localStorage.setItem('smart-warehouse-token', 'old-token')
  vi.stubGlobal('fetch', vi.fn(async (url) => String(url).endsWith('/auth/me')
    ? response({ id: 1, email: 'person@example.com', role: 'client', is_active: true })
    : response({ detail: { code: 'PASSWORD_REUSE', message: 'reuse', fields: null } }, 422)))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/change-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  fireEvent.change(await screen.findByLabelText('Mật khẩu hiện tại'), { target: { value: 'same-password-2026' } })
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'same-password-2026' } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'same-password-2026' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/khác mật khẩu hiện tại/i)
})

it('requires a recovery link before collecting a new password', () => {
  const active = createMemoryRouter(router.routes, { initialEntries: ['/reset-password'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  expect(screen.queryByLabelText('Mật khẩu mới')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /yêu cầu liên kết mới/i })).toHaveAttribute('href', '/forgot-password')
})

it('uses a newer link opened on the same page and counts Unicode code points', async () => {
  let payload: { token?: string } | undefined
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => {
    payload = JSON.parse(String(init.body))
    return response(null, 204)
  }))
  const active = createMemoryRouter(router.routes, { initialEntries: ['/reset-password#token=first'] })
  render(<AuthProvider><RouterProvider router={active} /></AuthProvider>)
  await act(() => active.navigate('/reset-password#token=second'))
  const password = '🔑'.repeat(70)
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: password } })
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: 'Đặt lại mật khẩu' }))
  await waitFor(() => expect(active.state.location.pathname).toBe('/login'))
  expect(payload?.token).toBe('second')
})
