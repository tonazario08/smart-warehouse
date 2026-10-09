import { useId } from 'react'
import type { InputHTMLAttributes } from 'react'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  hint?: string
  error?: string
}

export function Input({ className = '', error, hint, id, label, ...props }: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined
  const classes = ['ui-input', error ? 'ui-input--error' : '', className].filter(Boolean).join(' ')

  return <div className="ui-field">
    {label && <label className="ui-field__label" htmlFor={inputId}>{label}</label>}
    <input {...props} aria-describedby={describedBy} aria-invalid={Boolean(error)} className={classes} id={inputId} />
    {error ? <p className="ui-field__error" id={`${inputId}-error`}>{error}</p> : hint && <p className="ui-field__hint" id={`${inputId}-hint`}>{hint}</p>}
  </div>
}
