import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  description?: string
  eyebrow?: string
  actions?: ReactNode
}

export function PageHeader({ actions, description, eyebrow, title }: PageHeaderProps) {
  return <header className="ui-page-header">
    <div>
      {eyebrow && <p className="ui-page-header__eyebrow">{eyebrow}</p>}
      <h1 className="ui-page-header__title">{title}</h1>
      {description && <p className="ui-page-header__description">{description}</p>}
    </div>
    {actions && <div className="ui-page-header__actions">{actions}</div>}
  </header>
}
