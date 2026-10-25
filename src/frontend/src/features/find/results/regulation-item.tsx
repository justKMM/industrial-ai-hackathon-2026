import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { ChecklistRequirement, RegulationLevel, RegulationResult } from '@/lib/analysis'
import { groupBySection } from '@/lib/analysis/sections'
import { SectionBlock } from './section-block'

const LEVELS: Record<RegulationLevel, { label: string; hint: string }> = {
  device: { label: 'Device', hint: 'Approves the product itself' },
  vehicle: { label: 'Vehicle', hint: 'Sets how the product is installed on the vehicle' },
  horizontal: { label: 'Horizontal', hint: 'Applies because of a technology or material the product contains' },
}

interface Props {
  regulation: RegulationResult
  /** The requirements that pass the current filters. */
  visible: ChecklistRequirement[]
  filtering: boolean
  checked: ReadonlySet<string>
  onToggle: (id: string, value: boolean) => void
  onSetMany: (ids: string[], value: boolean) => void
}

export function RegulationItem({ regulation, visible, filtering, checked, onToggle, onSetMany }: Props) {
  const ids = visible.map((r) => r.id)
  const done = ids.filter((id) => checked.has(id)).length
  const level = regulation.level ? LEVELS[regulation.level] : undefined
  const total = regulation.requirements.length

  return (
    <AccordionItem value={regulation.code} className="rounded-xl border bg-card">
      <div className="flex items-start gap-3 px-4 pt-3">
        <Checkbox
          className="mt-1.5"
          aria-label={`Tick all requirements of ${regulation.code}`}
          checked={ids.length > 0 && done === ids.length}
          indeterminate={done > 0 && done < ids.length}
          onCheckedChange={(value) => onSetMany(ids, value)}
        />
        <div className="min-w-0 flex-1">
          <AccordionTrigger className="pr-0 pb-3 hover:no-underline">
            <span className="flex min-w-0 flex-col gap-1.5">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge>{regulation.code}</Badge>
                <span className="text-base font-medium">{regulation.title}</span>
                <span className="text-xs font-normal text-muted-foreground">version {regulation.version}</span>
              </span>
              <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-normal text-muted-foreground">
                {level && (
                  <Badge variant="outline" title={level.hint}>
                    {level.label} level
                  </Badge>
                )}
                {regulation.confidence !== 'high' && <span className="capitalize">{regulation.confidence} confidence</span>}
                <span className="tabular-nums">{filtering ? `${visible.length} of ${total}` : total} requirements</span>
                <span className="tabular-nums">{done} checked</span>
              </span>
            </span>
          </AccordionTrigger>
        </div>
      </div>
      <AccordionContent>
        <div className="flex flex-col gap-2 px-4 pb-3">
          <p className="text-sm text-pretty text-muted-foreground">{regulation.reason}</p>
          {regulation.covers.length > 0 && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Applies to: </span>
              {regulation.covers.join(', ')}
            </p>
          )}
        </div>
        {groupBySection(visible).map((section) => (
          <SectionBlock key={section.key} section={section} checked={checked} onToggle={onToggle} onSetMany={onSetMany} />
        ))}
      </AccordionContent>
    </AccordionItem>
  )
}
