import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../../shared/api/ApiError'
import { loginSchema, type LoginInput } from './schemas'
import { landingPathForRole } from '../../app/navigation'
import { useAuth } from './useAuth'

interface LoginLocationState {
  from?: { pathname?: string; search?: string; hash?: string }
  notice?: string
}

function destinationFromState(state: LoginLocationState | null, role: Parameters<typeof landingPathForRole>[0]) {
  const path = state?.from?.pathname
  if (!path?.startsWith('/') || path.startsWith('//')) return landingPathForRole(role)
  return `${path}${state?.from?.search ?? ''}${state?.from?.hash ?? ''}`
}

export function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LoginLocationState | null
  const form = useForm<LoginInput>({ resolver: zodResolver(loginSchema) })

  async function submit(input: LoginInput) {
    form.clearErrors('root')
    try {
      const user = await auth.login(input)
      navigate(destinationFromState(state, user.role), { replace: true })
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null
      form.setError('root', {
        type: 'server',
        message: apiError ? `${apiError.code}: ${apiError.message}` : 'Unable to reach the API. Try again.',
      })
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel" aria-labelledby="login-heading">
        <p className="kicker">Smart Warehouse</p>
        <h1 id="login-heading">Sign in</h1>
        <p>Use your warehouse account to continue.</p>
        {state?.notice && <p className="form-success" role="status">{state.notice}</p>}
        <form className="auth-form" noValidate onSubmit={form.handleSubmit(submit)}>
          <label htmlFor="login-email">Email</label>
          <input id="login-email" type="email" autoComplete="username" aria-invalid={Boolean(form.formState.errors.email)} {...form.register('email')} />
          {form.formState.errors.email?.message && <span className="form-error">{form.formState.errors.email.message}</span>}
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" autoComplete="current-password" aria-invalid={Boolean(form.formState.errors.password)} {...form.register('password')} />
          {form.formState.errors.password?.message && <span className="form-error">{form.formState.errors.password.message}</span>}
          {form.formState.errors.root?.message && <p className="message" role="alert">{form.formState.errors.root.message}</p>}
          <button disabled={form.formState.isSubmitting}>{form.formState.isSubmitting ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p className="auth-switch">Need an account? <Link to="/register">Register</Link></p>
      </section>
    </main>
  )
}
