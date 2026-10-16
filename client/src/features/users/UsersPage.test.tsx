import { QueryObserver } from '@tanstack/react-query'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { jsonResponse as json, renderManagementRoute } from '../../test/renderManagementRoute'
const admin = { id: 1, email: 'admin@example.com', role: 'admin', is_active: true }
const client = { id: 2, email: 'client@example.com', role: 'client', is_active: true }
const worker = { id: 3, email: 'worker@example.com', role: 'warehouse', is_active: false }
const page = (items: unknown[], total = items.length, number = 1) => ({ items, total, page: number, page_size: 20 })
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it('lists server pages without admin creation or admin record mutations', async () => {
  const view = renderManagementRoute('/users', 'admin', url => json(url.includes('page=2') ? page([worker], 21, 2) : page([admin, client], 21)))
  await screen.findByText(client.email)
  expect(within(screen.getByLabelText('Vai trò', { selector: '#create-user-role' })).queryByRole('option', { name: /Quản trị/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Đổi vai trò cho ' + admin.email })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Đổi trạng thái cho ' + admin.email })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText(worker.email)).toBeInTheDocument()
  expect(screen.getByText('Trang 2 / 2')).toBeInTheDocument()
  expect(view.fetchMock.mock.calls.some(([url]) => String(url).includes('/users?page=2&page_size=20'))).toBe(true)
})
it('validates and creates managed users, refreshes roster and clears password only on success', async () => {
  let created = false, reads = 0
  const view = renderManagementRoute('/users', 'admin', (url, init) => {
    if (init?.method === 'POST') { created = true; return json(client, 201) }
    reads++; return json(page(created ? [client] : []))
  })
  await screen.findByText('Chưa có người dùng.')
  await userEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }))
  expect(await screen.findByText('Nhập email hợp lệ.')).toBeInTheDocument()
  expect(view.fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  await userEvent.type(screen.getByLabelText('Email'), client.email)
  await userEvent.type(screen.getByLabelText('Mật khẩu'), 'synthetic-password-1')
  await userEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }))
  await screen.findByText(client.email)
  expect(reads).toBeGreaterThan(1)
  expect(screen.getByLabelText('Mật khẩu')).toHaveValue('')
  expect(JSON.stringify(view.queryClient.getQueryCache().getAll().map(q => q.queryKey))).not.toContain('synthetic-password')
})
it.each([409, 422])('keeps draft and associates sanitized server fields on %s', async status => {
  renderManagementRoute('/users', 'admin', (_, init) => init?.method === 'POST' ? json({ detail: { code: status === 409 ? 'USER_EMAIL_CONFLICT' : 'REQUEST_VALIDATION_ERROR', message: 'internal raw message', fields: { email: ['raw email'], password: ['raw password'] } } }, status) : json(page([])))
  await screen.findByText('Chưa có người dùng.')
  await userEvent.type(screen.getByLabelText('Email'), 'taken@example.com')
  await userEvent.type(screen.getByLabelText('Mật khẩu'), 'synthetic-password-1')
  await userEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/Email|Dữ liệu/)
  for (const label of ['Email', 'Mật khẩu']) {
    expect(screen.getByLabelText(label)).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText(label)).toHaveAccessibleDescription('Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.')
  }
  expect(screen.getByLabelText('Mật khẩu')).toHaveValue('synthetic-password-1')
  expect(screen.queryByText(/internal raw/)).not.toBeInTheDocument()
})
it('confirms, cancels and retries role changes without losing roster or current selection', async () => {
  let currentRole = 'client', attempts = 0, reads = 0
  const sent: string[] = []
  const auditFetch = vi.fn(async () => ({ items: [] }))
  let stop: () => void = () => {}
  const view = renderManagementRoute('/users', 'admin', (_, init) => {
    if (init?.method === 'PATCH') {
      const role = JSON.parse(String(init.body)).role; sent.push(role); attempts++
      if (attempts === 1) return json({ detail: { code: 'USER_ROLE_UNCHANGED', fields: null } }, 409)
      currentRole = role; return json({ ...client, role })
    }
    reads++; return json(page([{ ...client, role: currentRole }]))
  }, cache => { stop = new QueryObserver(cache, { queryKey: ['audit', { page: 1 }], queryFn: auditFetch }).subscribe(() => undefined) })
  await screen.findByText(client.email)
  await userEvent.click(screen.getByRole('button', { name: 'Đổi vai trò cho ' + client.email }))
  expect(view.fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'Hủy' }))
  expect(attempts).toBe(0)
  await userEvent.click(screen.getByRole('button', { name: 'Đổi vai trò cho ' + client.email }))
  expect(screen.getByLabelText('Vai trò mới')).toHaveValue('warehouse')
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận đổi vai trò' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Vai trò hiện tại không thay đổi.')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận đổi vai trò' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(reads).toBeGreaterThan(1)
  await userEvent.click(screen.getByRole('button', { name: 'Đổi vai trò cho ' + client.email }))
  expect(screen.getByLabelText('Vai trò mới')).toHaveValue('client')
  await userEvent.selectOptions(screen.getByLabelText('Vai trò mới'), 'warehouse')
  await userEvent.click(screen.getByRole('button', { name: 'Tải lại người dùng' }))
  expect(screen.getByLabelText('Vai trò mới')).toHaveValue('warehouse')
  await userEvent.selectOptions(screen.getByLabelText('Vai trò mới'), 'client')
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận đổi vai trò' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.getByRole('table').getElementsByTagName('tbody')[0]).toHaveTextContent('Khách hàng')
  expect(sent).toEqual(['warehouse', 'warehouse', 'client'])
  await waitFor(() => expect(auditFetch).toHaveBeenCalledTimes(3))
  stop()
})
it('blocks duplicate status submissions and invalidates roster plus observed audit data', async () => {
  let finish!: (response: Response) => void
  let changed = false
  const auditFetch = vi.fn(async () => ({ items: [] }))
  let stop: () => void = () => {}
  const view = renderManagementRoute('/users', 'admin', (_, init) => {
    if (init?.method === 'PATCH') return new Promise<Response>(resolve => { finish = resolve })
    return json(page([{ ...client, is_active: !changed }]))
  }, cache => { stop = new QueryObserver(cache, { queryKey: ['audit', { page: 1 }], queryFn: auditFetch }).subscribe(() => undefined) })
  await screen.findByText(client.email)
  await userEvent.click(screen.getByRole('button', { name: 'Vô hiệu hóa ' + client.email }))
  expect(view.fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận vô hiệu hóa' }))
  expect(screen.getByRole('button', { name: 'Hủy' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Xác nhận vô hiệu hóa' }))
  expect(view.fetchMock.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1)
  changed = true; await act(async () => { finish(json({ ...client, is_active: false })) })
  expect(await screen.findByText('Đã vô hiệu hóa')).toBeInTheDocument()
  await waitFor(() => expect(auditFetch).toHaveBeenCalledTimes(2))
  stop()
})
