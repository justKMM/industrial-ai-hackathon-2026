import { Search, X } from 'lucide-react'
import { FilterSelect } from '@/components/filter-select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { isFiltering, type Filters } from './filters'

interface Props {
  filters: Filters
  regulations: string[]
  /** Name of the selected component, shown as a removable chip. */
  componentName?: string
  shown: number
  total: number
  onChange: (patch: Partial<Filters>) => void
  onClear: () => void
  onExpandAll: () => void
  onCollapseAll: () => void
}

export function FiltersBar({ filters, regulations, componentName, shown, total, onChange, onClear, onExpandAll, onCollapseAll }: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            aria-label="Search requirements"
            placeholder="Search requirements or paragraphs"
            className="pl-9 sm:w-72"
            value={filters.query}
            onChange={(e) => onChange({ query: e.target.value })}
          />
        </div>
        <FilterSelect
          label="Regulation"
          allLabel="All regulations"
          value={filters.regulation}
          options={regulations.map((code) => ({ value: code, label: code }))}
          onChange={(regulation) => onChange({ regulation })}
        />
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={filters.hideChecked} onCheckedChange={(hideChecked) => onChange({ hideChecked })} />
          Hide checked
        </label>
        {isFiltering(filters) && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            <X /> Clear filters
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <p aria-live="polite">
          Showing {shown} of {total} requirements
        </p>
        {componentName && (
          <Badge variant="secondary" className="gap-1">
            Component: {componentName}
            <button
              type="button"
              aria-label="Clear the component filter"
              className="rounded-full p-0.5 hover:bg-foreground/10 focus-visible:outline-2 focus-visible:outline-ring"
              onClick={() => onChange({ component: '' })}
            >
              <X className="size-3" aria-hidden />
            </button>
          </Badge>
        )}
        <div className="flex gap-1 sm:ml-auto">
          <Button variant="ghost" size="sm" onClick={onExpandAll}>
            Expand all
          </Button>
          <Button variant="ghost" size="sm" onClick={onCollapseAll}>
            Collapse all
          </Button>
        </div>
      </div>
    </div>
  )
}
