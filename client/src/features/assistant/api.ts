import { ApiError, request } from '../../api'

export type Citation = { section_id: string; title: string; version: string; url: string }
export type AssistantReply = { status: 'answered' | 'insufficient_context'; answer: string; citations: Citation[] }
export type AssistantSource = Omit<Citation, 'url'> & { content: string }

export function askAssistant(token: string, question: string, signal: AbortSignal) {
  return request<AssistantReply>('/assistant/chat', { method: 'POST', body: JSON.stringify({ question }), signal }, token)
}

export function getAssistantSource(token: string, citation: Citation, signal: AbortSignal) {
  const id = encodeURIComponent(citation.section_id)
  const query = new URLSearchParams({ version: citation.version })
  return request<AssistantSource>(`/assistant/sources/${id}?${query}`, { signal }, token)
}

const messages: Record<string, string> = {
  ASSISTANT_INVALID_QUESTION: 'Nhập câu hỏi trong giới hạn độ dài cho phép.',
  ASSISTANT_RATE_LIMIT: 'Bạn đã hết lượt hỏi. Vui lòng thử lại sau.',
  ASSISTANT_NOT_CONFIGURED: 'Trợ lý kho hiện chưa được bật.',
  ASSISTANT_TIMEOUT: 'Trợ lý phản hồi quá thời gian. Vui lòng thử lại.',
  ASSISTANT_PROVIDER_ERROR: 'Không thể kết nối trợ lý. Vui lòng thử lại.',
  ASSISTANT_SOURCE_NOT_FOUND: 'Nguồn này không còn khả dụng. Hãy gửi lại câu hỏi để lấy nguồn mới.',
}

export function assistantError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code && messages[error.code]) return messages[error.code]
    if (error.status === 403) return 'Bạn không có quyền sử dụng trợ lý kho.'
    if (error.status === 422) return messages.ASSISTANT_INVALID_QUESTION
  }
  return 'Trợ lý kho hiện chưa khả dụng. Vui lòng thử lại.'
}
