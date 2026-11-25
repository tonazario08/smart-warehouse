import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { AssistantPage } from './AssistantPage'
import { askAssistant, getAssistantSource } from './api'

const session = vi.hoisted(() => ({ token: 'first-session', user: { id: 1 } }))
vi.mock('../../app/AuthProvider', () => ({ useAuth: () => session }))
vi.mock('./api', () => ({ askAssistant: vi.fn(), getAssistantSource: vi.fn(), assistantError: () => 'Trợ lý chưa trả lời được.' }))

const citation = { section_id: 'transfer', title: 'Chuyển kho', version: '1', url: '/api/v1/assistant/sources/transfer' }
const reply = { status: 'answered' as const, answer: 'Mở mục Chuyển kho.', citations: [citation] }

beforeEach(() => {
  vi.resetAllMocks()
  session.token = 'first-session'
  session.user.id = 1
})

it('sends a Vietnamese question and opens the cited source', async () => {
  vi.mocked(askAssistant).mockResolvedValue(reply)
  vi.mocked(getAssistantSource).mockResolvedValue({ ...citation, content: 'Nội dung nguồn đã duyệt.' })
  const user = userEvent.setup()
  render(<AssistantPage />)
  await user.type(screen.getByLabelText('Câu hỏi'), 'Chuyển kho thế nào?')
  await user.click(screen.getByRole('button', { name: 'Gửi câu hỏi' }))
  expect(await screen.findByText(reply.answer)).toBeInTheDocument()
  expect(vi.mocked(askAssistant).mock.calls[0]?.slice(0, 2)).toEqual(['first-session', 'Chuyển kho thế nào?'])
  await user.click(screen.getByRole('button', { name: 'Chuyển kho' }))
  expect(await screen.findByText('Nội dung nguồn đã duyệt.')).toBeInTheDocument()
})

it('retries the same question without adding a duplicate', async () => {
  vi.mocked(askAssistant).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(reply)
  const user = userEvent.setup()
  render(<AssistantPage />)
  await user.type(screen.getByLabelText('Câu hỏi'), 'Tôi cần hướng dẫn.')
  await user.click(screen.getByRole('button', { name: 'Gửi câu hỏi' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Trợ lý chưa trả lời được.')
  await user.click(screen.getByRole('button', { name: 'Thử lại' }))
  expect(await screen.findByText(reply.answer)).toBeInTheDocument()
  expect(screen.getAllByText('Tôi cần hướng dẫn.')).toHaveLength(1)
})

it('drops pending responses when the account changes', async () => {
  let resolveReply!: (value: typeof reply) => void
  const pending = new Promise<typeof reply>(resolve => { resolveReply = resolve })
  vi.mocked(askAssistant).mockReturnValue(pending)
  const user = userEvent.setup()
  const { rerender } = render(<AssistantPage />)
  await user.type(screen.getByLabelText('Câu hỏi'), 'Câu hỏi phiên cũ')
  await user.click(screen.getByRole('button', { name: 'Gửi câu hỏi' }))
  expect(screen.getByRole('status')).toHaveTextContent('Đang tìm tài liệu')
  session.token = 'second-session'
  session.user.id = 2
  rerender(<AssistantPage />)
  await act(() => { resolveReply(reply); return pending })
  expect(screen.queryByText('Câu hỏi phiên cũ')).not.toBeInTheDocument()
  expect(screen.queryByText(reply.answer)).not.toBeInTheDocument()
})
