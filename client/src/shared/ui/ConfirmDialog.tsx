import type { ReactNode } from 'react'
import { Button } from './Button'

type ConfirmDialogProps = {
  open: boolean
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
  return <dialog aria-labelledby="confirm-dialog-title" className="ui-confirm-dialog" open={open} onCancel={onCancel}>
    <div className="ui-confirm-dialog__content">
      <h2 className="ui-confirm-dialog__title" id="confirm-dialog-title">{title}</h2>
      <p className="ui-confirm-dialog__description">{description}</p>
      {children}
      <div className="ui-confirm-dialog__actions">
        <Button onClick={onCancel} variant="secondary">{cancelLabel}</Button>
        <Button onClick={onConfirm} variant={confirmVariant}>{confirmLabel}</Button>
      </div>
    </div>
  </dialog>
}
