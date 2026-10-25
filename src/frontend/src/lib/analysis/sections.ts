import type { ChecklistRequirement } from './types'

/**
 * The part of a paragraph label that names its section: "6.10.4.2" -> "6.10", "5.2.1. Table 4" -> "5.2",
 * "Annex 8 2.1. Table A8-1" -> "Annex 8". A label in another format is its own section.
 */
export function sectionKey(paragraph: string): string {
  const annex = paragraph.match(/^(Annex\s+\S+)/i)
  if (annex) return annex[1]
  const number = paragraph.match(/^(\d+)(?:\.(\d+))?/)
  if (!number) return paragraph
  return number[2] ? `${number[1]}.${number[2]}` : number[1]
}

export interface Section {
  key: string
  /** The heading of the section when the backend sent one. */
  title?: string
  requirements: ChecklistRequirement[]
}

/** Groups requirements by section, in the order the sections first appear (the document order the backend sends). */
export function groupBySection(requirements: ChecklistRequirement[]): Section[] {
  const sections = new Map<string, Section>()
  for (const requirement of requirements) {
    const key = sectionKey(requirement.source.paragraph)
    const section = sections.get(key) ?? { key, requirements: [] }
    section.title ??= requirement.sectionTitle
    section.requirements.push(requirement)
    sections.set(key, section)
  }
  return [...sections.values()]
}

export const sectionLabel = (key: string) => (key.startsWith('Annex') ? key : `Section ${key}`)
