import type { AnalysisResult } from './types'

const cell = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`

/** The checklist as CSV (UTF-8 with a byte order mark, so Excel reads the characters right), one row per requirement. */
export function checklistCsv(result: AnalysisResult, checked: ReadonlySet<string>): string {
  const rows = [['Done', 'Regulation', 'Version', 'Paragraph', 'Page', 'Requirement', 'Id']]
  for (const regulation of result.regulations) {
    for (const r of regulation.requirements) {
      rows.push([checked.has(r.id) ? 'yes' : 'no', r.source.regulation, r.source.version, r.source.paragraph, String(r.source.page), r.text, r.id])
    }
  }
  return '﻿' + rows.map((row) => row.map(cell).join(',')).join('\r\n')
}

export function downloadCsv(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.append(link)
  link.click()
  link.remove()
  // Some browsers cancel the download if the URL is revoked straight away.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
