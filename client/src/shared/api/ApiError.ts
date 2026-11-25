import type { FieldErrors } from './types'

type ErrorPayload = {
  detail?: unknown
}

type ErrorDetail = {
  code?: unknown
  message?: unknown
  fields?: unknown
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields: FieldErrors,
    readonly detail: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }

  static fromResponse(status: number, payload: unknown): ApiError {
    const detail = isRecord(payload) ? (payload as ErrorPayload).detail : undefined
    const data = isRecord(detail) ? (detail as ErrorDetail) : undefined
    const plainMessage = typeof detail === 'string' ? detail : undefined

    return new ApiError(
      status,
      typeof data?.code === 'string' ? data.code : 'UNEXPECTED_RESPONSE',
      typeof data?.message === 'string' ? data.message : plainMessage ?? 'The request could not be completed.',
      isRecord(data?.fields) ? data.fields as FieldErrors : null,
      detail,
    )
  }
}
