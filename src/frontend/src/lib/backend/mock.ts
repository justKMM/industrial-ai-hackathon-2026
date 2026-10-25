import { ApiError } from '@/lib/analysis/types'
import type { BackendApi, IndexStatus } from './types'

// A fake backend status in the browser: the index is ready, and "Rebuild" runs a short fake build (about 9 seconds) that ends ready again.
const TOTAL = 56
const BUILD_MS = 9000
const CARDS = ['UN R10', 'UN R48', 'UN R148', 'UN R150']

let builtAt = Date.now() - 26 * 3_600_000
let seconds = 108
let buildStarted: number | null = null

function snapshot(): IndexStatus {
  const base = { parser: 'rules-mock', regulations: TOTAL, total: TOTAL, staleReasons: [], problems: [] }
  if (buildStarted !== null) {
    const elapsed = Date.now() - buildStarted
    if (elapsed >= BUILD_MS) {
      builtAt = Date.now()
      seconds = Math.round(BUILD_MS / 100) / 10
      buildStarted = null
    } else {
      const share = elapsed / BUILD_MS
      const phase = share < 0.25 ? 'cards' : 'parsing'
      const done = Math.min(TOTAL - 1, Math.floor(((phase === 'cards' ? share / 0.25 : (share - 0.25) / 0.75) * TOTAL)))
      return { ...base, state: 'building', builtAt: new Date(builtAt).toISOString(), progress: { phase, done, total: TOTAL, current: CARDS[done % CARDS.length] } }
    }
  }
  return { ...base, state: 'ready', builtAt: new Date(builtAt).toISOString(), seconds }
}

export const mockBackend: BackendApi = {
  async status() {
    await new Promise((resolve) => setTimeout(resolve, 120))
    return { apiKey: true, index: snapshot() }
  },
  async rebuildIndex() {
    if (buildStarted !== null) throw new ApiError(409, 'The regulation index is already being built.')
    buildStarted = Date.now()
    return snapshot()
  },
}
