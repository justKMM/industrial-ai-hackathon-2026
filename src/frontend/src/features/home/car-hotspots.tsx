import { BookMarked } from 'lucide-react'
import { HotspotDot } from '@/components/hotspot-dot'

interface Hotspot {
  id: string
  name: string
  /** Position on the photo, in percent of its width and height. */
  x: number
  y: number
  regulations: { code: string; title: string }[]
}

// Illustrative content only: example regulations that can apply to each part.
const hotspots: Hotspot[] = [
  {
    id: 'windscreen',
    name: 'Windscreen',
    x: 43,
    y: 42,
    regulations: [
      { code: 'UN R43', title: 'Safety glazing materials' },
      { code: 'UN R125', title: 'Forward field of vision' },
    ],
  },
  {
    id: 'mirror',
    name: 'Side mirror',
    x: 27,
    y: 49,
    regulations: [{ code: 'UN R46', title: 'Devices for indirect vision' }],
  },
  {
    id: 'headlamp',
    name: 'Headlamp',
    x: 45,
    y: 55,
    regulations: [
      { code: 'UN R149', title: 'Road illumination devices' },
      { code: 'UN R48', title: 'Installation of lighting devices' },
      { code: 'UN R10', title: 'Electromagnetic compatibility' },
    ],
  },
  {
    id: 'grille',
    name: 'Front grille',
    x: 66,
    y: 55,
    regulations: [
      { code: 'UN R26', title: 'External projections' },
      { code: 'UN R127', title: 'Pedestrian safety' },
    ],
  },
  {
    id: 'wheel',
    name: 'Wheel and tyre',
    x: 37,
    y: 68,
    regulations: [
      { code: 'UN R124', title: 'Wheels for passenger cars' },
      { code: 'UN R30', title: 'Tyres for passenger cars' },
    ],
  },
]

/** Clickable dots laid over the banner photo; each opens a popover with example regulations. */
export function CarHotspots() {
  return (
    <ul className="absolute inset-0 m-0 list-none p-0">
      {hotspots.map((spot) => (
        <HotspotDot key={spot.id} x={spot.x} y={spot.y} label={`${spot.name}: show example regulations`} tone="photo">
          <p className="font-medium">{spot.name}</p>
          <p className="text-xs text-muted-foreground">Regulations that can apply</p>
          <ul className="mt-2 flex flex-col gap-2">
            {spot.regulations.map((r) => (
              <li key={r.code} className="flex items-start gap-2 text-sm">
                <BookMarked className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
                <span>
                  <span className="font-medium">{r.code}</span>
                  <span className="text-muted-foreground"> · {r.title}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t pt-2 text-xs text-muted-foreground">Illustrative examples for this kind of part.</p>
        </HotspotDot>
      ))}
    </ul>
  )
}
