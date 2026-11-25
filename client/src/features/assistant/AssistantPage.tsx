import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useAuth } from '../../app/AuthProvider'
import { Button } from '../../shared/ui/Button'
import { FeedbackMessage } from '../../shared/ui/FeedbackMessage'
import { PageHeader } from '../../shared/ui/PageHeader'
import { askAssistant, assistantError, getAssistantSource } from './api'
import type { AssistantReply, AssistantSource, Citation } from './api'
import './assistant.css'

const suggestions = [
  'Tôi ghi nhận nhập hàng vào kho thế nào?',
  'Cách chuyển hàng giữa hai kho?',
  'Điểm đặt hàng lại là gì?',
]
const questionLimit = 1000
type Exchange = { id: number; question: string; reply?: AssistantReply; error?: string }
type SourceState = { citation: Citation; document?: AssistantSource; error?: string }

export function AssistantPage() {
  const { token, user } = useAuth()
  if (!token || !user) return null
  return <AssistantSession key={token} token={token} />
}

function AssistantSession({ token }: { token: string }) {
  const [draft, setDraft] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [questionError, setQuestionError] = useState('')
  const [pending, setPending] = useState(false)
  const [source, setSource] = useState<SourceState | null>(null)
  const questionRequest = useRef<AbortController | null>(null)
  const sourceRequest = useRef<AbortController | null>(null)
  const nextId = useRef(0)
  const sourceHeading = useRef<HTMLHeadingElement>(null)
  const sourceTrigger = useRef<HTMLButtonElement | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const inputId = useId()
  const sourceId = useId()

  useEffect(() => () => {
    questionRequest.current?.abort()
    sourceRequest.current?.abort()
  }, [])

  async function submit(question: string, retryId?: number) {
    if (questionRequest.current) return
    if (!question || Array.from(question).length > questionLimit) {
      setQuestionError('Nhập câu hỏi từ 1 đến 1.000 ký tự.')
      input.current?.focus()
      return
    }
    const id = retryId ?? ++nextId.current
    setQuestionError('')
    if (retryId === undefined) {
      setDraft('')
      setExchanges(current => [...current, { id, question }])
    } else {
      setExchanges(current => current.map(item => item.id === id ? { id, question } : item))
    }
    const controller = new AbortController()
    questionRequest.current = controller
    setPending(true)
    try {
      const reply = await askAssistant(token, question, controller.signal)
      if (!controller.signal.aborted) setExchanges(current => current.map(item => item.id === id ? { ...item, reply } : item))
    } catch (error) {
      if (!controller.signal.aborted) setExchanges(current => current.map(item => item.id === id ? { ...item, error: assistantError(error) } : item))
    } finally {
      if (!controller.signal.aborted) {
        questionRequest.current = null
        setPending(false)
      }
    }
  }

  async function showSource(citation: Citation, trigger: HTMLButtonElement) {
    sourceRequest.current?.abort()
    const controller = new AbortController()
    sourceRequest.current = controller
    sourceTrigger.current = trigger
    setSource({ citation })
    try {
      const document = await getAssistantSource(token, citation, controller.signal)
      if (!controller.signal.aborted) setSource({ citation, document })
    } catch (error) {
      if (!controller.signal.aborted) setSource({ citation, error: assistantError(error) })
    }
  }

  const selectedSection = source?.citation.section_id
  useEffect(() => {
    if (selectedSection) sourceHeading.current?.focus()
  }, [selectedSection])

  function closeSource() {
    sourceRequest.current?.abort()
    setSource(null)
    sourceTrigger.current?.focus()
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submit(draft.trim())
  }

  return <div className="assistant">
    <PageHeader title="Trợ lý kho" description="Hỏi về quy trình kho, dự báo và bổ sung hàng. Mở nguồn để đối chiếu câu trả lời." />
    <div className="assistant__layout" data-source-open={Boolean(source)}>
      <section className="assistant__panel" aria-label="Hội thoại">
        {exchanges.length === 0 && <div className="assistant__suggestions">
          <h2>Bạn muốn tìm hiểu gì?</h2>
          {suggestions.map(question => <Button key={question} variant="secondary" onClick={() => { setDraft(question); setQuestionError(''); input.current?.focus() }}>{question}</Button>)}
        </div>}
        <ol className="assistant__messages" aria-label="Câu hỏi và câu trả lời" aria-live="polite">
          {exchanges.map(item => <li key={item.id} className="assistant__exchange">
            <div className="assistant__question"><strong>Bạn</strong><p>{item.question}</p></div>
            {item.reply && <div className="assistant__answer"><strong>Trợ lý kho</strong>
              <p>{item.reply.answer}</p>
              {item.reply.citations.length > 0 && <ul className="assistant__citations" aria-label="Nguồn tham khảo">{item.reply.citations.map(citation => <li key={citation.section_id}>
                <Button variant="secondary" size="small" onClick={event => void showSource(citation, event.currentTarget)}>{citation.title}</Button>
              </li>)}</ul>}
            </div>}
            {item.error && <div className="assistant__failure">
              <FeedbackMessage variant="error">{item.error}</FeedbackMessage>
              <Button variant="secondary" size="small" disabled={pending} onClick={() => void submit(item.question, item.id)}>Thử lại</Button>
            </div>}
          </li>)}
        </ol>
        {pending && <p className="assistant__pending" role="status">Đang tìm tài liệu và soạn câu trả lời…</p>}
        <form className="assistant__composer" onSubmit={handleSubmit}>
          <label htmlFor={inputId}>Câu hỏi</label>
          <textarea id={inputId} ref={input} className="ui-input assistant__input" rows={3} value={draft} aria-invalid={Boolean(questionError)} aria-describedby={questionError ? `${inputId}-error` : undefined} onChange={event => { setDraft(event.target.value); setQuestionError('') }} />
          {questionError && <FeedbackMessage id={`${inputId}-error`} variant="error">{questionError}</FeedbackMessage>}
          <Button type="submit" disabled={pending}>Gửi câu hỏi</Button>
        </form>
      </section>
      {source && <section className="assistant__panel assistant__source" aria-labelledby={sourceId}>
        <div className="assistant__source-header">
          <h2 id={sourceId} ref={sourceHeading} tabIndex={-1}>{source.citation.title}</h2>
          <Button size="small" variant="secondary" onClick={closeSource}>Đóng nguồn</Button>
        </div>
        {source.error
          ? <FeedbackMessage variant="error">{source.error}</FeedbackMessage>
          : source.document
            ? <><p className="assistant__source-version">Phiên bản {source.document.version}</p><p className="assistant__source-content">{source.document.content}</p></>
            : <p role="status">Đang tải nguồn…</p>}
      </section>}
    </div>
  </div>
}
