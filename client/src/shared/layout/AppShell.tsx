import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../app/AuthProvider'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { Button } from '../ui/Button'

export function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const main = useRef<HTMLElement>(null)
  const toggle = useRef<HTMLButtonElement>(null)
  const sidebar = useRef<HTMLElement>(null)
  const notice = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const denied = location.state?.accessDenied === true
  useEffect(() => { setOpen(false) }, [location.pathname, user?.id, user?.role])
  useEffect(() => {
    if (open) sidebar.current?.querySelector<HTMLElement>('a[href]')?.focus()
  }, [open])
  useEffect(() => {
    if (denied) notice.current?.focus()
  }, [denied, location.key])
  if (!user) return null
  return <div className="app-frame" onKeyDown={event => {
    if (event.key === 'Escape' && open && !event.defaultPrevented) {
      event.preventDefault()
      setOpen(false)
      toggle.current?.focus()
    }
  }}>
    <a className="app-skip-link" href="#app-main-content" onClick={event => {
      event.preventDefault()
      setOpen(false)
      main.current?.focus()
    }}>Bỏ qua điều hướng</a>
    <Sidebar panelRef={sidebar} user={user} onLogout={logout} open={open}
      onNavigate={() => { if (open) { setOpen(false); main.current?.focus() } }} />
    <div className="app-main">
      <Topbar menu={<button ref={toggle} type="button" className="app-menu-toggle" aria-controls="app-navigation-panel"
        aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? 'Đóng menu' : 'Mở menu'}</button>} />
      <main ref={main} id="app-main-content" className="app-content" tabIndex={-1}>
        {denied && <div ref={notice} className="app-denial" tabIndex={-1}>
          <p role="alert">Bạn không có quyền mở trang vừa yêu cầu.</p>
          <p>Bạn đã được đưa về trang được phép. Chọn mục khác từ menu để tiếp tục.</p>
          <Button variant="secondary" size="small" onClick={() => {
            void navigate({ pathname: location.pathname, search: location.search, hash: location.hash }, { replace: true, state: null })
            main.current?.focus()
          }}>Đóng thông báo</Button>
        </div>}
        <Outlet />
      </main>
    </div>
  </div>
}
