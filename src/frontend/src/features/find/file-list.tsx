import { FileText, Image, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatSize, roleOf } from '@/lib/upload'

interface Props {
  files: File[]
  disabled?: boolean
  onRemove: (index: number) => void
}

export function FileList({ files, disabled, onRemove }: Props) {
  return (
    <ul className="flex flex-col divide-y rounded-xl border bg-card">
      {files.map((file, i) => {
        const role = roleOf(file)
        const Icon = role === 'drawing' ? Image : FileText
        return (
          <li key={`${file.name}-${file.size}-${file.lastModified}`} className="flex items-center gap-3 px-4 py-2.5">
            <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
            {role && (
              <Badge variant="secondary" className="shrink-0 capitalize">
                {role}
              </Badge>
            )}
            <span className="hidden text-xs text-muted-foreground tabular-nums sm:inline">{formatSize(file.size)}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={disabled}
              aria-label={`Remove ${file.name}`}
              onClick={() => onRemove(i)}
            >
              <X />
            </Button>
          </li>
        )
      })}
    </ul>
  )
}
