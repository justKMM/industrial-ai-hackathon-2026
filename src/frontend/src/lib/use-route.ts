import { useCallback, useSyncExternalStore } from 'react'

export type Route = 'home' | 'find' | 'reference'

const routes: Route[] = ['home', 'find', 'reference']

export interface Location {
  route: Route
  /** The path segment after the route, e.g. the analysis id in `#/find/<id>`. */
  param?: string
}

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

// useSyncExternalStore needs a stable snapshot, so the hash string is the snapshot and it is parsed afterwards.
const readHash = () => window.location.hash

function parse(hash: string): Location {
  const [name, param] = hash.replace(/^#\/?/, '').split('/')
  const route = routes.find((r) => r === name) ?? 'home'
  return { route, param: param ? decodeURIComponent(param) : undefined }
}

/** Minimal hash router: `#/home`, `#/find`, `#/find/<id>`, `#/reference`. Back and reload keep the page. */
export function useRoute() {
  const location = parse(useSyncExternalStore(subscribe, readHash))
  const navigate = useCallback((route: Route, param?: string) => {
    window.location.hash = `/${route}${param ? `/${encodeURIComponent(param)}` : ''}`
    window.scrollTo({ top: 0 })
  }, [])
  return { ...location, navigate }
}
