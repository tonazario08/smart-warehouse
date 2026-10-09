import type { ReactNode } from 'react'

type EmptyStateProps = {
  title?: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ action, description = 'Dữ liệu sẽ xuất hiện tại đây khi có sẵn.', title = 'Chưa có dữ liệu' }: EmptyStateProps) {
  return <section className="ui-empty-state">
    <h2 className="ui-empty-state__title">{title}</h2>
    <p className="ui-empty-state__description">{description}</p>
    {action}
  </section>
}
