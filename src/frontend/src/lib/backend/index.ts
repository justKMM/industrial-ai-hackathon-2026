import { USE_MOCK } from '@/lib/config'
import { httpBackend } from './http'
import { mockBackend } from './mock'
import type { BackendApi } from './types'

export const backendApi: BackendApi = USE_MOCK ? mockBackend : httpBackend

export * from './types'
