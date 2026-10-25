import { useCallback, useEffect, useState } from 'react'
import { analysisApi, ApiError, type Analysis } from '@/lib/analysis'

const POLL_MS = 1500
const MAX_FAILURES = 3

export type AnalysisState =
  | { status: 'loading' }
  | { status: 'error'; message: string; notFound: boolean }
  | { status: 'ready'; analysis: Analysis }

/**
 * Follows one analysis: fetches it, and polls while it is queued or running. A request that fails is retried twice (a busy backend
 * can miss one poll) before the error is shown; an unknown id is shown at once. `retry` starts over after an error.
 * Mount it with `key={id}`: the state starts as `loading` for every id.
 */
export function useAnalysis(id: string): [AnalysisState, () => void] {
  const [state, setState] = useState<AnalysisState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0

    const poll = async () => {
      try {
        const analysis = await analysisApi.get(id)
        if (cancelled) return
        failures = 0
        setState({ status: 'ready', analysis })
        if (analysis.status === 'queued' || analysis.status === 'running') timer = setTimeout(poll, POLL_MS)
      } catch (error) {
        if (cancelled) return
        const notFound = error instanceof ApiError && error.status === 404
        failures += 1
        if (notFound || failures >= MAX_FAILURES) {
          setState({ status: 'error', message: error instanceof Error ? error.message : String(error), notFound })
        } else {
          timer = setTimeout(poll, POLL_MS)
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [id, attempt])

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return [state, retry]
}
