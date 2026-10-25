import type { StageId } from './types'

/** Order and wording of the stages shown while an analysis runs. The backend reports ids and statuses only. */
export const STAGES: { id: StageId; label: string; description: string }[] = [
  { id: 'vision', label: 'Reading the drawing', description: 'Finds the components and callouts on the exploded view.' },
  { id: 'profile', label: 'Understanding the product', description: 'Builds a profile of its parts, functions and materials.' },
  { id: 'regulations', label: 'Choosing regulations', description: 'Matches the profile to the regulations that apply.' },
  { id: 'sections', label: 'Locating relevant sections', description: 'Walks each regulation to the paragraphs the product must meet.' },
  { id: 'obligations', label: 'Writing the requirements', description: 'Turns each paragraph into single, quotable requirements.' },
  { id: 'components', label: 'Linking requirements to components', description: 'Connects the requirements to the parts on the drawing.' },
]
