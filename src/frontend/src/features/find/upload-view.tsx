import { useState } from 'react'
import { ArrowRight, KeyRound, Loader2, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { analysisApi, EXAMPLE_ID } from '@/lib/analysis'
import { USE_MOCK } from '@/lib/config'
import { acceptFiles, isImage } from '@/lib/upload'
import { FileDropzone } from './file-dropzone'
import { FileList } from './file-list'
import { RegulationIndexCard } from './regulation-index-card'
import { useBackendStatus } from './use-backend-status'

export function UploadView({ onStarted }: { onStarted: (id: string) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const { state: backend, refresh } = useBackendStatus()
  const noKey = backend.status === 'ready' && !backend.value.apiKey

  function addFiles(added: File[]) {
    const { accepted, rejected } = acceptFiles(files, added)
    for (const message of rejected) toast.error('File not added', { description: message })
    if (accepted.length) setFiles([...files, ...accepted])
  }

  async function submit() {
    setSubmitting(true)
    try {
      const { id } = await analysisApi.start(files)
      onStarted(id)
    } catch (error) {
      setSubmitting(false)
      toast.error('Could not start the search', { description: error instanceof Error ? error.message : String(error) })
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 pt-28 pb-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-balance">Find the regulations for your product</h1>
        <p className="text-pretty text-muted-foreground">
          Upload the product specification and an exploded view or drawing. regal.ai returns the regulations the product has to
          fulfil as a checklist of requirements, each cited to its page and paragraph.
        </p>
      </header>

      {USE_MOCK && (
        <Alert>
          <TriangleAlert />
          <AlertTitle>Mock mode</AlertTitle>
          <AlertDescription>
            The app is not connected to the backend: every search returns a recorded example of a rear lamp, whatever you upload. Run npm
            run dev to use the real backend.
          </AlertDescription>
        </Alert>
      )}

      {noKey && (
        <Alert variant="destructive">
          <KeyRound />
          <AlertTitle>The backend has no Anthropic API key</AlertTitle>
          <AlertDescription>
            Add AI_AGENT_KEY to the .env file in the repository root. New searches are refused until then; the example result still opens.
          </AlertDescription>
        </Alert>
      )}

      <FileDropzone disabled={submitting} onFiles={addFiles} />

      {files.length > 0 && (
        <>
          <FileList
            files={files}
            disabled={submitting}
            onRemove={(index) => setFiles(files.filter((_, i) => i !== index))}
          />
          {!files.some(isImage) && (
            <p className="text-sm text-muted-foreground">
              Add an exploded view or drawing for a better result: its callouts show which parts the requirements are about.
            </p>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" className="h-11 px-6 text-base" disabled={files.length === 0 || submitting || noKey} onClick={submit}>
          {submitting && <Loader2 className="animate-spin" data-icon="inline-start" aria-hidden />}
          {submitting ? 'Starting…' : 'Find regulations'}
          {!submitting && <ArrowRight data-icon="inline-end" aria-hidden />}
        </Button>
        <Button variant="ghost" size="lg" className="h-11 px-4 text-base" disabled={submitting} onClick={() => onStarted(EXAMPLE_ID)}>
          View an example result
        </Button>
      </div>

      <RegulationIndexCard state={backend} onRefresh={refresh} />
    </main>
  )
}
