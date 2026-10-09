const vietnameseLocale = 'vi-VN'

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat(vietnameseLocale, { maximumFractionDigits }).format(value)
}

export function formatQuantity(value: number | null | undefined, unit?: string | null) {
  const formatted = formatNumber(value)
  return unit ? `${formatted} ${unit}` : formatted
}

export function formatDateTime(value: Date | number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(vietnameseLocale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
