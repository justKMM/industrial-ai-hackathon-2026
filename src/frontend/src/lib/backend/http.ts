import { readJson } from '@/lib/http'
import type { BackendApi, BackendStatus, IndexStatus } from './types'

/** The real backend (src/backend/spec.md). */
export const httpBackend: BackendApi = {
  async status() {
    return readJson<BackendStatus>(await fetch('/api/status'))
  },
  async rebuildIndex() {
    return readJson<IndexStatus>(await fetch('/api/index/rebuild', { method: 'POST' }))
  },
}
