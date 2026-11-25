import { useId } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  hint?: string
  error?: string
  leadingIcon?: ReactNode
}

export function Input({ className = '', error, hint, id, label, leadingIcon, ...props }: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const describedBy = [props['aria-describedby'], error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined].filter(Boolean).join(' ') || undefined
  const classes = ['ui-input', error ? 'ui-input--error' : '', leadingIcon ? 'ui-input--with-icon' : '', className].filter(Boolean).join(' ')

  return <div className="ui-field">
    {label && <label className="ui-field__label" htmlFor={inputId}>{label}</label>}
    <div className="ui-input-shell">
      {leadingIcon && <span aria-hidden="true" className="ui-input-shell__icon">{leadingIcon}</span>}
      <input {...props} aria-describedby={describedBy} aria-invalid={error ? true : props['aria-invalid']} className={classes} id={inputId} />
    </div>
    {error ? <p className="ui-field__error" id={`${inputId}-error`}>{error}</p> : hint && <p className="ui-field__hint" id={`${inputId}-hint`}>{hint}</p>}
  </div>
}
