import { USE_MOCK } from '@/lib/config'
import { httpApi } from './http'
import { mockApi } from './mock'
import type { AnalysisApi } from './types'

/** The only way the app reaches the analysis: FastAPI through the /api proxy, or the browser's mock with `npm run dev:mock` (see lib/config.ts). */
export const analysisApi: AnalysisApi = USE_MOCK ? mockApi : httpApi

export * from './types'
