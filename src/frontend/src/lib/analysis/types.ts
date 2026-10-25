import type { Requirement } from '@/lib/cases'

/** Id of the sample analysis that opens without uploading anything. The backend serves a recorded run under it. */
export const EXAMPLE_ID = 'example'

// ---- Progress -------------------------------------------------------------------------------------------------------------------------

/** The stages of the analysis, in order. A stage that does not apply (no drawing uploaded) is reported as `skipped`. */
export type StageId = 'vision' | 'profile' | 'regulations' | 'sections' | 'obligations' | 'components'
export type StageStatus = 'pending' | 'running' | 'done' | 'skipped' | 'failed'

export interface AnalysisStage {
  id: StageId
  status: StageStatus
  /** A short fact about the stage once it is done, e.g. the regulations that were chosen. */
  detail?: string
}

export type AnalysisStatus = 'queued' | 'running' | 'done' | 'failed'

// ---- Result ---------------------------------------------------------------------------------------------------------------------------

/** device: approves the product itself; vehicle: how it is installed; horizontal: applies through a technology or material it contains. */
export type RegulationLevel = 'device' | 'vehicle' | 'horizontal'
export type Confidence = 'high' | 'medium' | 'low'
/** How well a requirement applies to this product. `unlikely` ones are never sent. */
export type Applies = 'certain' | 'likely' | 'possible'
export type RequirementKind =
  | 'design'
  | 'performance'
  | 'marking'
  | 'installation'
  | 'test-procedure'
  | 'conformity-of-production'
  | 'admin'

/** One line of the checklist: an atomic requirement with the citation it comes from. */
export interface ChecklistRequirement extends Requirement {
  /** Heading of the section it sits in, e.g. "Rear position lamps". Optional: the paragraph number groups without it. */
  sectionTitle?: string
  applies?: Applies
  kind?: RequirementKind
}

export interface RegulationResult {
  /** 'UN R48' */
  code: string
  title: string
  /** The base version label every citation of this regulation refers to. */
  version: string
  /** Absent for a regulation that was only cited by another one: the pipeline gives no level for it. */
  level?: RegulationLevel
  confidence: Confidence
  /** Why the regulation applies to this product, in one or two sentences. */
  reason: string
  /** Names of the parts or functions of the product it is about. */
  covers: string[]
  requirements: ChecklistRequirement[]
}

export interface ComponentResult {
  id: string
  name: string
  /** Where to draw the dot on the drawing, 0 to 1 from the top left. Absent when the component is not on the drawing. */
  marker?: { x: number; y: number }
  requirementIds: string[]
}

export interface AnalysisResult {
  product: { name: string; summary: string; vehicleCategories: string[] }
  regulations: RegulationResult[]
  /** Parts of the product and the requirements about each. Empty when there is nothing to link. */
  components: ComponentResult[]
  /** Requirements that are about the product as a whole, not one component. */
  wholeProductRequirementIds: string[]
  /** The uploaded drawing, when there was one. */
  drawing?: { url: string; alt: string }
  /** What failed without losing the run (a regulation whose sections could not be searched, ...): the list may be incomplete. */
  warnings?: string[]
}

export interface Analysis {
  id: string
  status: AnalysisStatus
  stages: AnalysisStage[]
  createdAt: string
  error?: string
  /** Present when `status` is `done`. */
  result?: AnalysisResult
}

// ---- Client ---------------------------------------------------------------------------------------------------------------------------

export interface AnalysisApi {
  /** Uploads the documents and starts the analysis. Resolves as soon as the job exists, not when it is done. */
  start(files: File[]): Promise<{ id: string }>
  /** The current state of a job; poll it until `status` is `done` or `failed`. Rejects with `ApiError` 404 for an unknown id. */
  get(id: string): Promise<Analysis>
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
