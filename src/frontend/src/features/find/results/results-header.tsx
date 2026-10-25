import { useEffect, useRef } from 'react'
import { Download } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { AnalysisResult } from '@/lib/analysis'

interface Props {
  result: AnalysisResult
  total: number
  done: number
  onExport: () => void
  onReset: () => void
  onNewSearch: () => void
}

export function ResultsHeader({ result, total, done, onExport, onReset, onNewSearch }: Props) {
  const { product } = result
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)

  // The upload or progress view that had focus is gone: move focus to the new page's heading.
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => heading.current?.focus({ preventScroll: true }), [])

  return (
    <header className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-brand">Regulations to fulfil</p>
          <h1 ref={heading} tabIndex={-1} className="mt-1 text-3xl font-semibold tracking-tight outline-none">
            {product.name}
          </h1>
          {product.summary && <p className="mt-2 max-w-3xl text-pretty text-muted-foreground">{product.summary}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {product.vehicleCategories.map((c) => (
              <Badge key={c} variant="outline">
                Vehicle category {c}
              </Badge>
            ))}
            <Badge variant="secondary">{result.regulations.length} regulations</Badge>
            <Badge variant="secondary">{total} requirements</Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={onExport}>
            <Download /> Export CSV
          </Button>
          <Button variant="outline" onClick={onNewSearch}>
            New search
          </Button>
        </div>
      </div>

      <Card size="sm">
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4 text-sm">
            <p className="font-medium">
              {done} of {total} requirements checked
            </p>
            <div className="flex items-center gap-3">
              <span className="text-muted-foreground tabular-nums">{percent}%</span>
              <Button variant="ghost" size="sm" disabled={done === 0} onClick={onReset}>
                Reset checks
              </Button>
            </div>
          </div>
          <Progress value={percent} aria-label="Requirements checked" />
        </CardContent>
      </Card>
    </header>
  )
}
