import { describe, expect, it } from 'vitest'
import { ApiError } from '../shared/api/ApiError'
import { queryClient } from './Providers'

describe('query provider defaults', () => {
  it('does not retry client errors and retries transient failures once', () => {
    const retry = queryClient.getDefaultOptions().queries?.retry
    expect(typeof retry).toBe('function')
    if (typeof retry !== 'function') throw new Error('Expected a query retry policy')

    expect(retry(0, new ApiError(403, 'PERMISSION_DENIED', 'Forbidden', null, null))).toBe(false)
    expect(retry(0, new ApiError(503, 'SERVICE_UNAVAILABLE', 'Try again', null, null))).toBe(true)
    expect(retry(1, new Error('Network unavailable'))).toBe(false)
  })
})
