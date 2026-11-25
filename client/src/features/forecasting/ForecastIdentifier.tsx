import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../shared/ui/Button'

export function ForecastIdentifier({ value, label, to }: { value: string; label: string; to?: string }) {
  const [result, setResult] = useState<{ value: string; state: 'copied' | 'fallback' } | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const state = result?.value === value ? result.state : null
  const short = value.length > 16 ? value.slice(0, 14) + '…' : value
  useEffect(() => {
    if (state === 'fallback') { input.current?.focus(); input.current?.select() }
  }, [state, value])
  return <span className="forecast-identifier">
    {to ? <Link to={to} title={value} aria-label={value}>{short}</Link> : <code title={value}>{short}</code>}
    {value && <Button type="button" variant="secondary" size="small" aria-label={`Sao chép ${label.toLowerCase()}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setResult({ value, state: 'copied' })
        } catch {
          setResult({ value, state: 'fallback' })
        }
      }}>Sao chép</Button>}
    {state === 'copied' && <span role="status">Đã sao chép</span>}
    {state === 'fallback' && <span className="forecast-identifier__fallback">
      <input ref={input} aria-label={label + ' đầy đủ'} readOnly value={value} />
      <span role="status">Không sao chép tự động được. Dùng lệnh sao chép trên thiết bị.</span>
    </span>}
  </span>
}
