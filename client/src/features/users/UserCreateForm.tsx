import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { ApiError } from '../../shared/api/ApiError'
import { userCreateSchema, type UserCreateInput } from './schemas'

export function UserCreateForm({ create, pending, onCreated }: {
  create: (input: UserCreateInput) => Promise<unknown>
  pending: boolean
  onCreated: () => void
}) {
  const form = useForm<UserCreateInput>({
    resolver: zodResolver(userCreateSchema), defaultValues: { email: '', password: '', role: 'client' },
  })

  async function submit(input: UserCreateInput) {
    form.clearErrors()
    try {
      await create({ ...input, email: input.email.trim().toLowerCase() })
      form.reset()
      onCreated()
    } catch (error) {
      if (error instanceof ApiError) {
        for (const field of ['email', 'password', 'role'] as const) {
          const value = error.fields?.[field]
          if (value) form.setError(field, { type: 'server', message: Array.isArray(value) ? value.join(' ') : value })
        }
      }
      form.setError('root', { type: 'server', message: error instanceof Error ? error.message : 'Could not create user.' })
    }
  }

  return <form className="admin-inline-form" noValidate onSubmit={form.handleSubmit(submit)} aria-label="Create managed user">
    <h3>Create managed user</h3>
    <div className="admin-form-fields">
      <div><label htmlFor="create-user-email">Email</label><input id="create-user-email" type="email" autoComplete="off" aria-invalid={Boolean(form.formState.errors.email)} {...form.register('email')} />{form.formState.errors.email?.message && <small className="form-error">{form.formState.errors.email.message}</small>}</div>
      <div><label htmlFor="create-user-password">Password</label><input id="create-user-password" type="password" autoComplete="new-password" aria-invalid={Boolean(form.formState.errors.password)} {...form.register('password')} />{form.formState.errors.password?.message && <small className="form-error">{form.formState.errors.password.message}</small>}</div>
      <div><label htmlFor="create-user-role">Role</label><select id="create-user-role" {...form.register('role')}><option value="client">Client</option><option value="warehouse">Warehouse</option></select></div>
    </div>
    {form.formState.errors.root?.message && <p role="alert" className="form-error">{form.formState.errors.root.message}</p>}
    <button type="submit" disabled={pending || form.formState.isSubmitting}>{pending ? 'Creating…' : 'Create user'}</button>
  </form>
}
