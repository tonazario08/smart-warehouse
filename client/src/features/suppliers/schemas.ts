import { z } from 'zod'

const optionalText = z.string().trim().transform((value) => value || null)
export const supplierSchema = z.strictObject({
  name: z.string().trim().min(1, 'Enter a supplier name.').max(200),
  email: optionalText.pipe(z.email('Enter a valid email address.').nullable()),
  phone: optionalText.pipe(z.string().max(50).nullable()),
  address: optionalText,
})
export type SupplierForm = z.input<typeof supplierSchema>
