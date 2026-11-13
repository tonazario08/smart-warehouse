import { useEffect, useState } from 'react'
import { ApiError, request } from '../api'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../app/AuthProvider'
import warehouseIcon from '../shared/assets/figma/warehouse.svg'
import { Button } from '../shared/ui/Button'
import { FeedbackMessage } from '../shared/ui/FeedbackMessage'
import { Input } from '../shared/ui/Input'
import './auth.css'

function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main className="auth-page">
    <aside className="auth-brand" aria-label="Kho thông minh">
      <div className="auth-brand__mark"><img alt="" height="22" src={warehouseIcon} width="22" /></div>
      <div className="auth-brand__name"><strong>Kho thông minh</strong><span>Nền tảng vận hành kho</span></div>
      <div className="auth-brand__message"><h1>Vận hành kho rõ ràng, chính xác và nhất quán.</h1><p>Quản lý sản phẩm, tồn kho, nhập xuất và hoạt động kho hàng trên một hệ thống duy nhất.</p></div>
      <p className="auth-brand__footer">Kho thông minh · Hệ thống quản lý kho vận</p>
    </aside>
    <section className="auth-content">{children}</section>
  </main>
}

export function LoginPage() {
  const { clearError, error, loading, login, passwordChanged, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const from = (location.state as { from?: { pathname?: string; search?: string; hash?: string } } | null)?.from
  const destination = !passwordChanged && from?.pathname?.startsWith('/') && !from.pathname.startsWith('//')
    ? from.pathname + (from.search ?? '') + (from.hash ?? '')
    : '/dashboard'

  if (user) return <Navigate replace to={destination} />

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (await login(email, password)) {
      navigate(destination, { replace: true })
    }
  }

  return <AuthLayout><section className={`auth-card auth-card--login${error ? ' auth-card--login-error' : ''}`}>
    <header className="auth-card__header"><h2>Đăng nhập</h2><p>Truy cập hệ thống quản lý kho thông minh.</p></header>
    {passwordChanged && <FeedbackMessage className="auth-feedback" variant="success">Mật khẩu đã được thay đổi thành công. Vui lòng đăng nhập lại.</FeedbackMessage>}
    {error && <FeedbackMessage className="auth-feedback auth-feedback--login-error" variant="error"><strong>Không thể đăng nhập</strong><span>{error}</span></FeedbackMessage>}
    <form className="auth-form" onSubmit={submit}>
      <Input autoComplete="email" label="Email" onChange={(event) => { clearError(); setEmail(event.target.value) }} placeholder="admin@example.com" required type="email" value={email} />
      <Input autoComplete="current-password" label="Mật khẩu" onChange={(event) => { clearError(); setPassword(event.target.value) }} placeholder="Nhập mật khẩu" required type="password" value={password} />
      <div className="auth-form__options"><Link to="/forgot-password">Quên mật khẩu?</Link></div>
      <Button fullWidth isLoading={loading} loadingLabel="Đang đăng nhập..." type="submit"><span aria-hidden="true" className="auth-button__icon">+</span>Đăng nhập</Button>
    </form>
    <p className="auth-access-note">Bạn cần quyền truy cập? Liên hệ quản trị viên của hệ thống.</p>
  </section></AuthLayout>
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [sent, setSent] = useState(false)
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy) return
    setBusy(true); setError(''); setSent(false)
    try { await request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }); setSent(true) }
    catch (cause) { setError(cause instanceof ApiError && cause.status === 503 ? 'Dịch vụ khôi phục mật khẩu hiện chưa khả dụng. Vui lòng thử lại sau.' : 'Không thể gửi yêu cầu. Vui lòng thử lại sau.') }
    finally { setBusy(false) }
  }
  return <AuthLayout><section className="auth-card auth-card--compact">
    <header className="auth-card__header"><h2>Quên mật khẩu</h2><p>Nhập email để nhận liên kết đặt lại mật khẩu.</p></header>
    {sent && <FeedbackMessage className="auth-feedback" variant="success">Nếu email thuộc một tài khoản đang hoạt động, bạn sẽ nhận được liên kết đặt lại mật khẩu.</FeedbackMessage>}
    {error && <FeedbackMessage className="auth-feedback" variant="error">{error}</FeedbackMessage>}
    <form className="auth-form" onSubmit={submit}><Input autoComplete="email" label="Email" onChange={event => setEmail(event.target.value)} required type="email" value={email} /><Button fullWidth isLoading={busy} loadingLabel="Đang gửi..." type="submit">Gửi liên kết</Button></form>
    <Link className="auth-back-link" to="/login">← Quay lại đăng nhập</Link>
  </section></AuthLayout>
}

const passwordErrorMessages: Record<string, string> = {
  CURRENT_PASSWORD_INVALID: 'Mật khẩu hiện tại không chính xác.',
  PASSWORD_REUSE: 'Mật khẩu mới phải khác mật khẩu hiện tại.',
  PASSWORD_CONFIRMATION_MISMATCH: 'Mật khẩu xác nhận không khớp.',
  INVALID_RESET_TOKEN: 'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.',
  PASSWORD_RECOVERY_UNAVAILABLE: 'Dịch vụ khôi phục mật khẩu hiện chưa khả dụng.',
}

function PasswordForm({ mode, resetToken }: { mode: 'reset'; resetToken: string } | { mode: 'change'; resetToken?: never }) {
  const { capturePasswordChange, token: sessionToken } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState(''), [password, setPassword] = useState(''), [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy) return
    const length = Array.from(password).length
    if (length < 12 || length > 128) { setError('Mật khẩu mới phải có từ 12 đến 128 ký tự.'); return }
    if (password !== confirm) { setError('Mật khẩu xác nhận không khớp.'); return }
    const finishSession = capturePasswordChange()
    setBusy(true); setError('')
    try {
      const body = mode === 'reset' ? { token: resetToken, new_password: password, confirm_password: confirm } : { current_password: current, new_password: password, confirm_password: confirm }
      await request('/auth/' + (mode === 'reset' ? 'reset-password' : 'change-password'), { method: 'POST', body: JSON.stringify(body) }, mode === 'change' ? sessionToken ?? undefined : undefined)
      if (finishSession()) navigate('/login', { replace: true })
    } catch (cause) {
      const message = cause instanceof ApiError ? passwordErrorMessages[cause.code] : undefined
      setError(message ?? 'Không thể thay đổi mật khẩu. Vui lòng kiểm tra thông tin và thử lại.')
    } finally { setBusy(false) }
  }
  return <>
    {error && <FeedbackMessage className="auth-feedback" variant="error">{error}</FeedbackMessage>}
    <form className="auth-form" onSubmit={submit}>
      {mode === 'change' && <Input autoComplete="current-password" label="Mật khẩu hiện tại" onChange={event => setCurrent(event.target.value)} required type="password" value={current} />}
      <Input autoComplete="new-password" label="Mật khẩu mới" hint="Từ 12 đến 128 ký tự." onChange={event => setPassword(event.target.value)} required type="password" value={password} />
      <Input autoComplete="new-password" label="Xác nhận mật khẩu mới" onChange={event => setConfirm(event.target.value)} required type="password" value={confirm} />
      <Button fullWidth isLoading={busy} loadingLabel="Đang xử lý..." type="submit">{mode === 'reset' ? 'Đặt lại mật khẩu' : 'Đổi mật khẩu'}</Button>
    </form>
  </>
}

export function ResetPasswordPage() {
  const { hash } = useLocation()
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(hash.slice(1)).get('token'))
  useEffect(() => {
    if (!hash) return
    setResetToken(new URLSearchParams(hash.slice(1)).get('token'))
    if (window.location.hash === hash) {
      window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    }
  }, [hash])
  return <AuthLayout><section className="auth-card auth-card--reset">
    <header className="auth-card__header"><h2>Đặt lại mật khẩu</h2><p>Nhập mật khẩu mới cho tài khoản của bạn.</p></header>
    {resetToken
      ? <PasswordForm key={resetToken} mode="reset" resetToken={resetToken} />
      : <><FeedbackMessage className="auth-feedback" variant="error">Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.</FeedbackMessage><Link className="auth-back-link" to="/forgot-password">Yêu cầu liên kết mới</Link></>}
    <Link className="auth-back-link" to="/login">← Quay lại đăng nhập</Link>
  </section></AuthLayout>
}

export function ChangePasswordPage() {
  return <section className="auth-card"><header className="auth-card__header"><h2>Đổi mật khẩu</h2><p>Sau khi đổi mật khẩu, bạn cần đăng nhập lại.</p></header><PasswordForm mode="change" /></section>
}
