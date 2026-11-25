import type { ApiClient } from '../../shared/api/ApiClient'
import type { LoginInput, RegisterInput, TokenResponse, User } from './types'

export function createAuthApi(client: ApiClient) {
  return {
    register: (input: RegisterInput) => client.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
    login: (input: LoginInput) => client.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
    me: () => client.request<User>('/auth/me'),
  }
}

export type AuthApi = ReturnType<typeof createAuthApi>
