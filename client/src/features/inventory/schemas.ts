import { z } from 'zod'

export const movementSchema = z.object({
  warehouse_id: z.coerce.number().int().positive(),
  product_id: z.coerce.number().int().positive(),
  quantity: z.coerce.number().int().positive(),
  reference: z.string().trim().max(120).optional(),
  note: z.string().trim().max(2000).optional(),
}).strict()

export type MovementFormValues = z.input<typeof movementSchema>
export type MovementFormInput = z.output<typeof movementSchema>
