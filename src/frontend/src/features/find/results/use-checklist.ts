import { useCallback, useEffect, useState } from 'react'

const storageKey = (analysisId: string) => `regal.checked.${analysisId}`

function read(analysisId: string): ReadonlySet<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(storageKey(analysisId)) ?? '[]') as string[])
  } catch {
    return new Set()
  }
}

/**
 * The requirements the user has ticked off, kept in localStorage per analysis so a reload does not lose them.
 * Mount it under `key={analysisId}`: the state is read once, when the component mounts.
 */
export function useChecklist(analysisId: string) {
  const [checked, setChecked] = useState<ReadonlySet<string>>(() => read(analysisId))

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(analysisId), JSON.stringify([...checked]))
    } catch {
      // Storage is full or blocked: the ticks still work until the page is closed.
    }
  }, [analysisId, checked])

  const setMany = useCallback((ids: string[], value: boolean) => {
    setChecked((current) => {
      const next = new Set(current)
      for (const id of ids) {
        if (value) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }, [])

  const toggle = useCallback((id: string, value: boolean) => setMany([id], value), [setMany])
  const clear = useCallback(() => setChecked(new Set()), [])

  return { checked, toggle, setMany, clear }
}
