interface FormFieldErrorProps {
  id: string
  message?: string
}

export function FormFieldError({ id, message }: FormFieldErrorProps) {
  if (!message) return null

  return <small id={id} className="form-error">{message}</small>
}
