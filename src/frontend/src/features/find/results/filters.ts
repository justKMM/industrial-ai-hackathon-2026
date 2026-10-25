import type { AnalysisResult, ChecklistRequirement } from '@/lib/analysis'

/** Filter value that selects the requirements about the product as a whole. */
export const WHOLE_PRODUCT = '__whole__'

export interface Filters {
  query: string
  /** Regulation code, '' for all. */
  regulation: string
  hideChecked: boolean
  /** Component id, WHOLE_PRODUCT, or '' for all. */
  component: string
}

export const emptyFilters: Filters = { query: '', regulation: '', hideChecked: false, component: '' }

export const isFiltering = (f: Filters) => f.query !== '' || f.regulation !== '' || f.hideChecked || f.component !== ''

/** The ids of the requirements about a component, or null when no component is selected. */
export function componentRequirementIds(result: AnalysisResult, component: string): ReadonlySet<string> | null {
  if (!component) return null
  if (component === WHOLE_PRODUCT) return new Set(result.wholeProductRequirementIds)
  return new Set(result.components.find((c) => c.id === component)?.requirementIds)
}

export function filterRequirements(
  requirements: ChecklistRequirement[],
  filters: Filters,
  checked: ReadonlySet<string>,
  componentIds: ReadonlySet<string> | null,
): ChecklistRequirement[] {
  const query = filters.query.trim().toLowerCase()
  return requirements.filter(
    (r) =>
      (!filters.hideChecked || !checked.has(r.id)) &&
      (!componentIds || componentIds.has(r.id)) &&
      (!query || r.text.toLowerCase().includes(query) || r.source.paragraph.toLowerCase().includes(query)),
  )
}
