import { z } from 'zod'

const optionalText = z.string().trim().transform((value) => value || null)
export const supplierSchema = z.strictObject({
  name: z.string().trim().min(1, 'Nhập tên nhà cung cấp.').max(200, 'Tên nhà cung cấp không được quá 200 ký tự.'),
  email: optionalText.pipe(z.email('Nhập email hợp lệ.').max(320, 'Email không được quá 320 ký tự.').nullable()),
  phone: optionalText.pipe(z.string().max(50, 'Số điện thoại không được quá 50 ký tự.').nullable()),
  address: optionalText,
})
export type SupplierForm = z.input<typeof supplierSchema>
