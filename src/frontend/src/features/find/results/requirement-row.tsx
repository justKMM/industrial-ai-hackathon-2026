import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { ChecklistRequirement } from '@/lib/analysis'
import { cn } from '@/lib/utils'

interface Props {
  requirement: ChecklistRequirement
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}

export function RequirementRow({ requirement: r, checked, onCheckedChange }: Props) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <Checkbox id={`req-${r.id}`} className="mt-0.5" checked={checked} onCheckedChange={onCheckedChange} />
      <div className="min-w-0 flex-1">
        <label
          htmlFor={`req-${r.id}`}
          className={cn(
            'block cursor-pointer text-sm text-pretty',
            checked && 'text-muted-foreground line-through decoration-muted-foreground/40',
          )}
        >
          {r.text}
        </label>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="font-mono">§ {r.source.paragraph}</span>
          <span>page {r.source.page}</span>
          {r.applies && r.applies !== 'certain' && (
            <Badge variant="outline" className="capitalize">
              {r.applies}
            </Badge>
          )}
          {r.kind && <span className="capitalize">{r.kind.replace(/-/g, ' ')}</span>}
        </p>
      </div>
    </li>
  )
}
