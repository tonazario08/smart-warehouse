import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { jsonResponse, renderManagementRoute } from '../../test/renderManagementRoute'
import { formatDateTime } from '../../shared/lib/formatters'
const record = { id: 9, actor_user_id: 1, action: 'user.role_changed', target_type: 'user', target_id: 2, before_data: { role: 'client', password_hash: 'secret' }, after_data: { role: '<img src=x onerror=alert(1)>', password: 'secret', extra: { email: 'nested-secret' } }, created_at: '2026-09-29T09:00:00Z' }
function renderAudit() {
  return renderManagementRoute('/audit', 'admin', url => jsonResponse({ items: [record], total: 21, page: url.includes('page=2') ? 2 : 1, page_size: 20 })).fetchMock
}
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })
it('renders only safe allowlisted translated facts without executable or arbitrary payload fields', async () => {
  renderAudit()
  await screen.findByText('Đổi vai trò', { selector: 'td' })
  expect(screen.getByText('Tài khoản #1')).toBeInTheDocument()
  expect(screen.getByText('Người dùng #2')).toBeInTheDocument()
  expect(screen.getByText('Khách hàng')).toBeInTheDocument()
  expect(screen.getByText('Không xác định')).toBeInTheDocument()
  expect(document.querySelector('.management-workspace img')).toBeNull()
  expect(screen.queryByText('secret')).not.toBeInTheDocument()
  expect(screen.queryByText('nested-secret')).not.toBeInTheDocument()
  expect(screen.queryByText('<img src=x onerror=alert(1)>')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Sửa|Xóa/ })).not.toBeInTheDocument()
  expect(screen.getByText(formatDateTime(record.created_at))).toBeInTheDocument()
})
it('sends exact action/target filters and resets bounded server pagination', async () => {
  const fetchMock = renderAudit()
  await screen.findByText('Đổi vai trò', { selector: 'td' })
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 2')
  await userEvent.selectOptions(screen.getByLabelText('Hành động'), 'user.created')
  await userEvent.type(screen.getByLabelText('Loại đối tượng'), 'user')
  await userEvent.type(screen.getByLabelText('Mã đối tượng'), '2')
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(await screen.findByText('Trang 1 / 2')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([url]) => { const p = new URL(String(url)).searchParams; return p.get('action') === 'user.created' && p.get('target_type') === 'user' && p.get('target_id') === '2' && p.get('page') === '1' })).toBe(true)
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 2')
  expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
})
it.each(['0', '-2', '1.5', '2147483648', 'not-id'])('rejects invalid target ID %s without another API read', async value => {
  const fetchMock = renderAudit()
  await screen.findByText('Đổi vai trò', { selector: 'td' })
  const before = fetchMock.mock.calls.length
  fireEvent.change(screen.getByLabelText('Mã đối tượng'), { target: { value } })
  await userEvent.click(screen.getByRole('button', { name: 'Áp dụng bộ lọc' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã đối tượng phải là số nguyên dương hợp lệ.')
  expect(fetchMock.mock.calls).toHaveLength(before)
})
it('keeps session on forbidden read and exposes an actionable safe retry state', async () => {
  let denied = true
  renderManagementRoute('/audit', 'admin', () => denied ? jsonResponse({ detail: { code: 'PERMISSION_DENIED', message: 'unsafe server diagnostic' } }, 403) : jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Bạn không có quyền thực hiện thao tác này.')
  expect(localStorage.getItem('smart-warehouse-token')).toBe('admin-test-token')
  denied = false
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText('Không có nhật ký phù hợp.')).toBeInTheDocument()
})

it.each(['constructor', '__proto__'])('does not treat inherited role names %s as translated safe values', async role => {
  renderManagementRoute('/audit', 'admin', () => jsonResponse({ items: [{ ...record, before_data: null, after_data: { role } }], total: 1, page: 1, page_size: 20 }))
  expect(await screen.findByText('Không xác định')).toBeInTheDocument()
  expect(screen.queryByText('Unexpected Application Error!')).not.toBeInTheDocument()
})
