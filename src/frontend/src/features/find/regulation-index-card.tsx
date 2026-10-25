import { useState } from 'react'
import { CircleCheck, Database, Loader2, RefreshCw, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { backendApi, type IndexStatus } from '@/lib/backend'
import type { BackendState } from './use-backend-status'

const formatDate = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function StateBadge({ index }: { index: IndexStatus }) {
  switch (index.state) {
    case 'ready':
      return (
        <Badge variant="outline" className="gap-1">
          <CircleCheck className="text-brand" aria-hidden /> Ready
        </Badge>
      )
    case 'building':
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="animate-spin" aria-hidden /> Building
        </Badge>
      )
    case 'stale':
      return (
        <Badge variant="outline" className="gap-1 border-amber-500/50 text-amber-700">
          <TriangleAlert aria-hidden /> Out of date
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="destructive" className="gap-1">
          <TriangleAlert aria-hidden /> Failed
        </Badge>
      )
    default:
      return <Badge variant="secondary">Not built</Badge>
  }
}

function Summary({ index }: { index: IndexStatus }) {
  const { progress } = index
  if (index.state === 'building' && progress) {
    const percent = progress.total ? Math.round((progress.done / progress.total) * 100) : 0
    return (
      <div className="flex flex-col gap-2" role="status">
        <p className="text-sm">
          {progress.phase === 'cards' ? 'Reading the title and scope of each regulation' : 'Parsing every paragraph and table'}
          {progress.current && <span className="text-muted-foreground"> · {progress.current}</span>}
          <span className="text-muted-foreground tabular-nums">
            {' '}
            ({progress.done} of {progress.total})
          </span>
        </p>
        <Progress value={percent} aria-label="Index build progress" />
        {!index.builtAt && <p className="text-sm text-muted-foreground">This is the first build. A search started now waits for it.</p>}
      </div>
    )
  }
  if (index.state === 'building') return <p className="text-sm text-muted-foreground">Starting the build…</p>
  if (index.state === 'missing' || index.state === 'failed') {
    return <p className="text-sm text-destructive">{index.error ?? 'The regulation index has not been built yet.'}</p>
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p>
        {index.regulations} of {index.total} regulations parsed
        {index.builtAt && <span className="text-muted-foreground"> · built {formatDate(index.builtAt)}</span>}
        {index.seconds !== undefined && <span className="text-muted-foreground"> in {Math.round(index.seconds)} s</span>}
      </p>
      {index.staleReasons.map((reason) => (
        <p key={reason} className="text-amber-700">
          {reason}
        </p>
      ))}
      {index.problems.length > 0 && (
        <p className="text-destructive">
          {index.problems.length} regulation(s) could not be parsed: {index.problems.slice(0, 2).join('; ')}
        </p>
      )}
    </div>
  )
}

interface Props {
  state: BackendState
  /** Fetch the status again (called right after a rebuild was asked for, so the progress shows). */
  onRefresh: () => void
}

/** The regulation index: when it was built, whether it is out of date, and the button that parses the regulation PDFs again. */
export function RegulationIndexCard({ state, onRefresh }: Props) {
  const [asking, setAsking] = useState(false)

  async function rebuild() {
    setAsking(true)
    try {
      await backendApi.rebuildIndex()
    } catch (error) {
      toast.error('Could not rebuild the index', { description: error instanceof Error ? error.message : String(error) })
    } finally {
      setAsking(false)
      onRefresh()
    }
  }

  const index = state.status === 'ready' ? state.value.index : null
  const building = index?.state === 'building'

  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Database className="size-4 text-muted-foreground" aria-hidden />
            <h2 className="text-sm font-medium">Regulation index</h2>
            {index && <StateBadge index={index} />}
          </div>
          <Button
            variant={index?.state === 'stale' ? 'default' : 'outline'}
            size="sm"
            disabled={!index || building || asking}
            onClick={rebuild}
          >
            <RefreshCw className={building || asking ? 'animate-spin' : undefined} />
            {building ? 'Rebuilding…' : 'Rebuild index'}
          </Button>
        </div>

        {state.status === 'loading' && <Skeleton className="h-5 w-2/3" />}
        {state.status === 'error' && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
            <p>Could not reach the backend: {state.message} Start it as described in src/backend/README.md, or run the app with the mock: npm run dev:mock.</p>
            <Button variant="outline" size="sm" onClick={onRefresh}>
              Try again
            </Button>
          </div>
        )}
        {index && <Summary index={index} />}

        <p className="text-xs text-muted-foreground">
          The regulation PDFs are parsed once and the result is stored on the server, so a search never waits for the parser. Rebuild only
          after the PDFs or the parser changed.
        </p>
      </CardContent>
    </Card>
  )
}
