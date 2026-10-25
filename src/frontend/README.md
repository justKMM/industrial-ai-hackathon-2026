# regal.ai frontend

The web interface for regal.ai. Upload the technical documents of a car component and get the regulations it has to fulfil, as a checklist of requirements you can tick off. Each requirement cites its regulation, version, page and paragraph.

Built with React 19, TypeScript, Vite, Tailwind CSS v4 and [shadcn/ui](https://ui.shadcn.com), with Lucide icons.

## Getting started

Requires Node.js 20 or newer.

```bash
npm install
npm run dev       # http://localhost:5173
```

The app needs the backend to run a search: start it first, as described in [Using the backend](#using-the-backend). To try the interface without it, use `npm run dev:mock`.

| Script | What it does |
|---|---|
| `npm run dev` | Start the dev server with hot reload, connected to the backend |
| `npm run dev:mock` | The same, with the backend faked in the browser: every search returns a recorded example. A **Mock** badge in the navigation shows it |
| `npm run build` | Type-check and build for production into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |

## What is in the app

| Page | Route | What it does |
|---|---|---|
| Home | `#/home` | Landing page with the product banner, an overview and calls to action |
| Find Regulations | `#/find` | Upload documents, follow the analysis, and work through the resulting checklist |
| Reference Cases | `#/reference` | Browse the expert-curated requirements of the sample products, to compare with a result |

### Finding regulations

1. **Upload** a specification (Markdown or text) and, if you have one, an exploded view or drawing (PNG, JPG or WebP). One drawing is used. Or open **View an example result**.
2. **Follow the analysis.** It runs in the background and can take a few minutes. The page shows each stage; the address of the page (`#/find/<id>`) brings you back to it later.
3. **Work through the checklist.**
   - Regulations are listed with their title, version, why they apply and how many requirements they hold. Open one to see its requirements, grouped by section, each with its paragraph and page.
   - Tick requirements, whole sections or whole regulations. Progress is shown at the top and kept in your browser, so a reload does not lose it.
   - Search, filter by regulation, or hide what you have already checked.
   - When a drawing was uploaded, select a dot on it (or a component chip) to list only the requirements about that part.
   - **Export CSV** saves the checklist, including what you have ticked.

The app does not judge whether your product meets a requirement. It tells you which ones apply.

### Reference cases

The Reference Cases page and the figures on the home page read straight from the repository's `cases/` folder. Each case is a folder with:

- `expected.json`: `{ "requirements": [{ "id", "text", "source": { "regulation", "version", "page", "paragraph" } }] }`
- an optional `spec.md`, whose first heading (for example `# spec: Rear Lamp`) becomes the product name

Add a case folder and it appears without any code change.

## Using the backend

The analysis is done by the FastAPI backend in `src/backend` (see [its README](../backend/README.md)). In short:

1. Put your Anthropic key in the `.env` file in the repository root (`AI_AGENT_KEY=sk-ant-...`).
2. Start the backend from the repository root, on port 8000:
   ```bash
   pip install -r src/backend/requirements.txt
   uvicorn backend.main:app --app-dir src
   ```
3. Start the app (`npm run dev`). The dev server forwards `/api` to `http://localhost:8000`. To use another address, set `BACKEND_URL` first (in PowerShell: `$env:BACKEND_URL="http://localhost:8001"`).

Nothing has to be set to switch between the two: `npm run dev` always talks to the backend, and `npm run dev:mock` never does.

The first time the backend starts it parses the regulation PDFs (about two minutes) and keeps the result on disk. The **Regulation index** card at the bottom of the Find page shows its state and has a **Rebuild index** button for when the PDFs or the parser change; a search never rebuilds it. The "View an example result" link needs no key.

The app only talks to the backend through `src/lib/analysis/` and `src/lib/backend/`. In the mock, every upload gets a recorded run of the rear lamp example; a file whose name contains `fail` makes the analysis fail, and one containing `warn` gives a result with a warning, to see those states.

## Project structure

```
src/
  App.tsx                    Page switching and the toast container
  components/
    app-header.tsx           Floating navigation bar
    filter-select.tsx        Select used by the filter bars
    hotspot-dot.tsx          Pulsing dot that opens a popover
    reveal.tsx               Fade-in on scroll
    ui/                      shadcn/ui components (generated)
  features/
    home/                    Landing page sections
    find/                    Upload, progress and results of an analysis
    find/results/            The checklist
    reference/               Reference cases browser
  lib/
    analysis/                Types, client (mock and HTTP) and helpers for the analysis
    backend/                 Status of the backend: API key, regulation index (mock and HTTP)
    config.ts, http.ts       The mock switch and the shared fetch helper
    cases.ts                 Reads the cases/ folder
    upload.ts                Which files are accepted
    use-route.ts             Hash-based routing
  assets/                    Images
```

Each feature folder owns its components. Shared code lives in `components/` and `lib/`.

## Development notes

- **Components:** use shadcn/ui first. Add one with `npx shadcn@latest add <name>` from this folder. See [AGENTS.md](AGENTS.md) for the coding conventions.
- **Routing:** a small hash router (`src/lib/use-route.ts`) handles the pages, so no router library is needed.
- **Styling:** colours, glass and gradient utilities and the animations are defined in `src/index.css`. Animations are plain CSS and switch off when the user prefers reduced motion. There is no dark theme.
- **Edited shadcn files:** the `Select` menu opens below its trigger, the `Checkbox` has an indeterminate icon, and the `Sonner` toaster is fixed to the light theme. Re-adding those components overwrites the changes.
- **Hotspots on the home banner:** the dots over the car photo and their example regulations are placeholder content in `src/features/home/car-hotspots.tsx`. They are positioned as percentages of the photo, so re-place them if the image changes.

For design decisions, the data contract and the list of next steps, see [spec.md](spec.md); for the backend, [../backend/README.md](../backend/README.md).

## Troubleshooting

- **Blank page and an error like "does not provide an export named 'default'":** the dev server got out of sync after many quick file changes. Stop it, run `npm run dev` again and hard-reload the browser.
- **"This search no longer exists":** the mock keeps its analyses in your browser's local storage, and the backend in `runs/web/`. Clearing site data or deleting that folder removes them.
- **"Could not reach the backend" on the Find page:** the backend is not running on port 8000 (or at `BACKEND_URL`). Start it, or run `npm run dev:mock` to try the interface without it.
- **Every search returns the rear lamp example and the navigation shows "Mock":** the app was started with `npm run dev:mock`. Use `npm run dev`.
- **"The backend has no Anthropic API key":** add `AI_AGENT_KEY` to the `.env` file in the repository root; the backend finds it without a restart.
