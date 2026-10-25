import { useCallback, useEffect, useState } from 'react'
import { backendApi, type BackendStatus } from '@/lib/backend'

const POLL_MS = 1500

export type BackendState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; value: BackendStatus }

/**
 * The backend's status (API key, regulation index). It is fetched once, and again every 1.5 seconds while the index is being built, so the
 * progress shows. `refresh` fetches it again, e.g. right after a rebuild was asked for.
 */
export function useBackendStatus(): { state: BackendState; refresh: () => void } {
  const [state, setState] = useState<BackendState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const poll = async () => {
      try {
        const value = await backendApi.status()
        if (cancelled) return
        setState({ status: 'ready', value })
        if (value.index.state === 'building') timer = setTimeout(poll, POLL_MS)
      } catch (error) {
        if (!cancelled) setState({ status: 'error', message: error instanceof Error ? error.message : String(error) })
      }
    }

    void poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [attempt])

  const refresh = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, refresh }
}
