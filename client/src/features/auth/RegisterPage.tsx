import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import type { FieldErrors } from '../../shared/api/types'
import { ApiError } from '../../shared/api/ApiError'
import { Link } from 'react-router-dom'
import { registerSchema, type RegisterInput } from './schemas'
import { useAuth } from './useAuth'

type RegisterAction = (input: RegisterInput) => Promise<unknown>
const registrationFields = ['email', 'password'] as const

function fieldMessage(fields: FieldErrors, field: typeof registrationFields[number]) {
  const value = fields?.[field]
  return Array.isArray(value) ? value.join(' ') : value
}

export function RegisterPage({ register }: { register?: RegisterAction }) {
  const auth = useAuth()
  const form = useForm<RegisterInput>({ resolver: zodResolver(registerSchema) })
  const [success, setSuccess] = useState(false)

  async function submit(input: RegisterInput) {
    setSuccess(false)
    form.clearErrors()
    try {
      await (register ?? auth.register)(input)
      form.reset()
      setSuccess(true)
    } catch (error) {
      if (error instanceof ApiError) {
        for (const field of registrationFields) {
          const message = fieldMessage(error.fields, field)
          if (message) form.setError(field, { type: 'server', message })
        }
        form.setError('root', { type: 'server', message: `${error.code}: ${error.message}` })
      } else {
        form.setError('root', { type: 'server', message: 'Unable to reach the API. Try again.' })
      }
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel" aria-labelledby="register-heading">
        <p className="kicker">Smart Warehouse</p>
        <h1 id="register-heading">Create your account</h1>
        <p>Registration creates a client account. An administrator can update access later.</p>
        {success && <p className="form-success" role="status">Account created. You can sign in now.</p>}
        <form className="auth-form" noValidate onSubmit={form.handleSubmit(submit)}>
          <label htmlFor="register-email">Email</label>
          <input id="register-email" type="email" autoComplete="email" aria-invalid={Boolean(form.formState.errors.email)} {...form.register('email')} />
          {form.formState.errors.email?.message && <span className="form-error">{form.formState.errors.email.message}</span>}
          <label htmlFor="register-password">Password</label>
          <input id="register-password" type="password" autoComplete="new-password" aria-invalid={Boolean(form.formState.errors.password)} {...form.register('password')} />
          {form.formState.errors.password?.message && <span className="form-error">{form.formState.errors.password.message}</span>}
          {form.formState.errors.root?.message && <p className="message" role="alert">{form.formState.errors.root.message}</p>}
          <button disabled={form.formState.isSubmitting}>{form.formState.isSubmitting ? 'Creating account…' : 'Create account'}</button>
        </form>
        <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
      </section>
    </main>
  )
}
