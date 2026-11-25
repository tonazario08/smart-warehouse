import { z } from 'zod'

export const categorySchema = z.strictObject({
  name: z.string().trim().min(1, 'Nhập tên danh mục.').max(120, 'Tên danh mục không được quá 120 ký tự.'),
  parent_id: z.string().optional().transform(value => value ? Number(value) : null).pipe(z.number({ error: 'Chọn danh mục cha hợp lệ.' }).int('Chọn danh mục cha hợp lệ.').positive('Chọn danh mục cha hợp lệ.').max(2147483647, 'Chọn danh mục cha hợp lệ.').nullable()),
})
export type CategoryForm = z.input<typeof categorySchema>
