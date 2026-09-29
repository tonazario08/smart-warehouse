import { z } from 'zod'

export const categorySchema = z.strictObject({
  name: z.string().trim().min(1, 'Enter a category name.').max(120),
  parent_id: z.string().optional().transform((value) => value ? Number(value) : null).pipe(z.number().int().positive().nullable()),
})
export type CategoryForm = z.input<typeof categorySchema>
