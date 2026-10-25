import { ApiError, type Analysis, type AnalysisApi } from './types'

const BASE = '/api'

async function read<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
  const message = typeof body?.detail === 'string' ? body.detail : `${response.status} ${response.statusText}`
  throw new ApiError(response.status, message)
}

/** The real backend (see src/backend/spec.md). Not exercised yet: the endpoints do not exist. */
export const httpApi: AnalysisApi = {
  async start(files) {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return read<{ id: string }>(await fetch(`${BASE}/analyses`, { method: 'POST', body: form }))
  },
  async get(id) {
    return read<Analysis>(await fetch(`${BASE}/analyses/${encodeURIComponent(id)}`))
  },
}
