import type { HTMLAttributes, ReactNode } from 'react'

type FeedbackVariant = 'info' | 'success' | 'warning' | 'error'

type FeedbackMessageProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
  variant?: FeedbackVariant
}

export function FeedbackMessage({ children, className = '', role, variant = 'info', ...props }: FeedbackMessageProps) {
  const classes = ['ui-feedback-message', `ui-feedback-message--${variant}`, className].filter(Boolean).join(' ')
  return <div {...props} className={classes} role={role ?? (variant === 'error' ? 'alert' : 'status')}>{children}</div>
}
