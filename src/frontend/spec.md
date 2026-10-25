# Frontend spec and working notes

Audience: engineers and AI assistants picking up work on `src/frontend`. This file is the single source of truth for decisions, contracts and current state of the frontend. Read it with `AGENTS.md` (coding conventions) and, for the other side of the contract, `src/backend/spec.md`. The human-facing `README.md` holds no decisions. Last updated 2026-10-25 (the real backend exists: `src/backend`).

## 1. Product and scope

regal.ai **finds the regulations a car component has to fulfil**, and lists them as a checklist the user ticks off. The challenge giver only expects the relevant regulations and their requirements, each cited to regulation, base version, page and paragraph. The app does **not** assess whether a product meets them: there is no "met / unmet" verdict anywhere. (An earlier version had an "unmet requirements" dashboard; it was removed on 2026-10-25 when this was clarified.)

Flow:

1. The user uploads a specification (Markdown or text) and/or an exploded view or drawing (one image).
2. The backend runs the `ai_agent` pipeline as an **asynchronous job**. A real run takes about 7 minutes and costs $2 to $5, so the app shows progress and the result has its own URL.
3. The result is a checklist: regulations (accordion) > sections > atomic requirements, each with a checkbox, plus the drawing with a dot per component that filters the list.

Out of scope: auth, multiple users, assessing fulfilment, regulation PDFs (the backend owns them), and the sub-goal of the challenge (diff between regulation versions; the algorithm exists in `src/ai_agent/drift.py` but has no UI).

### Decisions already made (do not reopen without a reason)

- **Documents go straight to a FastAPI endpoint** (`POST /api/analyses`, `multipart/form-data`), not to a folder and not to S3. A browser cannot write to `cases/`, saving then deleting adds cleanup and race conditions, and the files are small.
- **Asynchronous job with polling**, not one long request. Changed on 2026-10-25: the pipeline takes minutes, and a job survives a page reload because the id is in the URL.
- **The real backend is the default.** `npm run dev:mock` (Vite mode `mock`, or `VITE_USE_MOCK=true`) fakes it in the browser, and the app then shows a **Mock** badge in the nav and an alert on the Find page. Both implement one interface (`AnalysisApi`). History: until 2026-10-25 the mock was the default and `VITE_USE_MOCK=false` in `.env.local` switched it off; a `.env.local` made with `echo ... > .env.local` in Windows PowerShell is UTF-16, Vite could not read it, and the app kept returning the recorded example while looking real. A mode needs no file, and a fake result must never pass for a real one.
- **Hash routing** (`#/find/<id>`), no `react-router`, no global state store, no data-fetching library. Revisit past about five routes.
- **No animation or extra UI library.** Motion is CSS only. No chart library: nothing in the app needs one.
- **Ticks are the user's working state and live in `localStorage`**, per analysis id (`regal.checked.<id>`). The backend never sees them.
- **The regulation index belongs to the backend** (`src/backend/spec.md` section 5): the PDFs are parsed once, at the backend's first start, and kept on disk. The frontend only shows its status and offers a **Rebuild index** button; a search never triggers a rebuild. Parsing again is explicit because it is slow (about 110 s) and only needed when the PDFs or the parser change.
- **The Reference Cases page stays** (it reads `cases/*/expected.json`, the expert answers) as a way to compare with what a search returns.

## 2. Current state

| Area | State |
|---|---|
| Nav island, hash router (`home`, `find`, `reference`) | done |
| Home: split banner with photo and hotspots, stats, sample checklist, how it works, features, CTA, footer | done, copy matches the new direction |
| Find: upload view (validation, example link) | done |
| Find: progress view (six stages, elapsed time, polling) | done |
| Find: results checklist (regulations, sections, tri-state ticks, filters, drawing with component dots, CSV export, reset) | done |
| Find: failure and not-found states | done |
| Find: regulation index card (state, progress, Rebuild button) and the "no API key" alert | done, tested in mock and real mode |
| Reference Cases (reads `cases/`) | done |
| Mock backend (recorded run of the dev case) | done; opt-in with `npm run dev:mock`, flagged by a Mock badge and an alert |
| Real clients `lib/analysis/http.ts`, `lib/backend/http.ts` (the default) | tested against the real backend: status, index rebuild with progress, example result with section titles, and a full upload in the browser (multipart through the proxy, job, progress from the artifacts, result, drawing, reload) against the real backend with its pipeline faked from the recorded run. **A real model run (about $4) has not been done through the UI** |
| Vite dev proxy `/api` -> `http://localhost:8000` | done |
| Tests | none for the frontend in the repo. Verification: `npm run lint`, `npm run build`, and a throwaway puppeteer-core script outside the repo that drove every flow below in headless Chrome (36 checks, 2026-10-25) |
| Git | the frontend changes of 2026-10-25 are **uncommitted** (branch `feature/refactor-based-on-regcomp`) |

## 3. Routing and layout

`lib/use-route.ts`: `useRoute()` returns `{ route, param, navigate(route, param?) }` for `#/home` (default), `#/find`, `#/find/<analysisId>`, `#/reference`. `navigate` scrolls to the top. `components/app-header.tsx` is a **fixed floating glass nav island** (links: Home, Find Regulations, Reference Cases; shorter labels below `sm`), so pages use `pt-28`. `App.tsx` lazy-loads the Find and Reference pages and mounts `<Toaster />`.

## 4. Data contracts

### 4.1 Analysis API (the contract with the backend)

`src/lib/analysis/types.ts` is the source of truth for the types; `src/backend/spec.md` maps each field to the pipeline's files. In short:

```
POST /api/analyses            multipart, field "files" repeated   -> 202 { id }
GET  /api/analyses/{id}       -> Analysis   (404 for an unknown id; the frontend polls this every 1.5 s)
GET  /api/analyses/{id}/drawing  -> the uploaded image (Analysis.result.drawing.url points here)
id "example"                  a recorded run that is always done and needs no API key (the "View an example result" link)

GET  /api/status              -> { apiKey: boolean, index: IndexStatus }     (src/lib/backend/types.ts)
POST /api/index/rebuild       -> 202 IndexStatus   (409 while a build is running)
```

`IndexStatus` is `{ state: 'missing'|'building'|'ready'|'stale'|'failed', parser, builtAt?, seconds?, regulations, total, staleReasons[], problems[], progress?: { phase: 'cards'|'parsing', done, total, current? }, error? }`. The frontend polls `/api/status` once, and every 1.5 s while `state` is `building` (`features/find/use-backend-status.ts`). `apiKey: false` shows an alert on the upload page and disables "Find regulations".

```ts
Analysis        { id, status: 'queued'|'running'|'done'|'failed', stages: AnalysisStage[], createdAt, error?, result? }
AnalysisStage   { id: 'vision'|'profile'|'regulations'|'sections'|'obligations'|'components',
                  status: 'pending'|'running'|'done'|'skipped'|'failed', detail? }   // labels live in lib/analysis/stages.ts
AnalysisResult  { product: { name, summary, vehicleCategories }, regulations: RegulationResult[],
                  components: ComponentResult[], wholeProductRequirementIds: string[], drawing?: { url, alt }, warnings?: string[] }
RegulationResult{ code: 'UN R48', title, version /*base label*/, level?: 'device'|'vehicle'|'horizontal' /*absent for a regulation only cited by another*/,
                  confidence: 'high'|'medium'|'low', reason, covers: string[], requirements: ChecklistRequirement[] }
ChecklistRequirement { id, text, source: { regulation, version, page, paragraph }, sectionTitle?, applies?: 'certain'|'likely'|'possible', kind? }
ComponentResult { id, name, marker?: { x, y } /* 0..1 from the top left */, requirementIds: string[] }
```

Rules the UI relies on:

- `stages` always lists all six stages in order; a stage that does not apply (no drawing) is `skipped`. `detail` is a short fact shown once a stage is done.
- A requirement belongs to exactly one regulation (it sits in that regulation's `requirements`); a component's `requirementIds` may overlap with other components'. `wholeProductRequirementIds` are the ones about no single component.
- `warnings` (when present) is shown as a "This list may be incomplete" notice above the checklist: the backend sends one sentence per part of the run that failed without losing it (a regulation whose sections could not be searched or whose text could not be turned into requirements). In the mock, a file name containing `warn` gives a result with a warning.
- `components` may be empty (text-only run): the drawing panel is then hidden. `marker` may be missing for a component that is not on the drawing: it still gets a chip.
- `sectionTitle` is optional. Sections are grouped from the paragraph label (`lib/analysis/sections.ts`: `6.10.4.2` -> `6.10`, `Annex 8 2.1` -> `Annex 8`); the title is shown when present.
- `applies` other than `certain` is shown as a badge. `kind` is shown as plain text.
- `source.version` is the **base** version label and `page` the physical PDF page. Never show or compute anything that contradicts that.
- `stages[].detail` is shown when a stage is done, and also for a `skipped` stage ("Not available for this run."); without a detail a skipped stage reads "Skipped: no drawing was uploaded.".
- Errors: a rejected `start` shows a toast (the backend's sentence: no key, unsupported file, ...); `get` rejecting with `ApiError` 404 shows "This search no longer exists"; other failures are retried twice and then shown with a "Try again" button; `status: 'failed'` shows `error`.

### 4.2 The mock (`lib/analysis/mock.ts`, `mock-result.ts`, `lib/backend/mock.ts`)

A fake backend inside the browser. Jobs are stored in `localStorage` (`regal.mock.analyses`) and their progress is a function of the time since creation (about 14 s in total with a drawing), so a reload keeps them. Every upload answers with the **recorded run of the dev case** (`outputs/dev-rear-lamp-image/`: `submission.json`, `component_map.json`, `profile.md`) plus `regulations/index.json` for titles and `cases/dev-rear-lamp/exploded_view.png`. Those files are read through `import.meta.glob` and loaded lazily. Test hooks: a file whose name contains `fail` makes the job fail at the regulation stage; the id `example` is always done; without an image the result has no drawing and no dots.

`lib/backend/mock.ts` fakes the status: the index is ready (built a day ago), and "Rebuild index" runs a 9-second fake build with progress.

Hand-written for the mock (the real run keeps these in `regulations.json`): the `reason`, `level` and `confidence` of the four regulations. The dot positions (`MARKERS`) were measured on `exploded_view.png`: they are where the leader lines end.

### 4.3 Upload rules (`lib/upload.ts`)

The pipeline reads **one text specification and one image**. Allowed: `.md`, `.txt`, `.png`, `.jpg`, `.jpeg`, `.webp`; at most one drawing (a second one is rejected with a toast); 10 MB per file; exact duplicates are ignored. The backend turns several text files into one specification (see its spec). PDF, DOCX and spreadsheets are not supported: the pipeline cannot read them yet.

### 4.4 Cases (Reference Cases page and home stats)

`cases/<case-id>/expected.json`: `{ requirements: [{ id, text, source: { regulation, version, page, paragraph } }] }`. Optional `cases/<case-id>/spec.md`: its first heading (`# spec: Rear Lamp`) is the product name. A new folder shows up with no code change. `lib/cases.ts` exports `Requirement`, `Citation`, `listCases()`, `loadRequirements(caseId)`. `vite.config.ts` sets `server.fs.allow` to the repo root so Vite may read `cases/`, `outputs/` and `regulations/`.

## 5. Pages and components

### Home (`features/home/`)

`HomePage({ onNavigate })`: `hero-section` (split banner; slogan "Compliance that doesn't slow you down"; CTAs "Find regulations" and "Browse reference cases"), `car-hotspots` (dots over `src/assets/mercedes-in-motion.jpg` with **hardcoded, illustrative** example regulations, positions in percent of the photo, the photo wrapper keeps `aspect-[1200/795]`), `stats-strip` (real numbers from `cases/`, count-up), `product-showcase` with `product-visual` (decorative sample checklist built from real requirement texts of the dev case), `how-it-works`, `features-section`, `cta-band`, `site-footer`. Keep the disclaimer in the hotspot popovers. Verify the UN regulation numbers and titles in them before a demo. The photo shows a car front while the dev case is a rear lamp.

### Find (`features/find/`)

`find-page` picks the view from the route param: no id -> `upload-view`; id -> `analysis-view` (mounted with `key={id}`).

- `upload-view`, `file-dropzone`, `file-list`: validation through `acceptFiles` (toast per rejected file), role badges (Specification / Drawing), "Find regulations" and "View an example result"; the no-key alert.
- `regulation-index-card` + `use-backend-status`: at the bottom of the upload page. State badge (Ready, Building, Out of date, Failed, Not built), "N of M regulations parsed, built <date> in <s>", the reasons when the index is out of date, a progress bar and the current regulation while building, and the **Rebuild index** button (disabled while building; the "Out of date" state makes it the primary button). When the backend cannot be reached it says so and offers "Try again".
- `analysis-view` + `use-analysis`: loading skeleton, error notice (not found / try again), failed notice, `analysis-progress` while queued or running, `results/results-view` when done.
- `results/`: `results-view` (state: ticks via `use-checklist`, filters, which regulations are open), `results-header` (product, chips, "x of y checked" with progress bar, Export CSV, Reset checks, New search; focuses the h1 on mount), `filters-bar` (search over text and paragraph, regulation select, "Hide checked", clear, expand/collapse all, component chip), `regulation-item` (accordion item: tri-state checkbox that ticks what is visible, code, title, version, level badge, counts, reason, "Applies to"), `section-block` (section checkbox, count), `requirement-row` (checkbox + label, paragraph, page, badges), `drawing-panel` (drawing with `HotspotDot` per component and a chip per component plus "Whole product"; selecting one filters the list; a popover shows the count per regulation), `filters.ts`. Narrowing the list (search, regulation, component) opens all regulations so matches are not hidden.
- Ticks, reset, "Hide checked" and the CSV (`lib/analysis/export-csv.ts`, UTF-8 with BOM, one row per requirement, all requirements not only the visible ones) all work on requirement ids.

### Reference Cases (`features/reference/`)

`reference-page`, `requirements-table` (`table-fixed`, set column widths), `filters.ts`, `use-requirements.ts`. Product picker, text/ID search, regulation, version (follows the regulation), paragraph prefix, "Showing N of M". Shared piece: `components/filter-select.tsx` (also used by the results filters), and `components/hotspot-dot.tsx` (a pulsing dot with a popover: used on the home photo and on the drawing).

## 6. Visual system (`src/index.css`)

- shadcn neutral palette plus brand tokens `--brand` (indigo) and `--brand-2` (blue): `text-brand`, `bg-brand`, `from-brand`, `to-brand-2`. `.dark` is never applied: **there is no dark theme**.
- Utilities `glass` (nav) and `text-gradient`; animations `animate-fade-up`, `animate-float`, `animate-blob`, `animate-shimmer`; `components/reveal.tsx` reveals on first scroll into view. A `prefers-reduced-motion` block disables motion; JS-driven motion checks `prefersReducedMotion()` (`lib/motion.ts`).
- Clean modern AI-SaaS, restrained; text-only logo "regal.ai"; no emoji.

## 7. Conventions and gotchas

Follow `AGENTS.md`. In addition:

- Files are kebab-case; features own their folder; shared code lives in `components/` and `lib/`.
- shadcn is `base-nova` on `@base-ui/react`; add components with `npx shadcn@latest add <name> -y` from `src/frontend`. Installed: accordion, alert, badge, button, card, checkbox, input, popover, progress, select, skeleton, sonner, table. Generated files import `cn` from the `cn` package; leave that.
- **Edits to generated shadcn files (re-adding the component overwrites them):** `select.tsx` (`SelectContent` defaults `alignItemWithTrigger=false`, `align="start"` so menus open below the trigger), `checkbox.tsx` (a minus icon and the primary colours for the `indeterminate` state), `sonner.tsx` (`theme="light"` and no `next-themes`: with the OS in dark mode the toast description was near-white on a white card).
- `eslint.config.js` turns off `react-refresh/only-export-components` under `src/components/ui`.
- `lib/config.ts` (`USE_MOCK`) and `lib/http.ts` (`readJson`, which turns a FastAPI `{detail}` into an `ApiError`) are shared by the two clients (`lib/analysis`, `lib/backend`). The proxy target is `http://localhost:8000`, or `BACKEND_URL` (read by `vite.config.ts`). A response with status 500 or more and no JSON body is what the dev server's proxy sends when nothing listens there; `readJson` turns it into "the backend did not answer".
- `tsconfig.app.json` has no `baseUrl` (deprecated in TS 6); the `@/` alias works through `paths`. `erasableSyntaxOnly` is on: no constructor parameter properties (see `ApiError`).
- Base UI checkbox: the `id` prop goes to the hidden input, so `<label htmlFor>` toggles it; the visible control is a `span role="checkbox"`.
- Effects must not call `setState` synchronously (the React lint rules flag it): derive state, or set it in event handlers and after `await`.
- `html { scrollbar-gutter: stable }` prevents sideways layout shifts between short and long pages.
- A blank page with "does not provide an export named 'default'" in the console was a stale Vite dev server after files changed rapidly; restart `npm run dev` and hard-reload.
- Tooling: in the Bash tool, heredocs containing apostrophes or backslashes break; write files with the Write/Edit tools. Stop any dev server you start.
- **Visual and interaction checks:** headless Chrome works for screenshots (`chrome --headless=new --window-size=1440,1000 --virtual-time-budget=9000 --screenshot=out.png "http://localhost:5173/#/find/example"`; reveal-on-scroll sections stay blank in full-page captures). For clicks, `puppeteer-core` against the installed Chrome worked; the script is not in the repo. The `example` id makes the results page reachable without an upload.
- Images in the `Reveal` sections are invisible until scrolled into view; that is expected.

## 8. Next steps

1. Do one real search through the UI against the real backend (about $4, 7 minutes) and look at the live result: dot positions (they are the centre of a box the model drew, up to about 0.1 of the image off the leader line), section titles, progress details. Everything around the model has been exercised; the model's own output has not.
2. Show the cited page next to a requirement: `GET /api/regulations/{reg}/pages/{n}.png` (backend spec, next steps) in a dialog from the `§ paragraph / page` text.
3. Decide how to treat `possible` requirements in the checklist (hide by default? a toggle). The dev case returns 317 requirements against 190 expected.
4. A sub-goal screen (changes between regulation versions) needs decisions first: `src/backend/spec.md` section 9.
5. More file types (PDF text, several drawings) once the pipeline can read them; update `lib/upload.ts` and the dropzone copy together with the backend.
6. A real smoke test in the repo (the throwaway puppeteer script is the starting point) if the team wants regression protection.
7. Commit the frontend work.
