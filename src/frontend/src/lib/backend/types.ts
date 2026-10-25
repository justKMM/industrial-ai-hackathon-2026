/**
 * The regulation index: what the parser learned from the regulation PDFs. The backend builds it once (at its first start), keeps it on disk,
 * and parses again only when asked. A search never triggers a rebuild.
 */
export type IndexState =
  | 'missing' // nothing built yet (a first build normally starts by itself)
  | 'building'
  | 'ready'
  | 'stale' // built, but the parser or a PDF changed since: still usable, a rebuild is recommended
  | 'failed' // the last build failed (the previous index, if any, is still used)

export interface IndexProgress {
  /** `cards`: the title, scope and contents of each regulation; `parsing`: every paragraph and table of each regulation. */
  phase: 'cards' | 'parsing'
  done: number
  total: number
  current?: string
}

export interface IndexStatus {
  state: IndexState
  /** Identifies the parser the index was built with. */
  parser: string
  builtAt?: string
  /** How long the last build took. */
  seconds?: number
  /** Regulations in the index, and regulations with a PDF on the server. */
  regulations: number
  total: number
  /** Why a `stale` index is stale, in words. */
  staleReasons: string[]
  /** Regulations that could not be parsed. */
  problems: string[]
  progress?: IndexProgress
  error?: string
}

export interface BackendStatus {
  /** Whether the backend has an Anthropic API key: without it a search is refused (the example result still opens). */
  apiKey: boolean
  index: IndexStatus
}

export interface BackendApi {
  status(): Promise<BackendStatus>
  /** Parse every regulation PDF again. Rejects with `ApiError` 409 when a build is already running. */
  rebuildIndex(): Promise<IndexStatus>
}
