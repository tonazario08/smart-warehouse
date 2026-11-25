import type { ReactNode } from 'react'

export type AsyncStatus = 'loading' | 'error' | 'empty' | 'success'

interface AsyncStateProps {
  status: AsyncStatus
  children?: ReactNode
  error?: ReactNode
  emptyMessage?: ReactNode
  loadingMessage?: ReactNode
}

export function AsyncState({
  status,
  children,
  error = 'Records could not be loaded.',
  emptyMessage = 'No records to show yet.',
  loadingMessage = 'Loading records',
}: AsyncStateProps) {
  if (status === 'loading') return <p className="async-state" role="status" aria-live="polite">{loadingMessage}</p>
  if (status === 'error') return <p className="async-state async-state-error" role="alert">{error}</p>
  if (status === 'empty') return <p className="async-state async-state-empty">{emptyMessage}</p>
  return <>{children}</>
}
