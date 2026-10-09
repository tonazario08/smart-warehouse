import { useState } from 'react'
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

function UnsupportedMessage({ children }: { children: React.ReactNode }) {
  return <FeedbackMessage className="auth-feedback" variant="warning">{children}</FeedbackMessage>
}

export function LoginPage() {
  const { clearError, error, loading, login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  if (user) return <Navigate replace to="/dashboard" />

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (await login(email, password)) {
      navigate((location.state as { from?: Location } | null)?.from?.pathname ?? '/dashboard', { replace: true })
    }
  }

  return <AuthLayout><section className="auth-card auth-card--login">
    <header className="auth-card__header"><h2>Đăng nhập</h2><p>Truy cập hệ thống quản lý kho thông minh.</p></header>
    {error && <FeedbackMessage className="auth-feedback auth-feedback--login-error" variant="error"><strong>Không thể đăng nhập</strong><span>{error}</span></FeedbackMessage>}
    <form className="auth-form" onSubmit={submit}>
      <Input autoComplete="email" label="Email" onChange={(event) => { clearError(); setEmail(event.target.value) }} placeholder="admin@example.com" required type="email" value={email} />
      <Input autoComplete="current-password" label="Mật khẩu" onChange={(event) => { clearError(); setPassword(event.target.value) }} placeholder="Nhập mật khẩu" required type="password" value={password} />
      <div className="auth-form__options"><span className="auth-form__remember" aria-label="Đăng nhập được duy trì theo cơ chế hiện có"><span aria-hidden="true" className="auth-form__checkbox" />Ghi nhớ đăng nhập</span><Link to="/forgot-password">Quên mật khẩu?</Link></div>
      <Button fullWidth isLoading={loading} loadingLabel="Đang đăng nhập..." type="submit"><span aria-hidden="true" className="auth-button__icon">+</span>Đăng nhập</Button>
    </form>
    <p className="auth-access-note">Bạn cần quyền truy cập? Liên hệ quản trị viên của hệ thống.</p>
  </section></AuthLayout>
}

export function ForgotPasswordPage() {
  const [message, setMessage] = useState('')

  return <AuthLayout><section className="auth-card auth-card--compact">
    <header className="auth-card__header"><h2>Quên mật khẩu</h2><p>Nhập email để nhận hướng dẫn đặt lại mật khẩu.</p></header>
    {message && <UnsupportedMessage>{message}</UnsupportedMessage>}
    <form className="auth-form" onSubmit={(event) => { event.preventDefault(); setMessage('Máy chủ hiện chưa hỗ trợ gửi liên kết đặt lại mật khẩu. Vui lòng liên hệ quản trị viên.') }}>
      <Input autoComplete="email" label="Email" placeholder="admin@example.com" required type="email" />
      <Button fullWidth type="submit"><span aria-hidden="true" className="auth-button__icon">+</span>Gửi liên kết đặt lại mật khẩu</Button>
    </form>
    <Link className="auth-back-link" to="/login">← Quay lại đăng nhập</Link>
  </section></AuthLayout>
}

export function ResetPasswordPage() {
  const [message, setMessage] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setMessage('Mật khẩu mới cần có ít nhất 8 ký tự, bao gồm chữ và số.')
      return
    }
    if (password !== confirmation) {
      setMessage('Xác nhận mật khẩu chưa khớp.')
      return
    }
    setMessage('Máy chủ hiện chưa hỗ trợ đặt lại mật khẩu. Vui lòng liên hệ quản trị viên.')
  }

  return <AuthLayout><section className="auth-card auth-card--reset">
    <header className="auth-card__header"><h2>Đặt lại mật khẩu</h2><p>Tạo mật khẩu mới cho tài khoản của bạn.</p></header>
    {message && <UnsupportedMessage>{message}</UnsupportedMessage>}
    <form className="auth-form" onSubmit={submit}>
      <Input autoComplete="new-password" label="Mật khẩu mới" onChange={(event) => setPassword(event.target.value)} placeholder="Nhập mật khẩu mới" required type="password" value={password} />
      <Input autoComplete="new-password" label="Xác nhận mật khẩu" onChange={(event) => setConfirmation(event.target.value)} placeholder="Nhập lại mật khẩu mới" required type="password" value={confirmation} />
      <div className="auth-password-rules"><span>• Ít nhất 8 ký tự</span><span>• Bao gồm chữ và số</span></div>
      <Button fullWidth type="submit"><span aria-hidden="true" className="auth-button__icon">+</span>Đặt lại mật khẩu</Button>
    </form>
    <Link className="auth-back-link" to="/login">← Quay lại đăng nhập</Link>
  </section></AuthLayout>
}
