import type { ButtonHTMLAttributes, ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'small' | 'medium' | 'large'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  isLoading?: boolean
  loadingLabel?: string
}

export function Button({
  children,
  className = '',
  variant = 'primary',
  size = 'medium',
  fullWidth = false,
  isLoading = false,
  loadingLabel = 'Đang xử lý...',
  disabled,
  type = 'button',
  ...props
}: ButtonProps) {
  const classes = [
    'ui-button',
    `ui-button--${variant}`,
    `ui-button--${size}`,
    fullWidth ? 'ui-button--full-width' : '',
    className,
  ].filter(Boolean).join(' ')

  return <button {...props} className={classes} disabled={disabled || isLoading} type={type}>{isLoading ? loadingLabel : children}</button>
}
