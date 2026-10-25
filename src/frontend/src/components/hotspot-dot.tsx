import type { ReactNode } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

interface Props {
  /** Position on the picture, in percent of its width and height. */
  x: number
  y: number
  /** The accessible name of the dot. */
  label: string
  active?: boolean
  /** `photo`: a white pulse for dark pictures; `paper`: a brand pulse for drawings. */
  tone?: 'photo' | 'paper'
  /** The popover content. */
  children: ReactNode
}

/** A pulsing dot on a picture that opens a popover. Render it inside a `<ul className="absolute inset-0">` over the picture. */
export function HotspotDot({ x, y, label, active, tone = 'paper', children }: Props) {
  return (
    <li className="absolute" style={{ left: `${x}%`, top: `${y}%` }}>
      <Popover>
        <PopoverTrigger
          aria-label={label}
          className="group relative -translate-x-1/2 -translate-y-1/2 rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <span
            aria-hidden
            className={cn(
              'absolute inset-0 animate-ping rounded-full [animation-duration:2.4s]',
              tone === 'photo' ? 'bg-white/70' : 'bg-brand/40',
            )}
          />
          <span
            className={cn(
              'relative block size-4 rounded-full border-2 border-white bg-brand shadow-md transition-transform group-hover:scale-125 group-data-popup-open:scale-125 sm:size-5',
              active && 'ring-2 ring-brand ring-offset-2',
            )}
          />
        </PopoverTrigger>
        <PopoverContent side="top" sideOffset={10} className="w-72">
          {children}
        </PopoverContent>
      </Popover>
    </li>
  )
}
