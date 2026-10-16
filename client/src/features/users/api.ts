import type { ApiClient } from '../../shared/api/ApiClient'
import type { UserCreateInput } from './schemas'
import type { ManagedRole, ManagedUser, UserPage } from './types'

export const createUsersApi = (client: ApiClient) => ({
  list: (page: number, pageSize: number) => client.request<UserPage>(`/users?page=${page}&page_size=${pageSize}`),
  create: (input: UserCreateInput) => client.request<ManagedUser>('/users', { method: 'POST', body: JSON.stringify(input) }),
  changeRole: (id: number, role: ManagedRole) => client.request<ManagedUser>(`/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  changeStatus: (id: number, is_active: boolean) => client.request<ManagedUser>(`/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
})
