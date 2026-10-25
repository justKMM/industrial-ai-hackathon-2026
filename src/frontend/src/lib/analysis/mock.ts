import { isImage } from '@/lib/upload'
import { buildSampleResult } from './mock-result'
import { ApiError, EXAMPLE_ID, type Analysis, type AnalysisApi, type AnalysisStage, type StageId } from './types'

// A fake backend that lives in the browser. Jobs are kept in localStorage so a reload keeps them, and their progress is a function
// of the time since they were created, so there are no timers to clean up.
//   * any upload gives the recorded run on the dev case (see mock-result.ts)
//   * a file whose name contains "fail" makes the job fail at the regulation stage, to see the error state
//   * the id "example" is always a finished job

const STORAGE_KEY = 'regal.mock.analyses'

interface Job {
  id: string
  createdAt: number
  withDrawing: boolean
  failing: boolean
}

const STEPS: { id: StageId; ms: number; needsDrawing?: boolean; detail?: string }[] = [
  { id: 'vision', ms: 2000, needsDrawing: true, detail: '7 callouts read' },
  { id: 'profile', ms: 1500, detail: '10 parts, 7 functions' },
  { id: 'regulations', ms: 2500, detail: 'UN R148, UN R48, UN R150, UN R10' },
  { id: 'sections', ms: 3000 },
  { id: 'obligations', ms: 3500, detail: '317 requirements' },
  { id: 'components', ms: 1500, needsDrawing: true, detail: '10 components' },
]

// crypto.randomUUID only exists in secure contexts (localhost, https); the dev server may be opened by IP address.
const newId = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36)

function readJobs(): Job[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as Job[]
  } catch {
    return []
  }
}

function saveJob(job: Job) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...readJobs().filter((j) => j.id !== job.id), job].slice(-20)))
}

function stagesAt(job: Job, elapsed: number): { stages: AnalysisStage[]; finished: boolean; failedAt?: StageId } {
  let clock = 0
  let failedAt: StageId | undefined
  const stages = STEPS.map((step): AnalysisStage => {
    if (step.needsDrawing && !job.withDrawing) return { id: step.id, status: 'skipped' }
    const start = clock
    clock += step.ms
    if (failedAt) return { id: step.id, status: 'pending' }
    if (job.failing && step.id === 'regulations' && elapsed >= start) {
      failedAt = step.id
      return { id: step.id, status: 'failed' }
    }
    if (elapsed >= clock) return { id: step.id, status: 'done', detail: step.detail }
    return { id: step.id, status: elapsed >= start ? 'running' : 'pending' }
  })
  return { stages, finished: !failedAt && elapsed >= clock, failedAt }
}

export const mockApi: AnalysisApi = {
  async start(files) {
    await new Promise((resolve) => setTimeout(resolve, 400))
    const job: Job = {
      id: newId(),
      createdAt: Date.now(),
      withDrawing: files.some(isImage),
      failing: files.some((f) => /fail/i.test(f.name)),
    }
    saveJob(job)
    return { id: job.id }
  },

  async get(id): Promise<Analysis> {
    await new Promise((resolve) => setTimeout(resolve, 150))
    const job: Job | undefined =
      id === EXAMPLE_ID
        ? { id, createdAt: 0, withDrawing: true, failing: false }
        : readJobs().find((j) => j.id === id)
    if (!job) throw new ApiError(404, 'This analysis no longer exists.')

    const { stages, finished, failedAt } = stagesAt(job, Date.now() - job.createdAt)
    const base = { id, stages, createdAt: new Date(job.createdAt).toISOString() }
    if (failedAt) return { ...base, status: 'failed', error: 'The model could not choose regulations for this product (mock failure).' }
    if (!finished) return { ...base, status: stages.some((s) => s.status === 'running') ? 'running' : 'queued' }
    return { ...base, status: 'done', result: await buildSampleResult(job.withDrawing) }
  },
}
