import type { Route } from '@/lib/use-route'
import { AnalysisView } from './analysis-view'
import { UploadView } from './upload-view'

interface Props {
  /** The analysis id from the URL (`#/find/<id>`); without it the page is the upload form. */
  id?: string
  onNavigate: (route: Route, param?: string) => void
}

export function FindPage({ id, onNavigate }: Props) {
  if (!id) return <UploadView onStarted={(started) => onNavigate('find', started)} />
  return <AnalysisView key={id} id={id} onNewSearch={() => onNavigate('find')} />
}
