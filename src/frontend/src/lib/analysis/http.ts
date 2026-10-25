import { readJson } from '@/lib/http'
import type { Analysis, AnalysisApi } from './types'

const BASE = '/api'

/** The real backend (src/backend/spec.md). */
export const httpApi: AnalysisApi = {
  async start(files) {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return readJson<{ id: string }>(await fetch(`${BASE}/analyses`, { method: 'POST', body: form }))
  },
  async get(id) {
    return readJson<Analysis>(await fetch(`${BASE}/analyses/${encodeURIComponent(id)}`))
  },
}
