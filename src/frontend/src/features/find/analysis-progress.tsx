import { useEffect, useState } from 'react'
import { CircleCheck, CircleDashed, CircleX, Loader2, Minus, type LucideIcon } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { STAGES } from '@/lib/analysis/stages'
import type { Analysis, StageStatus } from '@/lib/analysis'
import { cn } from '@/lib/utils'

const ICONS: Record<StageStatus, { icon: LucideIcon; className: string }> = {
  pending: { icon: CircleDashed, className: 'text-muted-foreground/60' },
  running: { icon: Loader2, className: 'animate-spin text-brand' },
  done: { icon: CircleCheck, className: 'text-brand' },
  skipped: { icon: Minus, className: 'text-muted-foreground/60' },
  failed: { icon: CircleX, className: 'text-destructive' },
}

function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

function formatElapsed(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function AnalysisProgress({ analysis }: { analysis: Analysis }) {
  const now = useNow(1000)
  const status = new Map(analysis.stages.map((s) => [s.id, s]))
  const active = STAGES.find((s) => status.get(s.id)?.status === 'running')

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 pt-28 pb-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Finding the regulations</h1>
        <p className="text-pretty text-muted-foreground">
          This can take a few minutes. You can leave this page open, or come back to it later through the same link.
        </p>
      </header>

      <Card>
        <CardContent className="flex flex-col gap-5">
          <p role="status" className="flex items-center justify-between text-sm">
            <span className="font-medium">{active ? `${active.label}…` : 'Waiting to start…'}</span>
            <span className="text-muted-foreground tabular-nums">
              {formatElapsed(now - Date.parse(analysis.createdAt))}
            </span>
          </p>
          <ol className="flex flex-col gap-4">
            {STAGES.map((stage) => {
              const current = status.get(stage.id)
              const { icon: Icon, className } = ICONS[current?.status ?? 'pending']
              const skipped = current?.status === 'skipped'
              return (
                <li key={stage.id} className={cn('flex gap-3', (current?.status ?? 'pending') === 'pending' && 'opacity-60')}>
                  <Icon className={cn('mt-0.5 size-5 shrink-0', className)} aria-hidden />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {stage.label}
                      <span className="sr-only"> ({current?.status ?? 'pending'})</span>
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {skipped ? 'Skipped: no drawing was uploaded.' : (current?.status === 'done' && current.detail) || stage.description}
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
        </CardContent>
      </Card>
    </main>
  )
}
