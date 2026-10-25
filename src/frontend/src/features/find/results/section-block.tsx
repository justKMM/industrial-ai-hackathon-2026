import { Checkbox } from '@/components/ui/checkbox'
import { sectionLabel, type Section } from '@/lib/analysis/sections'
import { RequirementRow } from './requirement-row'

interface Props {
  section: Section
  checked: ReadonlySet<string>
  onToggle: (id: string, value: boolean) => void
  onSetMany: (ids: string[], value: boolean) => void
}

/** The requirements of one section, with a checkbox that ticks the whole section. */
export function SectionBlock({ section, checked, onToggle, onSetMany }: Props) {
  const ids = section.requirements.map((r) => r.id)
  const done = ids.filter((id) => checked.has(id)).length
  const label = sectionLabel(section.key)
  return (
    <section aria-label={label}>
      <div className="flex items-center gap-3 border-y bg-muted/50 px-4 py-2">
        <Checkbox
          aria-label={`Tick all requirements of ${label}`}
          checked={done === ids.length}
          indeterminate={done > 0 && done < ids.length}
          onCheckedChange={(value) => onSetMany(ids, value)}
        />
        <h4 className="min-w-0 truncate text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
          {section.title && <span className="font-normal normal-case"> · {section.title}</span>}
        </h4>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {done}/{ids.length}
        </span>
      </div>
      <ul className="divide-y">
        {section.requirements.map((r) => (
          <RequirementRow key={r.id} requirement={r} checked={checked.has(r.id)} onCheckedChange={(value) => onToggle(r.id, value)} />
        ))}
      </ul>
    </section>
  )
}
