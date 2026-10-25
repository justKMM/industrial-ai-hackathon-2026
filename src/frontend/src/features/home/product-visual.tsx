import { Check, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface Row {
  regulation: string
  paragraph: string
  text: string
  done?: boolean
}

// Decorative sample content: requirement texts of the rear lamp example, shown as the checklist looks.
const rows: Row[] = [
  { regulation: 'UN R148', paragraph: '5.2.7', text: 'The colour of light emitted by the rear position lamp shall be red.', done: true },
  { regulation: 'UN R150', paragraph: '4.1.4', text: 'The outer surface of retro-reflective devices shall be easy to clean.', done: true },
  { regulation: 'UN R48', paragraph: '6.4.4.3', text: 'The reversing lamp shall be positioned at the rear of the vehicle.' },
  { regulation: 'UN R10', paragraph: '6.1.1.2', text: 'ESA(s) shall be tested for radiated and conducted emissions, for immunity to radiated and conducted disturbances.' },
]

const progress = [
  { label: 'R148', percent: 70, className: 'bg-brand' },
  { label: 'R48', percent: 45, className: 'bg-brand-2' },
  { label: 'R150', percent: 60, className: 'bg-brand/60' },
  { label: 'R10', percent: 20, className: 'bg-brand-2/60' },
]

export function ProductVisual() {
  return (
    <div aria-hidden className="relative mx-auto max-w-4xl">
      <div className="absolute -inset-x-6 -inset-y-6 -z-10 rounded-[2rem] bg-gradient-to-b from-brand/20 via-brand-2/10 to-transparent blur-2xl" />
      <div className="animate-float glass overflow-hidden rounded-2xl">
        <div className="flex items-center gap-3 border-b border-border/70 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-destructive/60" />
            <span className="size-2.5 rounded-full bg-muted-foreground/40" />
            <span className="size-2.5 rounded-full bg-muted-foreground/25" />
          </div>
          <div className="flex min-w-0 items-center gap-1.5 rounded-md bg-muted/70 px-2.5 py-1 text-xs text-muted-foreground">
            <FileText className="size-3.5 shrink-0" />
            <span className="truncate">Sample checklist: rear lamp</span>
          </div>
        </div>

        <div className="grid gap-5 p-4 sm:p-6 md:grid-cols-[1fr_14rem]">
          <ul className="flex flex-col gap-2.5">
            {rows.map((row) => (
              <li
                key={`${row.regulation}-${row.paragraph}`}
                className="flex items-center gap-3 rounded-xl border border-border/70 bg-background/70 px-3 py-2.5"
              >
                <span
                  className={cn(
                    'flex size-4 shrink-0 items-center justify-center rounded-[4px] border',
                    row.done ? 'border-brand bg-brand text-white' : 'border-input bg-background',
                  )}
                >
                  {row.done && <Check className="size-3" strokeWidth={3} />}
                </span>
                <div className="min-w-0 flex-1 text-left">
                  <p className={cn('truncate text-sm', row.done && 'text-muted-foreground line-through decoration-muted-foreground/40')}>
                    {row.text}
                  </p>
                  <p className="text-xs text-muted-foreground">Paragraph {row.paragraph}</p>
                </div>
                <Badge variant="outline" className="hidden shrink-0 sm:inline-flex">
                  {row.regulation}
                </Badge>
              </li>
            ))}
          </ul>

          <div className="hidden flex-col justify-between gap-4 rounded-xl border border-border/70 bg-background/70 p-4 text-left md:flex">
            <p className="text-sm font-medium">Progress by regulation</p>
            <div className="flex flex-col gap-3">
              {progress.map((p) => (
                <div key={p.label} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="w-9 shrink-0">{p.label}</span>
                  <div className="h-2 flex-1 rounded-full bg-muted">
                    <div className={`h-full rounded-full ${p.className}`} style={{ width: `${p.percent}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
