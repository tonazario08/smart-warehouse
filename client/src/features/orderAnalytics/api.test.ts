import { expect, it, vi } from 'vitest'
import { request } from '../../api'
import { getOrderWarehouses } from './api'

vi.mock('../../api')

it('loads beyond the first page of warehouses, retaining numeric IDs', async () => {
  const first = Array.from({ length: 100 }, (_, i) => ({ id: i + 1, code: 'W' + (i + 1), name: 'Warehouse' }))
  vi.mocked(request).mockResolvedValueOnce({ items: first, total: 101, page: 1, page_size: 100 })
    .mockResolvedValueOnce({ items: [{ id: 101, code: 'W101', name: 'Last warehouse' }], total: 101, page: 2, page_size: 100 })
  const signal = new AbortController().signal
  const options = await getOrderWarehouses('t', signal)
  expect(options).toHaveLength(101)
  expect(options.at(-1)).toMatchObject({ id: 101, code: 'W101' })
  expect(request).toHaveBeenNthCalledWith(1, '/warehouses?page=1&page_size=100', { signal }, 't')
  expect(request).toHaveBeenNthCalledWith(2, '/warehouses?page=2&page_size=100', { signal }, 't')
})
