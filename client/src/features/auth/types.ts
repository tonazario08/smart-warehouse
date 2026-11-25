import type { ApiClient } from '../../shared/api/ApiClient'

export type Role = 'admin' | 'warehouse' | 'client'

export interface User {
  id: number
  email: string
  role: Role
  is_active: boolean
}

export interface RegisterInput {
  email: string
  password: string
}

export interface LoginInput {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  login: (input: LoginInput) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  logout: () => void
  client: ApiClient
}
