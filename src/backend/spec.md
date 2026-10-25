# Backend spec and working notes

Audience: engineers and AI assistants building `src/backend`. This file is the plan and the record of what was checked. The frontend side of the contract is `src/frontend/spec.md` and the types in `src/frontend/src/lib/analysis/types.ts` (the types are the source of truth for the JSON). Last updated 2026-10-25. Nothing in this file has been built yet: `src/backend/main.py` still only answers `GET /`.

## 1. Purpose

The backend is a thin HTTP layer around the pipeline that already exists in `src/ai_agent/`. It receives a product's documents, runs the pipeline as a background job, reports progress, and returns the result in the shape the frontend needs. It holds **no regulatory logic of its own**: every regulation, page and paragraph in a response comes from the pipeline's files.

## 2. What exists (read from the code, 2026-10-25)

Correction to a common assumption: `src/regcomp/` is the **parser of the regulation PDFs**, not the algorithm that maps documents to regulations. That algorithm is `src/ai_agent/`, which uses `regcomp`.

| Piece | Where | Role |
|---|---|---|
| Regulation parser | `src/regcomp/parse.py` (rules), `parse_marker.py` (alternative), `corpus.py` | PDF to nodes: one per numbered paragraph, table or annex heading, each with `label` (`6.10.4.2`, `Annex 4 Part 1 1.2`), physical page range, `path` breadcrumb (`6 Specifications › 6.10 Rear position lamps › 6.10.4.2`), `body`, table grids. No model. Details: `src/README.md` |
| Pipeline | `src/ai_agent/pipeline.py` (`run_case`), CLI `run.py` | Product spec and/or drawing in, requirements with grounded citations out. Details: `src/ai_agent/README.md` |
| Format check | `tools/validate.py` | The platform's own check of `submission.json`; the pipeline already calls it (`emit.validate_submission`) |
| Drift agent | `src/ai_agent/drift.py`, `run_drift.py` | The challenge's sub-goal (changes between regulation versions). No API or UI yet; out of scope here |
| Benchmarks and tests | `eval/` | Not used at runtime. `eval/test_ai_agent.py` runs the whole chain offline with a scripted model |

The pipeline (`run_case(case_dir, settings, run_dir=None, log=..., llm=None, policy=..., catalog=None, use_image=True, image=None, component_map=None, use_text=True)`):

| Stage | Module | Artifact written in the run folder | What the UI uses it for |
|---|---|---|---|
| vision (only with an image) | `vision.py` | `vision.json` (text blocks, components with a normalised `region` box, callouts) | dots on the drawing |
| profile | `profile.py` | `profile.json`, `profile.md` | product name, summary, vehicle category, part names |
| regulations | `regulations.py`, `catalog.py` | `regulations.json` (`selected[]` with `level`, `confidence`, `covers`, `reason`; `rejected[]`; `redirects{}`) | the regulation list and why each applies |
| sections | `sections.py`, `tools.py` | `walk-<reg>.json`, `sections.json`, `citation_hop.json` | nothing directly |
| obligations | `obligations.py` | `chunks.json`, `candidates.json` (every candidate with its `status`) | nothing directly |
| emit | `emit.py` | `submission.json` (the requirements), `trace.json` (per requirement: node, quote, `kind`, `applies`, `why`) | the checklist |
| components (on by default when an image was read) | `components.py` | `component_map.json` (components, their `requirement_ids`, `whole_product_requirement_ids`, callouts) | the component filter |
| always | `llm.py` | `usage.json`, `calls.jsonl`, `run.json` | cost and time (not shown) |

Rules of the pipeline that the backend must keep intact: the model never writes a location (page and paragraph come from the parsed node); the pipeline never opens `expected.json`; every run leaves its files in `runs/<case>/<run id>/` (git-ignored).

Measured on the dev case (text and image, policy `precision-v2`, from `spec/finding/preset-and-outputs.md`): 317 requirements over UN R10, R148, R150, R48; regulation level precision/recall 1.00/1.00; page level 0.73/0.91. Cost and time at default settings: **about 7.5 minutes and $4**. The LLM layer replays identical requests from `runs/_llm_cache`, so repeating an upload of the same documents is almost free.

## 3. What the product returns

The challenge only expects the relevant regulations and the requirements to fulfil, each cited to regulation, **base** version, page and (optionally) paragraph. It does not expect an assessment of fulfilment, so the API returns no compliance verdict. The frontend shows the result as a checklist. Consequences for the backend:

- The version in every citation is the base version label, and the page is the physical PDF page: both already come from the node, never from a model.
- A regulation that was selected but has no emitted requirement is **left out** of the response.
- Requirement ids come from `submission.json` (`R-001` ...). They are stable only within one run; the frontend keys its ticks by analysis id plus requirement id.

## 4. Environment today (checked, not assumed)

- `src/backend/requirements.txt` holds only `fastapi[standard]` (includes `python-multipart`, `uvicorn`). `src/.venv` has FastAPI 0.162, uvicorn and python-multipart and **none of the pipeline's dependencies**: `anthropic`, `pymupdf`, `jsonschema`, `pillow` are missing (`scipy` and `numpy` are only needed by the drift agent). Add them to `requirements.txt`. Python 3.12 or newer (`tools/validate.py`).
- **No `.env`**: the pipeline needs `AI_AGENT_KEY` (an Anthropic key) in the environment or in the git-ignored `.env` at the repository root; `AI_AGENT_MODEL` defaults to `claude-sonnet-5-5`. The key is never printed or logged by the pipeline; the backend must not either.
- **The regulation PDFs are in the wrong folder for the code.** They were fetched into `regulations/pdf/<reg>/<base|latest>/` (56 regulations), but `regcomp.corpus.DATA` is `regulations/data/`. Today `corpus.pdf_path()` returns `None` and `RegGraph` raises `FileNotFoundError("the base PDF of UN R48 is not in regulations/data; run tools/fetch_regulations.py --out regulations/data")`. Fix once and tell everyone: either `python tools/fetch_regulations.py --out regulations/data` (the download links expire after the hackathon, so do it while they work) or move the folder. `regulations/data/` is git-ignored.
- `runs/` is git-ignored and holds the replay cache (`runs/_llm_cache`), the regulation cards (`runs/_cards/cards-<parser hash>.json`) and every run. **The first run parses all 56 PDFs to build the cards** (`Catalog().load()`), so warm it at startup, not on the first request.
- PyMuPDF is not thread-safe. The pipeline already parses regulations in the calling thread and walks them in worker threads; two pipelines running at once in one process would break that.

Run it from the repository root so `src/` is importable:

```
pip install -r src/backend/requirements.txt
uvicorn backend.main:app --app-dir src --reload --reload-dir src/backend --reload-dir src/ai_agent --reload-dir src/regcomp
```

Serves on http://localhost:8000. Restrict `--reload` to those folders: by default it watches the whole working directory, and a job writing into `runs/` (or a frontend build writing into `src/frontend/dist`) would restart the server in the middle of a run. A reload still kills a running job, so use it only while developing.

The frontend dev server proxies `/api` to port 8000 (`src/frontend/vite.config.ts`), so no CORS setup is needed.

## 5. Design

### 5.1 Asynchronous jobs

`POST /api/analyses` stores the upload, creates a job and returns `202` with its id at once. The frontend polls `GET /api/analyses/{id}` every 1.5 seconds and shows the stages. One request that stays open for seven minutes would hit proxy and browser timeouts and lose the result on a reload.

### 5.2 One worker

A `ThreadPoolExecutor(max_workers=1)` runs the jobs one after another; later jobs report `queued`. This keeps PyMuPDF single-threaded across jobs and caps spending. `Settings.workers` (default 5) still parallelises inside one run.

### 5.3 Persistence on disk

```
runs/web/<id>/
  job.json        { id, status, createdAt, finishedAt?, files: [{name, role, bytes}], hasDrawing, error? }   (written atomically)
  input/          spec.md, drawing.<ext>        the case folder handed to the pipeline
  run/            the run folder (run_case(..., run_dir=...))
  result.json     the adapter's output, cached after the first build
  job.log         the pipeline's log lines
```

State lives in memory while a job runs and is reloaded from `job.json` otherwise, so a restart keeps finished results. A job found `queued` or `running` at startup is marked `failed` ("interrupted by a restart"). No cleanup policy for the demo; document how to delete `runs/web/`.

### 5.4 Uploads become a case folder

`find_inputs` wants one text spec (`spec.md`, `technical_spec.md`, or the only other `.md`) and one image (the only `png/jpg/jpeg/webp`; with several it takes the first by name and ignores the rest). The backend therefore normalises:

- **Text files** (`.md`, `.txt`, UTF-8, no NUL bytes): one file becomes `spec.md`; several are joined in upload order, each under a `## <sanitised file name>` heading. Total cap 200,000 characters (413 beyond).
- **Image** (PNG, JPEG or WebP, checked by magic bytes, then opened with Pillow if installed): saved as `drawing.<ext>`. A second image is a `400`.
- Limits (same constants as `src/frontend/src/lib/upload.ts`): 10 MB per file, at least one file, only the types above (`415` otherwise). User file names are never used as paths.
- PDF and Word files are not read by the pipeline. Possible later step: extract text with PyMuPDF (already a dependency) into the specification; scanned PDFs would need OCR.

### 5.5 Progress comes from the artifacts

No change to `ai_agent` is needed: a stage is done when its artifact exists in `run/`. The first stage that is not done is `running`.

| Stage id | Done when | `detail` (shown by the frontend once done) |
|---|---|---|
| `vision` (skipped without an image) | `vision.json` | "N callouts read" (`len(components)`) |
| `profile` | `profile.json` | "N parts, M functions" |
| `regulations` | `regulations.json` | the chosen codes, comma separated |
| `sections` | `sections.json` (written after the walks and the citation hop) | "N provisions selected" (sum of `provisions`) |
| `obligations` | `submission.json` (written by emit) | "N requirements" |
| `components` (skipped when disabled) | `component_map.json` | "N components" |

Check the artifacts whenever the pipeline's `log` callback fires (it is called from several threads: guard shared state) and when `GET` is called. A later `progress` callback in `run_case` would make this exact (section 9).

### 5.6 The result adapter

A pure function `build_result(run_dir, job) -> AnalysisResult` (no network, no model, testable offline). Mapping, with the sources in the run folder:

| Field of `AnalysisResult` | Source |
|---|---|
| `product.name`, `summary`, `vehicleCategories` | `profile.json`: `product`, `summary`, `vehicle_categories` (drop `unspecified`) |
| `regulations[]` | one per regulation with at least one emitted requirement, in the order of `regulations.json` `selected[]`, then the regulations added by the citation hop |
| `regulations[].code`, `level`, `confidence`, `reason` | the `selected` entry. For a hop-added regulation: `reason` from `citation_hop.json` `vetted.add[]`, `confidence: "medium"` (the pipeline treats it so), `level` unknown (fallback `"device"`; see section 9) |
| `regulations[].title`, `version` | `regcomp.corpus.entry_for(code)["title"]` and `corpus.version_label(entry, "base")` |
| `regulations[].covers` | `selected[].covers` holds profile keys (`F1`, `P2`, `T1`): resolve them to names with `profile.json` `functions`, `parts`, `technologies` |
| `regulations[].requirements[]` | `submission.json` `requirements` grouped by `source.regulation`, in file order (document order) |
| requirement `applies`, `kind` | `trace.json` entry with the same `id` (`applies` is `certain`, `likely` or `possible`) |
| requirement `sectionTitle` | not available yet (section 9): from the node `path` |
| `components[]` | `component_map.json` `components`: `id`, `name`, `requirement_ids` |
| `components[].marker` | the centre of the `region` box of the component's `C*` key in `vision.json` (a component's `keys` list says which); none for spec-only components |
| `wholeProductRequirementIds` | `component_map.json` `whole_product_requirement_ids` |
| `drawing` | `{ url: "/api/analyses/<id>/drawing", alt }` when an image was uploaded |

Never put a quote, a stack trace or an unvalidated string from a model into a field the UI renders as code. `trace.json` also has the verbatim `quote` of each requirement: not exposed yet, but it is what a future "show the source sentence" needs.

### 5.7 The `example` analysis

`GET /api/analyses/example` must always answer with a finished result and work without an API key: the demo's safety net when the network or the key fails, and what the frontend's "View an example result" opens. Until a real run exists, build it from the recorded run in `outputs/dev-rear-lamp-image/` (`submission.json`, `component_map.json`, `profile.md`, `vision.json`) with the hand-written regulation reasons the frontend mock uses (`src/frontend/src/lib/analysis/mock-result.ts`), and serve `cases/dev-rear-lamp/exploded_view.png` as its drawing. After the first real run of the dev case, copy that run's `profile.json`, `regulations.json`, `trace.json`, `submission.json`, `vision.json`, `component_map.json` to `src/backend/fixtures/example/` (about 0.5 MB) and serve `example` from them through the same adapter.

### 5.8 Cost and errors

- Per job: `Settings.from_env(max_cost_usd=...)` with a lower default than the pipeline's 25 USD (suggest 8, overridable by an env var such as `WEB_MAX_COST_USD`). The pipeline stops before a call that would start above the cap (`BudgetExceeded`).
- Without `AI_AGENT_KEY` (`MissingKey`): `POST` answers `503` with a plain message; `example` still works. `GET /api/health` reports it.
- Job failures set `status: "failed"` and a short human `error`: `BudgetExceeded` ("stopped at $X of the $Y budget"), `Refused` (the model declined), missing PDF (`FileNotFoundError`: tell the operator to fetch the regulations), anything else a generic message with the job id. The full traceback goes to `job.log` only. Partial results are not returned.
- Keep `result.problems` (validation) and `result.failures` (stage failures, e.g. a regulation walk that did not finish) in `job.json` for the operator; the UI does not show them yet.

## 6. API

`/api` prefix. JSON field names are camelCase exactly as in `src/frontend/src/lib/analysis/types.ts`.

| Method and path | Request | Response |
|---|---|---|
| `GET /api/health` | | `200 { status: "ok", catalog: "loading"\|"ready"\|"failed", apiKey: boolean, pdfs: boolean }` |
| `POST /api/analyses` | `multipart/form-data`, field `files` repeated | `202 { id }` and `Location`. `400` no file, a second image, unreadable text; `413` too large; `415` unsupported type; `503` no API key |
| `GET /api/analyses/{id}` | | `200 Analysis`; `404 { detail }` for an unknown id (the frontend shows "This search no longer exists") |
| `GET /api/analyses/{id}/drawing` | | the uploaded image with its content type; `404` if none |
| `GET /api/analyses/example` | | a finished `Analysis` (section 5.7) |

FastAPI errors use `{ "detail": "<string>" }` and the frontend shows `detail` when it is a string.

A running job:

```json
{ "id": "5b1c…", "status": "running", "createdAt": "2026-10-25T10:12:03Z",
  "stages": [
    { "id": "vision", "status": "done", "detail": "7 callouts read" },
    { "id": "profile", "status": "running" },
    { "id": "regulations", "status": "pending" }, { "id": "sections", "status": "pending" },
    { "id": "obligations", "status": "pending" }, { "id": "components", "status": "pending" } ] }
```

A finished job adds `"status": "done"`, all stages `done` or `skipped`, and `result`:

```json
{ "product": { "name": "Rear lamp", "summary": "Combined rear lamp module …", "vehicleCategories": ["M1"] },
  "regulations": [ { "code": "UN R148", "title": "Light-Signalling Devices (LSD)", "version": "1.6.0", "level": "device",
      "confidence": "high", "reason": "…", "covers": ["Rear position lamp", "Outer lens"],
      "requirements": [ { "id": "R-001", "text": "Every device belonging to an approved type shall …",
          "source": { "regulation": "UN R148", "version": "1.6.0", "page": 6, "paragraph": "3.3.1.1" },
          "applies": "certain", "kind": "marking" } ] } ],
  "components": [ { "id": "K4", "name": "Outer lens", "marker": { "x": 0.08, "y": 0.25 }, "requirementIds": ["R-012"] } ],
  "wholeProductRequirementIds": ["R-001"],
  "drawing": { "url": "/api/analyses/5b1c…/drawing", "alt": "Exploded view" } }
```

Later: `GET /api/regulations/{reg}/pages/{n}.png`, the page of the base PDF rendered with PyMuPDF (validate `reg` against `regulations/index.json` and `n` against the page count, cache under `runs/_pages/`, hold the PyMuPDF lock). The frontend would show the cited page next to a requirement, and the `quote` from `trace.json` could be highlighted with `page.search_for`.

## 7. Code layout (suggested)

```
src/backend/
  __init__.py
  main.py          FastAPI app, lifespan (warm Catalog in a thread, scan runs/web), mounts the router;
                   optional: serve src/frontend/dist with StaticFiles so one process is the whole demo
  settings.py      paths (ROOT, runs/web), limits, WEB_MAX_COST_USD, example locations
  uploads.py       validate (magic bytes, size, types) and write the case folder
  jobs.py          JobStore (job.json), Runner (single worker, calls run_case with a shared Catalog and a log callback), stage derivation
  adapter.py       build_result(run_dir, job): pure, section 5.6
  example.py       the recorded run (section 5.7)
  routes.py        the endpoints
  tests/           section 10
  fixtures/example/  after the first real run
```

Pass one `Catalog().load()` instance to every `run_case(..., catalog=catalog)`: it is built once at startup. `run_case` returns a `RunResult` (`run_dir`, `submission`, `profile`, `regulations`, `candidates`, `problems`, `failures`, `ledger`).

## 8. Quality of the answer (what to expect, what to tune)

The pipeline was tuned for the challenge's score, not for a checklist: on the dev case it returns 317 requirements where the experts list 190, so roughly 40% of the rows are extras (requirement-level strict precision 0.43, recall 0.72). Each requirement carries `applies`; the frontend shows `likely` and `possible` as badges. If the checklist feels padded, the options are: hide `possible` by default in the UI, or add an API parameter that applies a stricter emission policy (`emit.POLICIES`: `precision-v2` is the default, `precision-v1` also drops a regulation that has no `certain` requirement unless it was picked at high confidence). Regulation choice is the weak point on other products (the six generated cases in `testing/RESULTS.md`: regulation recall 0.25 to 1.00), so the regulation list with its `reason` matters more to users than the row count.

## 9. Small changes wanted in `ai_agent` (owned by the algorithm side; each backward compatible)

1. **Section titles for the checklist.** Carry `graph.nodes[idx].path` (the breadcrumb) from `obligations.ground` into the candidate and from there into `trace.json`; the adapter takes the section segment (`6.10 Rear position lamps`) as `sectionTitle`. Without it the UI groups by paragraph number only.
2. **Dot positions on the drawing.** `vision.py` returns a `region` box per component, and the box centre misses the leader-line end by up to about 0.1 of the image (for the dev drawing: housing and fasteners are off by 0.05 to 0.13). Add an `anchor` point (where the leader line meets the part) to `MAP_SCHEMA`; the adapter prefers it over the box centre.
3. **Components for text-only runs.** `component_map` is only built when an image was read (`component_map=None`). Pass `component_map=True` always: with no drawing it groups the parts of the specification, which gives the UI its component chips.
4. **A progress callback.** An optional `progress(stage, event, detail)` argument of `run_case` would replace the artifact polling of section 5.5 with exact events.
5. **`level` for citation-hop regulations.** `regulations.vet_cited` could return the level, so every regulation in the response has a real one.

## 10. Testing (no model call, no cost)

- **Adapter:** run `build_result` on a recorded run folder and assert the invariants the frontend relies on: every id in `components[].requirementIds` and `wholeProductRequirementIds` exists among the requirements; every requirement sits in the regulation named by its `source.regulation`; versions equal the base labels in `regulations/index.json`; no regulation with zero requirements; `marker` values in 0 to 1. Until a full run folder exists use `outputs/dev-rear-lamp-image/`.
- **Uploads:** wrong magic bytes, `.docx`, empty file, two images, oversize, non-UTF-8 text, several text files joined in order, path-like file names.
- **Jobs and API (FastAPI `TestClient`):** replace `run_case` with a fake that writes the stage artifacts one by one and assert the `queued` to `running` to `done` transitions and the `detail` strings; failure paths (`BudgetExceeded`, missing key, missing PDF); restart recovery marks an unfinished job `failed`; `example` works with no key.
- **Pipeline itself:** `python eval/test_ai_agent.py --unit` must still pass; the backend must not change `ai_agent` behaviour.
- **Contract:** the frontend's mock result (`src/frontend/src/lib/analysis/mock-result.ts`) and the adapter's `example` output should have the same shape; compare their keys in a test or by eye once.
- **One real run** (about $4, 7 minutes; free if the replay cache holds the requests): `curl -F files=@cases/dev-rear-lamp/spec.md -F files=@cases/dev-rear-lamp/exploded_view.png http://localhost:8000/api/analyses`, poll the id, expect four regulations (UN R10, R148, R150, R48) and about 317 requirements, then open it in the frontend with `VITE_USE_MOCK=false`.

## 11. Open questions

- Show all requirements or hide `possible` ones by default? Needs a look at real results with the team (section 8).
- More inputs: several drawings (the pipeline uses one), PDF datasheets (text extraction), spreadsheets. Each needs a change in `inputs.py`/`vision.py` or a conversion step here, and in the frontend's `lib/upload.ts`.
- Show when a newer version of a regulation exists? `regulations/index.json` has the `latest` label for most; a `latestVersion` field would be cheap. Citations must stay on the base version (that is what the challenge scores).
- Cancel a running job? The pipeline has no cancellation; skipping it is fine for the demo.
- Serving: localhost only today. If the demo ever runs elsewhere, add auth in front, because every upload spends money.

## 12. Next steps (in order, each with a check)

1. **Environment.** Fix the PDF location (section 4), install the dependencies, create `.env` with `AI_AGENT_KEY`. Check: `python eval/test_ai_agent.py` passes with the corpus tests, and `python -c "import sys; sys.path.insert(0,'src'); from regcomp import corpus; print(corpus.pdf_path(corpus.entry_for('UN R48'),'base'))"` prints a path.
2. **One real run of the dev case** with `python src/ai_agent/run.py cases/dev-rear-lamp --max-cost 6` (text and image). Check: `runs/dev-rear-lamp/<id>/` holds all the files of section 2. Copy them to `src/backend/fixtures/example/`.
3. **Skeleton.** Package, `settings.py`, `GET /api/health`, lifespan warm-up of the catalog. Check: the health endpoint reports `catalog: "ready"` after a while.
4. **`uploads.py`** with its tests.
5. **`adapter.py` and `example.py`** with the invariant tests. Check: `GET /api/analyses/example` returns what the frontend mock returns, structurally.
6. **`jobs.py` and the routes** with the fake-pipeline tests. Check: the frontend with `VITE_USE_MOCK=false` runs the example and shows a fake job's progress.
7. **Real end-to-end** (section 10, last bullet). Fix whatever the mock hid.
8. **The `ai_agent` changes** of section 9 (1 and 2 first: they change what users see).
9. **Page images** (`GET /api/regulations/{reg}/pages/{n}.png`) and the frontend dialog.
10. **Run instructions in the root README**, and optionally serve `src/frontend/dist` from FastAPI so one command starts the demo.
