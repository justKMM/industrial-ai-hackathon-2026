import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { ACCEPT } from '@/lib/upload'
import { cn } from '@/lib/utils'

interface Props {
  disabled?: boolean
  onFiles: (files: File[]) => void
}

export function FileDropzone({ disabled, onFiles }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) onFiles(Array.from(e.dataTransfer.files))
      }}
      className={cn(
        'flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center transition-colors',
        dragging ? 'border-brand bg-brand/5' : 'bg-card',
        disabled && 'opacity-50',
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-brand/10 text-brand">
        <Upload className="size-5" aria-hidden />
      </div>
      <div>
        <p className="font-medium">Drag and drop your product documents here</p>
        <p className="mt-1 text-sm text-muted-foreground">
          The specification as Markdown or text, and an exploded view or drawing as PNG, JPG or WebP
        </p>
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        className="rounded-md px-2 py-1 text-sm font-medium text-foreground/70 underline underline-offset-4 transition-colors hover:bg-muted hover:text-foreground active:bg-muted-foreground/20 active:text-foreground focus-visible:outline-2 focus-visible:outline-ring disabled:pointer-events-none"
      >
        or browse files
      </button>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        accept={ACCEPT}
        disabled={disabled}
        aria-label="Choose product documents"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []))
          e.target.value = '' // allow choosing the same file again
        }}
      />
    </div>
  )
}
