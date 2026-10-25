import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { HotspotDot } from '@/components/hotspot-dot'
import type { AnalysisResult } from '@/lib/analysis'
import { cn } from '@/lib/utils'
import { WHOLE_PRODUCT } from './filters'

interface Props {
  result: AnalysisResult
  /** Requirement id to the code of its regulation. */
  regulationOf: ReadonlyMap<string, string>
  /** The selected component id, WHOLE_PRODUCT, or ''. */
  selected: string
  onSelect: (component: string) => void
}

function breakdown(ids: string[], regulationOf: ReadonlyMap<string, string>) {
  const counts = new Map<string, number>()
  for (const id of ids) {
    const code = regulationOf.get(id)
    if (code) counts.set(code, (counts.get(code) ?? 0) + 1)
  }
  return [...counts].sort((a, b) => b[1] - a[1])
}

/** The uploaded drawing with a dot on each component, and a chip per component; selecting one filters the checklist. */
export function DrawingPanel({ result, regulationOf, selected, onSelect }: Props) {
  const { drawing, components, wholeProductRequirementIds } = result
  const chips = [
    ...components.map((c) => ({ id: c.id, name: c.name, count: c.requirementIds.length })),
    { id: WHOLE_PRODUCT, name: 'Whole product', count: wholeProductRequirementIds.length },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Components</CardTitle>
        <CardDescription>
          {drawing ? 'Select a dot or a component to list the requirements about it.' : 'Select a component to list the requirements about it.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {drawing && (
          <div className="relative overflow-hidden rounded-lg border bg-white">
            <img src={drawing.url} alt={drawing.alt} className="block w-full" />
            <ul className="absolute inset-0 m-0 list-none p-0">
              {components
                .filter((c) => c.marker)
                .map((c) => (
                  <HotspotDot
                    key={c.id}
                    x={(c.marker?.x ?? 0) * 100}
                    y={(c.marker?.y ?? 0) * 100}
                    label={`${c.name}: ${c.requirementIds.length} requirements`}
                    active={selected === c.id}
                  >
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">{c.requirementIds.length} requirements</p>
                    <ul className="mt-2 flex flex-col gap-1 text-sm">
                      {breakdown(c.requirementIds, regulationOf).map(([code, count]) => (
                        <li key={code} className="flex justify-between gap-4">
                          <span>{code}</span>
                          <span className="text-muted-foreground tabular-nums">{count}</span>
                        </li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant={selected === c.id ? 'outline' : 'default'}
                      className="mt-3 w-full"
                      onClick={() => onSelect(selected === c.id ? '' : c.id)}
                    >
                      {selected === c.id ? 'Clear filter' : 'Show these requirements'}
                    </Button>
                  </HotspotDot>
                ))}
            </ul>
          </div>
        )}
        <ul className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li key={chip.id}>
              <button
                type="button"
                aria-pressed={selected === chip.id}
                onClick={() => onSelect(selected === chip.id ? '' : chip.id)}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring',
                  selected === chip.id
                    ? 'border-brand bg-brand text-white'
                    : 'bg-background text-foreground/75 hover:border-brand/50 hover:text-foreground',
                )}
              >
                {chip.name}
                <span className={cn('ml-1.5 tabular-nums', selected === chip.id ? 'text-white/80' : 'text-muted-foreground')}>{chip.count}</span>
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
