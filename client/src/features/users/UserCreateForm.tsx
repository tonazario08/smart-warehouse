import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { ApiError } from '../../shared/api/ApiError'
import { Button } from '../../shared/ui/Button'
import { Input } from '../../shared/ui/Input'
import { Select } from '../../shared/ui/Select'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { userCreateSchema, type UserCreateInput } from './schemas'

export function UserCreateForm({ create, pending, onCreated }: { create: (input: UserCreateInput) => Promise<unknown>; pending: boolean; onCreated: () => void }) {
  const form = useForm<UserCreateInput>({ resolver: zodResolver(userCreateSchema), defaultValues: { email: '', password: '', role: 'client' } })
  async function submit(input: UserCreateInput) {
    form.clearErrors()
    try { await create({ ...input, email: input.email.trim().toLowerCase() }); form.reset(); onCreated() }
    catch (error) {
      if (error instanceof ApiError) for (const field of ['email', 'password', 'role'] as const) {
        if (error.fields?.[field]) form.setError(field, { type: 'server', message: 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.' })
      }
      form.setError('root', { message: error instanceof ApiError ? error.message : 'Không thể tạo người dùng. Vui lòng thử lại.' })
    }
  }
  const busy = pending || form.formState.isSubmitting
  return <form className="management-panel management-form" aria-label="Tạo tài khoản được quản lý" noValidate onSubmit={form.handleSubmit(submit)}>
    <h2>Tạo tài khoản</h2><p>Chỉ tạo tài khoản khách hàng hoặc nhân viên kho. Mật khẩu không được lưu trong nhật ký quản trị.</p>
    <div className="management-fields">
      <Input label="Email" id="create-user-email" type="email" autoComplete="off" {...form.register('email')} error={form.formState.errors.email?.message} disabled={busy} />
      <Input label="Mật khẩu" id="create-user-password" type="password" autoComplete="new-password" {...form.register('password')} error={form.formState.errors.password?.message} disabled={busy} />
      <Select label="Vai trò" id="create-user-role" {...form.register('role')} options={[{ value: 'client', label: 'Khách hàng' }, { value: 'warehouse', label: 'Nhân viên kho' }]} error={form.formState.errors.role?.message} disabled={busy} />
    </div>
    {form.formState.errors.root?.message && <FeedbackMessage variant="error">{form.formState.errors.root.message}</FeedbackMessage>}
    <div className="management-actions"><Button type="submit" isLoading={busy}>Tạo người dùng</Button><Button variant="secondary" disabled={busy} onClick={() => form.reset()}>Hủy nhập</Button></div>
  </form>
}
