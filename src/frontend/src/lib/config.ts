/**
 * The app talks to the real backend (src/backend, through the /api proxy of the dev server).
 *
 * `npm run dev:mock` (Vite mode `mock`) or `VITE_USE_MOCK=true` fakes the backend in the browser instead: every search then returns a
 * recorded example, whatever is uploaded. The app shows a "Mock" badge in that case, so fake results are never taken for real ones.
 * A mode is used, and not only an env file, because a file written by `echo ... > .env.local` in Windows PowerShell is UTF-16 and Vite
 * cannot read it.
 */
export const USE_MOCK = import.meta.env.MODE === 'mock' || import.meta.env.VITE_USE_MOCK === 'true'
