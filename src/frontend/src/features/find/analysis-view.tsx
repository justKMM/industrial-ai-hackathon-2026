import { TriangleAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AnalysisProgress } from './analysis-progress'
import { ResultsView } from './results/results-view'
import { useAnalysis } from './use-analysis'

interface Props {
  id: string
  onNewSearch: () => void
}

function Notice({ title, message, children }: { title: string; message: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 pt-28 pb-16">
      <Alert variant="destructive">
        <TriangleAlert />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{message}</AlertDescription>
      </Alert>
      <div className="flex gap-3">{children}</div>
    </main>
  )
}

/** One analysis by id: loading, running (progress), failed, or done (the checklist). Mount it with `key={id}`. */
export function AnalysisView({ id, onNewSearch }: Props) {
  const [state, retry] = useAnalysis(id)

  if (state.status === 'loading') {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 px-6 pt-28 pb-16" aria-busy="true">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-64 w-full" />
      </main>
    )
  }

  if (state.status === 'error') {
    return (
      <Notice title={state.notFound ? 'This search no longer exists' : 'Could not load the search'} message={state.message}>
        {!state.notFound && <Button onClick={retry}>Try again</Button>}
        <Button variant="outline" onClick={onNewSearch}>
          Start a new search
        </Button>
      </Notice>
    )
  }

  const { analysis } = state
  if (analysis.status === 'failed') {
    return (
      <Notice title="The search failed" message={analysis.error ?? 'Something went wrong while analysing the documents.'}>
        <Button onClick={onNewSearch}>Start a new search</Button>
      </Notice>
    )
  }
  if (analysis.status === 'done' && analysis.result) {
    return <ResultsView analysisId={id} result={analysis.result} onNewSearch={onNewSearch} />
  }
  return <AnalysisProgress analysis={analysis} />
}
