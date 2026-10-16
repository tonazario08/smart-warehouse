import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/ApiError'
import { AuthProvider } from './AuthProvider'
import { registerSchema, type RegisterInput } from './schemas'
import { RegisterPage } from './RegisterPage'

function renderRegister(register: (input: RegisterInput) => Promise<unknown>) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <MemoryRouter><RegisterPage register={register} /></MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('public registration', () => {
  it('normalizes email and submits only email and password', async () => {
    const user = userEvent.setup()
    const register = vi.fn().mockResolvedValue({ id: 4, email: 'new@example.com', role: 'client', is_active: true })
    renderRegister(register)

    await user.type(screen.getByLabelText('Email'), '  NEW@Example.com  ')
    await user.type(screen.getByLabelText('Password'), 'strong-password')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(register).toHaveBeenCalledWith({ email: 'new@example.com', password: 'strong-password' })
    expect(register.mock.calls[0]?.[0]).not.toHaveProperty('role')
    expect(await screen.findByRole('status')).toHaveTextContent(/account created/i)
  })

  it('rejects a role field in the strict registration schema', () => {
    const result = registerSchema.safeParse({
      email: 'new@example.com', password: 'strong-password', role: 'admin',
    })

    expect(result.success).toBe(false)
  })

  it('maps backend field errors to controls and preserves the backend code and message', async () => {
    const user = userEvent.setup()
    const register = vi.fn().mockRejectedValue(new ApiError(
      409,
      'USER_EMAIL_CONFLICT',
      'Email is already registered.',
      { email: ['Choose another email address.'] },
      null,
    ))
    renderRegister(register)

    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password'), 'strong-password')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Choose another email address.')).toBeInTheDocument()
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('USER_EMAIL_CONFLICT')
    expect(alert).toHaveTextContent('Email is already registered.')
  })

  it('shows local password validation before making a registration request', async () => {
    const user = userEvent.setup()
    const register = vi.fn()
    renderRegister(register)

    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText(/at least 12 characters/i)).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })
})
