import { httpApi } from './http'
import { mockApi } from './mock'
import type { AnalysisApi } from './types'

/**
 * The only way the app reaches the analysis. The mock is the default until the backend exists;
 * put VITE_USE_MOCK=false in src/frontend/.env.local to talk to FastAPI through the /api proxy.
 */
export const analysisApi: AnalysisApi = import.meta.env.VITE_USE_MOCK === 'false' ? httpApi : mockApi

export * from './types'
