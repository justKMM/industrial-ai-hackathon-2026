import { ApiError } from '@/lib/analysis/types'

/** The JSON of a response, or an `ApiError` with the backend's message (FastAPI sends `{ detail: "<string>" }`). */
export async function readJson<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
  if (body === null && response.status >= 500) {
    // The dev server's proxy answers 500 with no body when nothing listens on the backend's port.
    throw new ApiError(response.status, 'the backend did not answer. Is it running on port 8000?')
  }
  const message = typeof body?.detail === 'string' ? body.detail : `${response.status} ${response.statusText}`
  throw new ApiError(response.status, message)
}
