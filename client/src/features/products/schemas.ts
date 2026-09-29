import { z } from 'zod'

export const productSchema = z.strictObject({
  sku: z.string().trim().min(1, 'Enter an SKU.').max(80).transform((value) => value.toUpperCase()),
  name: z.string().trim().min(1, 'Enter a product name.').max(200),
  description: z.string().trim().transform((value) => value || null).nullable(),
  category_id: z.string().min(1, 'Choose a category.').transform(Number).pipe(z.number().int().positive()),
  supplier_id: z.string().optional().transform((value) => value ? Number(value) : null).pipe(z.number().int().positive().nullable()),
  unit: z.string().trim().min(1, 'Enter a unit.').max(40),
  reorder_level: z.string().min(1, 'Enter a reorder level.').transform(Number).pipe(z.number().int().min(0)),
  is_active: z.boolean(),
})
export type ProductForm = z.input<typeof productSchema>
