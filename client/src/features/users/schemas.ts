import { z } from 'zod'

export const userCreateSchema = z.strictObject({
  email: z.email('Nhập email hợp lệ.'),
  password: z.string().min(12, 'Mật khẩu cần ít nhất 12 ký tự.').max(128, 'Mật khẩu không được quá 128 ký tự.'),
  role: z.enum(['client', 'warehouse'], { error: 'Chọn vai trò được hỗ trợ.' }),
})

export type UserCreateInput = z.infer<typeof userCreateSchema>
