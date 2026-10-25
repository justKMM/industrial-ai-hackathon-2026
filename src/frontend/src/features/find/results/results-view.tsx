import { useMemo, useState } from 'react'
import { SearchX } from 'lucide-react'
import { Accordion } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import type { AnalysisResult } from '@/lib/analysis'
import { checklistCsv, downloadCsv } from '@/lib/analysis/export-csv'
import { cn } from '@/lib/utils'
import { DrawingPanel } from './drawing-panel'
import { componentRequirementIds, emptyFilters, filterRequirements, isFiltering, WHOLE_PRODUCT, type Filters } from './filters'
import { FiltersBar } from './filters-bar'
import { RegulationItem } from './regulation-item'
import { ResultsHeader } from './results-header'
import { useChecklist } from './use-checklist'

interface Props {
  analysisId: string
  result: AnalysisResult
  onNewSearch: () => void
}

/** The checklist: a header with progress, the regulations as an accordion of tickable requirements, and the drawing with its components. */
export function ResultsView({ analysisId, result, onNewSearch }: Props) {
  const checklist = useChecklist(analysisId)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const codes = useMemo(() => result.regulations.map((r) => r.code), [result])
  const [open, setOpen] = useState<string[]>(() => codes.slice(0, 1))

  const regulationOf = useMemo(
    () => new Map(result.regulations.flatMap((reg) => reg.requirements.map((r) => [r.id, reg.code] as const))),
    [result],
  )
  const total = regulationOf.size
  const done = useMemo(() => [...regulationOf.keys()].filter((id) => checklist.checked.has(id)).length, [regulationOf, checklist.checked])

  const groups = useMemo(() => {
    const componentIds = componentRequirementIds(result, filters.component)
    return result.regulations
      .filter((reg) => !filters.regulation || reg.code === filters.regulation)
      .map((regulation) => ({
        regulation,
        visible: filterRequirements(regulation.requirements, filters, checklist.checked, componentIds),
      }))
  }, [result, filters, checklist.checked])
  const filtering = isFiltering(filters)
  const shown = groups.reduce((n, g) => n + g.visible.length, 0)

  // Narrowing the list opens the regulations so the matches are not hidden behind a closed row.
  function change(patch: Partial<Filters>) {
    setFilters((current) => ({ ...current, ...patch }))
    if ('query' in patch || 'regulation' in patch || 'component' in patch) setOpen(codes)
  }

  const componentName =
    filters.component === WHOLE_PRODUCT ? 'Whole product' : result.components.find((c) => c.id === filters.component)?.name
  const showComponents = result.components.length > 0

  return (
    <main className="mx-auto max-w-7xl px-6 pt-28 pb-16">
      <ResultsHeader
        result={result}
        total={total}
        done={done}
        onExport={() => downloadCsv('regulation-checklist.csv', checklistCsv(result, checklist.checked))}
        onReset={checklist.clear}
        onNewSearch={onNewSearch}
      />

      <div className={cn('mt-8 grid gap-6', showComponents && 'xl:grid-cols-[minmax(0,1fr)_30rem]')}>
        {showComponents && (
          <aside className="xl:sticky xl:top-24 xl:col-start-2 xl:row-start-1 xl:self-start">
            <DrawingPanel
              result={result}
              regulationOf={regulationOf}
              selected={filters.component}
              onSelect={(component) => change({ component })}
            />
          </aside>
        )}

        <div className="flex min-w-0 flex-col gap-4 xl:col-start-1 xl:row-start-1">
          <FiltersBar
            filters={filters}
            regulations={codes}
            componentName={componentName}
            shown={shown}
            total={total}
            onChange={change}
            onClear={() => {
              setFilters(emptyFilters)
            }}
            onExpandAll={() => setOpen(codes)}
            onCollapseAll={() => setOpen([])}
          />

          {shown === 0 ? (
            <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
              <SearchX className="size-8" aria-hidden />
              <p>No requirements match these filters.</p>
              <Button variant="outline" onClick={() => setFilters(emptyFilters)}>
                Clear filters
              </Button>
            </div>
          ) : (
            <Accordion multiple value={open} onValueChange={(value) => setOpen(value as string[])} className="gap-3">
              {groups
                .filter((g) => !filtering || g.visible.length > 0)
                .map(({ regulation, visible }) => (
                  <RegulationItem
                    key={regulation.code}
                    regulation={regulation}
                    visible={visible}
                    filtering={filtering}
                    checked={checklist.checked}
                    onToggle={checklist.toggle}
                    onSetMany={checklist.setMany}
                  />
                ))}
            </Accordion>
          )}
        </div>
      </div>
    </main>
  )
}
