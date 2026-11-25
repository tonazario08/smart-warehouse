import { z } from 'zod'

const coordinate = z.string().optional().transform((value) => value?.trim() ? Number(value) : null).pipe(z.number().finite().nullable())
export const warehouseSchema = z.strictObject({
  code: z.string().trim().min(1, 'Enter a warehouse code.').max(40).transform((value) => value.toUpperCase()),
  name: z.string().trim().min(1, 'Enter a warehouse name.').max(200),
  address: z.string().trim().min(1, 'Enter an address.'),
  latitude: coordinate.pipe(z.number().min(-90).max(90).nullable()),
  longitude: coordinate.pipe(z.number().min(-180).max(180).nullable()),
}).superRefine((value, context) => {
  if ((value.latitude === null) !== (value.longitude === null)) {
    context.addIssue({ code: 'custom', message: 'Latitude and longitude must be provided together.', path: ['latitude'] })
  }
})
export type WarehouseForm = z.input<typeof warehouseSchema>
