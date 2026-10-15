import { useId } from 'react'
import type { SelectHTMLAttributes } from 'react'

export type SelectOption = {
  label: string
  value: string | number
  disabled?: boolean
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> & {
  label?: string
  hint?: string
  error?: string
  options: SelectOption[]
  placeholder?: string
}

export function Select({ className = '', error, hint, id, label, options, placeholder = 'Chọn một mục', ...props }: SelectProps) {
  const generatedId = useId()
  const selectId = id ?? generatedId
  const describedBy = [props['aria-describedby'], error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined].filter(Boolean).join(' ') || undefined
  const classes = ['ui-select', error ? 'ui-select--error' : '', className].filter(Boolean).join(' ')

  return <div className="ui-field">
    {label && <label className="ui-field__label" htmlFor={selectId}>{label}</label>}
    <select {...props} aria-describedby={describedBy} aria-invalid={error ? true : props['aria-invalid']} className={classes} id={selectId}>
      <option value="">{placeholder}</option>
      {options.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
    </select>
    {error ? <p className="ui-field__error" id={`${selectId}-error`}>{error}</p> : hint && <p className="ui-field__hint" id={`${selectId}-hint`}>{hint}</p>}
  </div>
}
