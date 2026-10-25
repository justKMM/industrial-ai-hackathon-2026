// What the analysis can read: one text specification and one drawing. The backend turns the text files into the specification
// and uses the first image as the exploded view (src/backend/spec.md).
export const TEXT_EXTENSIONS = ['.md', '.txt']
export const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp']
export const ACCEPT = [...TEXT_EXTENSIONS, ...IMAGE_EXTENSIONS].join(',')
export const MAX_FILE_BYTES = 10 * 1024 * 1024

export type FileRole = 'specification' | 'drawing'

const extensionOf = (name: string) => name.slice(name.lastIndexOf('.')).toLowerCase()

export function roleOf(file: File): FileRole | null {
  const extension = extensionOf(file.name)
  if (TEXT_EXTENSIONS.includes(extension)) return 'specification'
  if (IMAGE_EXTENSIONS.includes(extension)) return 'drawing'
  return null
}

export const isImage = (file: File) => roleOf(file) === 'drawing'

export const sameFile = (a: File, b: File) => a.name === b.name && a.size === b.size && a.lastModified === b.lastModified

export function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

/** Splits dropped files into the ones to add and a message per rejected one. Exact duplicates are ignored without a message. */
export function acceptFiles(current: File[], added: File[]): { accepted: File[]; rejected: string[] } {
  const accepted: File[] = []
  const rejected: string[] = []
  let drawings = current.filter(isImage).length
  for (const file of added) {
    if ([...current, ...accepted].some((f) => sameFile(f, file))) continue
    const role = roleOf(file)
    if (!role) {
      rejected.push(`${file.name}: use Markdown or text for the specification, PNG, JPG or WebP for the drawing.`)
    } else if (file.size > MAX_FILE_BYTES) {
      rejected.push(`${file.name}: larger than ${formatSize(MAX_FILE_BYTES)}.`)
    } else if (role === 'drawing' && drawings >= 1) {
      rejected.push(`${file.name}: only one drawing is used. Remove the current one first.`)
    } else {
      if (role === 'drawing') drawings += 1
      accepted.push(file)
    }
  }
  return { accepted, rejected }
}
