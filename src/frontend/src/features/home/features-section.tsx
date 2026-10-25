import {
  BookMarked,
  ClipboardCheck,
  History,
  ListChecks,
  MousePointerClick,
  Shapes,
  type LucideIcon,
} from 'lucide-react'
import { Reveal } from '@/components/reveal'
import { SectionHeading } from './section-heading'

interface Feature {
  icon: LucideIcon
  title: string
  body: string
}

const features: Feature[] = [
  {
    icon: BookMarked,
    title: 'Grounded citations',
    body: 'Every requirement cites its regulation, version, page and paragraph, so it can be traced to the source text.',
  },
  {
    icon: ListChecks,
    title: 'Atomic requirements',
    body: 'Regulations are broken into single, testable engineering requirements instead of long paragraphs of prose.',
  },
  {
    icon: Shapes,
    title: 'Applicability by product',
    body: 'Regulations and paragraphs are matched to the product type, its materials and the electronics it contains.',
  },
  {
    icon: History,
    title: 'Current regulations first',
    body: 'When a regulation has been replaced by a newer one, regal.ai points you to the one that is in force.',
  },
  {
    icon: MousePointerClick,
    title: 'Components on your drawing',
    body: 'Select a part of your exploded view to see which requirements are about it.',
  },
  {
    icon: ClipboardCheck,
    title: 'A checklist you keep',
    body: 'Tick off requirements as you verify them, track your progress and export the list as a CSV file.',
  },
]

export function FeaturesSection() {
  return (
    <section aria-labelledby="features" className="px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <SectionHeading
          id="features"
          eyebrow="Built for traceability"
          title="Every requirement points back to the regulation"
          description="regal.ai keeps the link between your product and the exact paragraph each requirement comes from."
        />

        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <li key={f.title}>
              <Reveal delay={(i % 3) * 100} className="h-full">
                <article className="group h-full rounded-2xl border bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-brand/40">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-brand/10 text-brand transition-colors group-hover:bg-brand group-hover:text-white">
                    <f.icon className="size-5" aria-hidden />
                  </div>
                  <h3 className="mt-4 text-base font-semibold">{f.title}</h3>
                  <p className="mt-2 text-sm text-pretty text-muted-foreground">{f.body}</p>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
