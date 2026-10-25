# regal.ai backend

The server behind regal.ai. It takes the documents of a car component, runs the analysis pipeline in `src/ai_agent` as a background job, and returns the regulations the component has to fulfil as a checklist of requirements. Each requirement carries the regulation, version, page and paragraph it comes from. The app in `src/frontend` talks to it.

The backend holds no regulatory logic of its own: everything it returns comes from the pipeline's files. What it adds is the job handling and a **regulation index**, so the regulation PDFs are parsed once and not on every search.

Built with FastAPI. Python 3.12 or newer.

## Getting started

From the repository root:

```bash
pip install -r src/backend/requirements.txt
```

1. **Add your Anthropic API key** to the `.env` file in the repository root:
   ```
   AI_AGENT_KEY=sk-ant-...
   ```
2. **Start the backend:**
   ```bash
   uvicorn backend.main:app --app-dir src
   ```
   It serves on http://localhost:8000, with interactive API docs at http://localhost:8000/docs. You can also start it from this folder with `uvicorn main:app` or `fastapi dev main.py`.
3. **Start the frontend** (see [the frontend README](../frontend/README.md)):
   ```bash
   cd src/frontend
   npm run dev
   ```
   It forwards `/api` to the backend on port 8000. There is nothing to configure: `npm run dev` is connected to the backend, and `npm run dev:mock` is the one that fakes it.

The first time it starts, the backend parses the regulation PDFs in the background (about two minutes) and keeps the result on disk. A search started in the meantime waits for it. Later starts are immediate.

While developing the backend you can add `--reload --reload-dir src/backend --reload-dir src/ai_agent --reload-dir src/regcomp`. Restrict the reload to those folders: by default it watches the whole working directory, and the files a search writes into `runs/` would restart the server in the middle of the search. A reload also stops a search that is running.

To serve the built frontend from the same process (one command for a demo), run `npm run build` in `src/frontend` and start the backend with `SERVE_FRONTEND=true`; the app is then at http://localhost:8000.

## Configuration

The `.env` file is git-ignored and read by both the pipeline and the backend. A variable that is already set in the environment wins over the file.

| Variable | Meaning | Default |
|---|---|---|
| `AI_AGENT_KEY` | Your Anthropic API key. Without it new searches are refused; the example result still opens | none |
| `AI_AGENT_MODEL` | The model of every pipeline stage | `claude-sonnet-5-5` |
| `WEB_MAX_COST_USD` | The most one search may spend, in US dollars. A search stops before a model call that would go over it | `8` |

You can paste the key while the backend runs: the next request finds it, no restart needed. The key is never returned by the API or written to a log.

Optional environment variables:

| Variable | Meaning | Default |
|---|---|---|
| `REGULATIONS_DIR` | The folder with the regulation PDFs | `regulations/data`, else `regulations/pdf` |
| `SERVE_FRONTEND` | `true` serves `src/frontend/dist` at `/` | off |
| `AI_AGENT_POLICY` | Which requirements the pipeline keeps (`precision-v2`, `precision-v1`, `baseline-v1`) | `precision-v2` |
| `AI_AGENT_WORKERS` | How many model requests the pipeline runs in parallel | `5` |
| `REGCOMP_PARSER` | Which PDF parser to use (`rules` or `marker`) | `rules` |

### The regulation PDFs

`tools/fetch_regulations.py` downloads them into `regulations/pdf/`, while the parser looks in `regulations/data/`. The backend takes `regulations/data` if it exists and `regulations/pdf` otherwise, so a fresh checkout works without moving anything. To fetch them:

```bash
python tools/fetch_regulations.py          # into regulations/pdf
```

Only the base version of each regulation is used.

## The regulation index

Parsing the 56 regulation PDFs takes about 84 seconds. The backend does it once and stores the result in `runs/_index/` (about 16 MB):

- the **cards**: title, scope, contents and supersession of every regulation, which the pipeline reads to choose the regulations;
- the **parsed documents**: every paragraph and table of every regulation, with its label, page and breadcrumb, which the pipeline walks to find the requirements.

A search loads a document in hundredths of a second instead of parsing the PDF, so it never waits for the parser.

**Keeping it up to date is explicit.** The index is built automatically only when there is none yet. After that it changes only when you press **Rebuild index** (on the Find page of the app), or call `POST /api/index/rebuild`. The same card tells you when it is out of date: the parser changed, a PDF changed or disappeared, or a regulation has no entry yet. An out-of-date index still works. A rebuild takes about two minutes, and searches keep using the old index until it is done. If it fails, the old index stays.

Deleting `runs/_index/` makes the next start build it again.

## How a search runs

1. You upload a specification (Markdown or text) and, optionally, one drawing. The backend answers at once with the id of a new search.
2. The pipeline runs in the background, one search at a time: reading the drawing, understanding the product, choosing the regulations, locating the relevant sections, writing the requirements, linking them to the components. The app follows these stages.
3. When it is done, the result is the list of regulations, each with its requirements, plus the components and their requirements. A search that partly failed says so ("This list may be incomplete").

A search with a drawing takes about 7 minutes and costs about $4 in the rear lamp example. Repeating a search with the same documents should cost almost nothing, because the pipeline replays identical model requests from its own cache (`runs/_llm_cache`).

**Accepted files:** text as `.md` or `.txt` (UTF-8), and at most one image (PNG, JPEG or WebP). Several text files are joined into one specification, in upload order. At most 10 MB per file, 20 files and 200,000 characters of text. The type of a file is decided by its content, not its name. PDF and Word files are not supported yet.

**Where things are stored** (all under `runs/`, which git ignores):

| Folder | Contents |
|---|---|
| `runs/_index/` | The regulation index |
| `runs/web/<id>/` | One folder per search: the uploaded files, the pipeline's run files, the result, and `job.log` with the pipeline's log and any error details |
| `runs/_llm_cache/` | The pipeline's cache of model answers |

Delete `runs/web/` to forget all searches. The backend has no login and spends money from the key in `.env`: run it on your own machine only.

## Endpoints

The full request and response shapes are at http://localhost:8000/docs.

| Endpoint | What it does |
|---|---|
| `GET /api/status` | Whether the backend has an API key, and the state of the regulation index |
| `POST /api/index/rebuild` | Parse every regulation PDF again |
| `POST /api/analyses` | Upload files (`multipart/form-data`, field `files`) and start a search |
| `GET /api/analyses/{id}` | Progress of a search, and its result once done. `example` is a recorded result that needs no key |
| `GET /api/analyses/{id}/drawing` | The drawing that was uploaded with a search |

## Project structure

```
src/backend/
  main.py          App and endpoints
  settings.py      Paths, limits, the API key check
  knowledge.py     The regulation index and the parse cache
  jobs.py          Background searches and their progress
  uploads.py       Checks the uploaded files and writes the case folder
  adapter.py       Turns the pipeline's run folder into the result the frontend shows
  example.py       The recorded example result
  models.py        Response models
  fsutil.py        Atomic JSON files
  requirements.txt
  tests/
  spec.md          Design decisions, how it was checked, open questions
```

## Tests

```bash
python -m pytest src/backend/tests
```

60 tests, about 20 seconds. None calls the model or costs anything. The ones that need the regulation PDFs are skipped when the PDFs are missing. One test runs the real pipeline with a scripted model in place of Claude and checks the result the backend builds from what the pipeline writes.

## Troubleshooting

- **"The backend has no Anthropic API key" (503):** add `AI_AGENT_KEY` to `.env`. No restart needed.
- **"No regulation PDFs found":** fetch them (see above), or set `REGULATIONS_DIR`.
- **The first search waits:** the regulation index is being built for the first time. Its progress is shown on the Find page.
- **A search failed with "spending limit":** raise `WEB_MAX_COST_USD`.
- **A search failed with "restarted while this search was running":** the backend was stopped or reloaded during it. Start the search again.
- **"The regulation index is out of date":** press **Rebuild index**. Until then it works as before.
- **`ModuleNotFoundError`:** install the requirements into the Python you start the backend with.
- **Port 8000 is taken:** start the backend with `--port 8001`, and the frontend with `BACKEND_URL` set to `http://localhost:8001` (PowerShell: `$env:BACKEND_URL="http://localhost:8001"; npm run dev`).

For the design, how it was checked, what the parser supports for the versioning sub-goal, and the next steps, see [spec.md](spec.md). The pipeline is described in [src/ai_agent/README.md](../ai_agent/README.md) and the regulation parser in [src/README.md](../README.md).
