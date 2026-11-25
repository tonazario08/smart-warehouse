import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Button } from './Button'

type ConfirmDialogProps = {
  open: boolean
  busy?: boolean
  title?: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  confirmVariant?: 'primary' | 'danger'
  onConfirm: () => void
  onCancel: () => void
  children?: ReactNode
}

export function ConfirmDialog({
  busy = false,
  cancelLabel = 'Hủy',
  children,
  confirmLabel = 'Xác nhận',
  confirmVariant = 'primary',
  description = 'Thao tác này sẽ được áp dụng ngay khi bạn xác nhận.',
  onCancel,
  onConfirm,
  open,
  title = 'Xác nhận thao tác',
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const interactionLocked = useRef(false)
  const backdropPressed = useRef(false)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog || !open) return
    const trigger = dialog.ownerDocument.activeElement as HTMLElement | null
    interactionLocked.current = false
    backdropPressed.current = false
    if (!dialog.open) dialog.showModal()
    // Start with the non-destructive action, and let the native modal contain focus.
    dialog.querySelector<HTMLButtonElement>('[data-dialog-cancel]')?.focus()
    return () => {
      if (dialog.open) dialog.close()
      if (trigger?.isConnected) trigger.focus()
    }
  }, [open])

  useEffect(() => {
    if (!busy) interactionLocked.current = false
    const dialog = dialogRef.current
    if (open && busy) dialog?.focus()
    else if (open && dialog && dialog.ownerDocument.activeElement === dialog) dialog.querySelector<HTMLButtonElement>('[data-dialog-cancel]')?.focus()
  }, [busy, open])

  const cancel = () => {
    if (busy || interactionLocked.current) return
    interactionLocked.current = true
    onCancel()
  }
  const confirm = () => {
    if (busy || interactionLocked.current) return
    interactionLocked.current = true
    try { onConfirm() } catch (cause) { interactionLocked.current = false; throw cause }
  }
  const outside = (event: React.MouseEvent<HTMLDialogElement> | React.PointerEvent<HTMLDialogElement>) => {
    if (event.target !== event.currentTarget) return false
    const bounds = event.currentTarget.getBoundingClientRect()
    return event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom
  }

  return <dialog aria-busy={busy} aria-describedby={descriptionId} aria-labelledby={titleId} aria-modal="true" className="ui-confirm-dialog" ref={dialogRef} tabIndex={-1}
    onCancel={(event) => { event.preventDefault(); cancel() }}
    onClose={(event) => { if (open && !event.currentTarget.open) { if (busy) event.currentTarget.showModal(); else cancel() } }}
    onPointerDown={(event) => { backdropPressed.current = outside(event) }}
    onPointerCancel={() => { backdropPressed.current = false }}
    onClick={(event) => { const shouldCancel = backdropPressed.current && outside(event); backdropPressed.current = false; if (shouldCancel) cancel() }}>
    <div className="ui-confirm-dialog__content">
      <h2 className="ui-confirm-dialog__title" id={titleId}>{title}</h2>
      <p className="ui-confirm-dialog__description" id={descriptionId}>{description}</p>
      {children}
      <div className="ui-confirm-dialog__actions">
        <Button data-dialog-cancel="" disabled={busy} onClick={cancel} variant="secondary">{cancelLabel}</Button>
        <Button disabled={busy} onClick={confirm} variant={confirmVariant}>{confirmLabel}</Button>
      </div>
    </div>
  </dialog>
}
