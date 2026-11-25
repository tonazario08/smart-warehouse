import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../../api'

type Result<T> = { owner: object; data: T | null; error: boolean }
const POLL_INTERVAL_MS = 5000

export function useOrderAnalytics<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
  isPending: (data: T) => boolean,
) {
  const [result, setResult] = useState<Result<T> | null>(null)
  const owner = useMemo(() => ({ key }), [key])
  const loaders = useRef({ load, isPending })
  loaders.current = { load, isPending }
  useEffect(() => {
    if (owner.key === null) return
    const { load: request, isPending: shouldPoll } = loaders.current
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    const fetchData = async () => {
      try {
        const data = await request(controller.signal)
        if (controller.signal.aborted) return
        setResult({ owner, data, error: false })
        if (shouldPoll(data)) timer = setTimeout(() => { void fetchData() }, POLL_INTERVAL_MS)
      } catch (cause) {
        if (!controller.signal.aborted && !(cause instanceof ApiError && cause.staleSession)) {
          setResult({ owner, data: null, error: true })
        }
      }
    }
    void fetchData()
    return () => {
      controller.abort()
      if (timer !== undefined) clearTimeout(timer)
    }
  }, [owner])
  const current = result?.owner === owner ? result : null
  return { data: current?.data ?? null, error: current?.error ?? false }
}
