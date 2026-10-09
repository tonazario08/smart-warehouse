import type { HTMLAttributes, ReactNode } from 'react'

type BadgeVariant = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  children: ReactNode
  variant?: BadgeVariant
}

export function Badge({ children, className = '', variant = 'neutral', ...props }: BadgeProps) {
  const classes = ['ui-badge', `ui-badge--${variant}`, className].filter(Boolean).join(' ')
  return <span {...props} className={classes}>{children}</span>
}
