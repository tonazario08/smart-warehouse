import type { ReactNode } from 'react'
import type { NavigationItem } from './navigation'

interface AppShellProps {
  title: string
  activePath: string
  navigationItems: NavigationItem[]
  children: ReactNode
  utility?: ReactNode
}

export function AppShell({ title, activePath, navigationItems, children, utility }: AppShellProps) {
  return (
    <div className="application-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <a className="shell-brand" href="/" aria-label="Smart Warehouse home">
        <span className="brand-mark" aria-hidden="true">SW</span>
        <span>Smart Warehouse</span>
      </a>
      <header className="utility-header">
        <h1>{title}</h1>
        <div className="utility-controls">{utility}</div>
      </header>
      <aside className="route-rail">
        <nav aria-label="Primary navigation">
          <ul>
            {navigationItems.map((item) => {
              const isCurrent = activePath === item.href
              return (
                <li key={item.href}>
                  <a className="route-link" href={item.href} aria-current={isCurrent ? 'page' : undefined}>
                    {item.label}
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>
      <main id="main-content" className="shell-content" tabIndex={-1}>{children}</main>
    </div>
  )
}
