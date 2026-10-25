import type {
  AnalysisResult,
  ChecklistRequirement,
  Confidence,
  ComponentResult,
  RegulationLevel,
  RegulationResult,
} from './types'

// The mock answers every upload with the recorded run on the dev case (outputs/dev-rear-lamp-image/), the real output of the pipeline.
// Everything is loaded lazily so none of it lands in the main bundle.

const submissions = import.meta.glob<{ requirements: ChecklistRequirement[] }>('../../../../../outputs/dev-rear-lamp-image/submission.json', {
  import: 'default',
})
const componentMaps = import.meta.glob<ComponentMapFile>('../../../../../outputs/dev-rear-lamp-image/component_map.json', { import: 'default' })
const profiles = import.meta.glob<string>('../../../../../outputs/dev-rear-lamp-image/profile.md', { query: '?raw', import: 'default' })
const indexes = import.meta.glob<{ regulation: string; title: string }[]>('../../../../../regulations/index.json', { import: 'default' })
const drawings = import.meta.glob<string>('../../../../../cases/dev-rear-lamp/exploded_view.png', {
  query: '?url',
  import: 'default',
  eager: true,
})

interface ComponentMapFile {
  components: { id: string; name: string; requirement_ids: string[]; regulations: Record<string, unknown> }[]
  whole_product_requirement_ids: string[]
}

// The pipeline only gives a box for each drawn part; these are the points where the leader lines of exploded_view.png end
// (the black dots of the drawing), so the dots of the mock sit exactly on them. 0 to 1 from the top left.
const MARKERS: Record<string, { x: number; y: number }> = {
  'Outer lens': { x: 0.08, y: 0.248 },
  'Retro-reflector': { x: 0.229, y: 0.267 },
  'Seal / gasket': { x: 0.162, y: 0.351 },
  Reflector: { x: 0.286, y: 0.39 },
  'LED modules on PCB': { x: 0.2845, y: 0.617 },
  Housing: { x: 0.345, y: 0.767 },
  'Fasteners / clips': { x: 0.37, y: 0.879 },
}

// Written for the mock: the real run keeps the reason the model gave for each regulation.
const REGULATIONS: Record<string, { level: RegulationLevel; confidence: Confidence; reason: string }> = {
  'UN R48': {
    level: 'vehicle',
    confidence: 'high',
    reason:
      'Sets how the lamps and the retro-reflector are installed on an M1 vehicle: number, position, visibility angles, colour and electrical connections.',
  },
  'UN R148': {
    level: 'device',
    confidence: 'high',
    reason:
      'Approves the rear position, stop and reversing lamp functions as devices: photometry, colour, markings and test procedures. It combines the older R7 and R23.',
  },
  'UN R150': {
    level: 'device',
    confidence: 'high',
    reason:
      'Approves the retro-reflector as a device: photometric and colorimetric performance, physical tests and markings. It replaces the older R3.',
  },
  'UN R10': {
    level: 'horizontal',
    confidence: 'medium',
    reason:
      'The LED modules on a circuit board make the lamp an electronic sub-assembly, so the electromagnetic compatibility requirements apply.',
  },
}

const line = (text: string, label: string) => text.match(new RegExp(`^${label}:\\s*(.+)$`, 'm'))?.[1].trim() ?? ''

async function first<T>(loaders: Record<string, () => Promise<T>>): Promise<T> {
  const load = Object.values(loaders)[0]
  if (!load) throw new Error('The sample run is missing from outputs/dev-rear-lamp-image/')
  return load()
}

/** The recorded run, shaped like the answer of the backend. Without a drawing there are no components and no image. */
export async function buildSampleResult(withDrawing: boolean, warnings?: string[]): Promise<AnalysisResult> {
  const [submission, componentMap, profile, index] = await Promise.all([
    first(submissions),
    first(componentMaps),
    first(profiles),
    first(indexes),
  ])
  const titles = new Map(index.map((e) => [e.regulation, e.title]))
  const components = new Map(componentMap.components.map((c) => [c.id, c]))

  const byRegulation = new Map<string, ChecklistRequirement[]>()
  for (const requirement of submission.requirements) {
    const code = requirement.source.regulation
    byRegulation.set(code, [...(byRegulation.get(code) ?? []), requirement])
  }

  const regulations: RegulationResult[] = [...byRegulation].map(([code, requirements]) => {
    const info = REGULATIONS[code]
    const covers = [...components.values()].filter((c) => code in c.regulations).map((c) => c.name)
    return {
      code,
      title: titles.get(code) ?? code,
      version: requirements[0].source.version,
      level: info?.level ?? 'device',
      confidence: info?.confidence ?? 'medium',
      reason: info?.reason ?? 'Selected for this product.',
      covers,
      requirements,
    }
  })

  const linked: ComponentResult[] = componentMap.components.map((c) => ({
    id: c.id,
    name: c.name,
    marker: withDrawing ? MARKERS[c.name] : undefined,
    requirementIds: c.requirement_ids,
  }))

  return {
    product: {
      name: line(profile, 'Product') || 'Product',
      summary: line(profile, 'Summary'),
      vehicleCategories: line(profile, 'Vehicle categories').split(',').map((c) => c.trim()).filter(Boolean),
    },
    regulations,
    components: linked,
    wholeProductRequirementIds: componentMap.whole_product_requirement_ids,
    drawing: withDrawing ? { url: Object.values(drawings)[0], alt: 'Exploded view of the rear lamp' } : undefined,
    warnings,
  }
}
