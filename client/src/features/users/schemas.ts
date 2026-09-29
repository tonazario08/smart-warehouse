import { z } from 'zod'

export const userCreateSchema = z.strictObject({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(12, 'Password must be at least 12 characters.').max(128, 'Password must be at most 128 characters.'),
  role: z.enum(['client', 'warehouse']),
})

export type UserCreateInput = z.infer<typeof userCreateSchema>
