# regal.ai frontend

The web interface for regal.ai. Upload the technical documents of a car component and get the regulations it has to fulfil, as a checklist of requirements you can tick off. Each requirement cites its regulation, version, page and paragraph.

Built with React 19, TypeScript, Vite, Tailwind CSS v4 and [shadcn/ui](https://ui.shadcn.com), with Lucide icons.

## Getting started

Requires Node.js 20 or newer.

```bash
npm install
npm run dev       # http://localhost:5173
```

| Script | What it does |
|---|---|
| `npm run dev` | Start the dev server with hot reload |
| `npm run build` | Type-check and build for production into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |

Out of the box the app runs against a **mock backend** that lives in the browser, so you can try everything without the API. See [Using the real backend](#using-the-real-backend).

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

## Using the real backend

The analysis is done by the FastAPI backend in `src/backend` (see its `spec.md`). To use it instead of the mock:

```bash
echo VITE_USE_MOCK=false > .env.local     # a file named .env.local in this folder (git ignores it)
npm run dev                               # /api is proxied to http://localhost:8000
```

The app only talks to the backend through `src/lib/analysis/`. The mock answers every upload with a recorded run of the rear lamp example. In the mock, a file whose name contains `fail` makes the analysis fail, to see the error state.

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

For design decisions, the data contract and the list of next steps, see [spec.md](spec.md).

## Troubleshooting

- **Blank page and an error like "does not provide an export named 'default'":** the dev server got out of sync after many quick file changes. Stop it, run `npm run dev` again and hard-reload the browser.
- **"This search no longer exists":** the mock keeps its analyses in your browser's local storage. Clearing site data removes them.
