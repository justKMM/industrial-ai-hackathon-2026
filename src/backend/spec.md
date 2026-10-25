# Backend spec and working notes

Audience: engineers and AI assistants working on `src/backend`. This file records what the backend does, why, how it was checked, and what is still open. How to run, configure and troubleshoot it, for people, is in [README.md](README.md). The frontend side of the contract is `src/frontend/spec.md`; the JSON types are in `src/frontend/src/lib/analysis/types.ts` and `src/lib/backend/types.ts`, and their Python twins in `src/backend/models.py`. Last updated 2026-10-25.

## 1. Purpose

A thin HTTP layer around the pipeline in `src/ai_agent/`. It receives a product's documents, runs the pipeline as a background job, reports progress, and returns the result in the shape the frontend shows. It holds **no regulatory logic of its own**: every regulation, version, page and paragraph in a response is copied from the pipeline's files. It also owns one thing the pipeline does not have: a **persistent regulation index**, so the regulation PDFs are parsed once and not on every run (section 5).

## 2. Status

| Area | State |
|---|---|
| `POST /api/analyses`, `GET /api/analyses/{id}`, `GET /api/analyses/{id}/drawing`, the `example` analysis | built, tested |
| Jobs: one worker, queue, progress from artifacts, failure messages, restart recovery | built, tested |
| Persistent regulation index, `GET /api/status`, `POST /api/index/rebuild` | built, tested, run on the real 56 PDFs |
| Result adapter (run folder to `AnalysisResult`) | built, tested against a real pipeline run (scripted model) and the recorded dev run |
| API key from `.env`, picked up without a restart | built, tested; one real call confirmed the key works |
| A full real analysis (real model, real drawing) | **not run** (about $4 and 7 minutes; nobody asked for it yet). Everything around the model has been run with a script in its place |
| Sub-goal (changes between regulation versions) | not exposed; see section 9 |
| Page images of the cited regulation pages | not built |
| Tests | `python -m pytest src/backend/tests` (60 tests, about 20 s, no model call, no cost) |

## 3. Running and configuring it

The commands, the variables of `.env`, the PDF folder and the troubleshooting list are in [README.md](README.md). What matters for the design:

- **The key.** `.env` in the repository root is read by `ai_agent.config` (the pipeline) and by the backend; a variable already set in the real environment wins. `Settings.from_env(max_cost_usd=WEB_MAX_COST_USD)` is what every job uses, so the pipeline's own `AI_AGENT_MAX_COST_USD` has no effect here. Without a key a new search is refused with `503`, `GET /api/status` says `apiKey: false`, and the example still opens. `load_env` never overrides a variable that is already set, and an empty `AI_AGENT_KEY=` line counts as set to nothing, so `backend.settings.api_key_present()` drops an empty value before it reads the file again: **a key pasted into `.env` while the backend runs is found by the next request, no restart.** The key is never returned, logged or stored: error text is scrubbed (`settings.redact`) before it reaches a response or `job.log`, and a test checks it.
- **The regulation PDFs.** `regcomp.corpus` looks in `regulations/data/`, but `tools/fetch_regulations.py` writes to `regulations/pdf/` unless told otherwise, so a fresh checkout has them there. The backend takes `regulations/data` when it exists, else `regulations/pdf` (`REGULATIONS_DIR` overrides both) and points `corpus.DATA` at it when it starts, so nothing has to be moved and the pipeline is not edited. Only the 56 base versions are on the machine this was written on; the 36 `latest` versions have not been fetched.
- **First start.** There is no index yet, so the backend builds it by itself in the background: about **110 seconds** for the 56 regulations (measured). A search started meanwhile waits in `queued` until the cards exist. Later starts find the index and do nothing.
- **Entry points.** `uvicorn backend.main:app --app-dir src` from the repository root, or `uvicorn main:app` / `fastapi dev main.py` from `src/backend` (`main.py` puts `src/` on `sys.path` itself; all three were run). `--reload` must be limited with `--reload-dir`, or the files a job writes into `runs/` restart the server mid-run (section 11).

## 4. What exists upstream (read from the code)

`src/regcomp/` is the **parser of the regulation PDFs** (PDF to nodes: paragraphs, tables and annex headings with label, physical page range, breadcrumb `path`, text, table grids). `src/ai_agent/` is the algorithm that maps a product's documents to regulations; it uses `regcomp`. `tools/validate.py` is the platform's format check (the pipeline already runs it). Details: `src/README.md`, `src/ai_agent/README.md`.

| Pipeline stage | Artifact in the run folder | Used for |
|---|---|---|
| vision (only with an image) | `vision.json` (components with a normalised `region` box) | dots on the drawing |
| profile | `profile.json` | product name, summary, vehicle category, names of parts |
| regulations | `regulations.json` (`selected[]`: `level`, `confidence`, `covers`, `reason`; `redirects`) | the regulation list and why each applies |
| sections | `sections.json`, `walk-<reg>.json`, `citation_hop.json` | progress detail |
| obligations, emit | `candidates.json`, `submission.json`, `trace.json` (`applies`, `kind`, `quote`, `why` per requirement) | the checklist |
| components | `component_map.json` | the component filter |

The backend calls `ai_agent.pipeline.run_case(case_dir, settings, run_dir, log=..., catalog=..., component_map=True)`: with its own run folder, the shared catalog, a log callback, and the component map always on (with no drawing it groups the parts of the specification, which gives the frontend its component chips). The pipeline's own rules hold: the model never writes a location, and it never opens `expected.json`. Measured on the dev case (text and image): 317 requirements over UN R10, R148, R150, R48; regulation precision and recall 1.00 and 1.00, page level 0.73 and 0.91; about **7.5 minutes and $4** per run. Identical model requests are replayed for free from `runs/_llm_cache`.

## 5. The regulation index

**Is the parsed knowledge persistent? Now it is; before this backend it was only partly.** The pipeline cached the regulation *cards* (`runs/_cards/cards-<parser hash>.json`) but parsed the PDFs of the chosen regulations again on every run (`RegGraph(reg)` calls the parser each time). `backend/knowledge.py` keeps both:

```
runs/_index/
  manifest.json                    parser, parser hash, build time and duration, per regulation: pages, nodes, PDF size and mtime; problems
  cards/cards-<hash>.json          the cards (title, scope, contents, supersession), as ai_agent.catalog writes them
  parsed/<parser>-<hash>/<reg>__base__grids__<size>-<mtime>.pkl     one pickled ParsedDocument per PDF
```

- **Keyed by the parser.** The hash of the parser's source file is in the folder name, so changing `regcomp/parse.py` makes the stored documents unreachable by itself; a PDF that changes on disk gets a new file name (its size and time are in it). Old parser folders are deleted after a build.
- **What it saves.** A document loads in about 0.01 s (up to 0.5 MB each, 16 MB for all 56). `RegGraph("UN R48")` took 0.03 s from the cache; parsing the PDF takes about 2 s. The whole corpus parses in about 84 s (largest: UN R49, 363 pages, 21 s). A run selects four to eight regulations, so a run no longer waits 10 to 60 s for the parser.
- **How the pipeline uses it without being edited.** `KnowledgeIndex.install()` replaces `ai_agent.store._parser` (the function `RegGraph` asks for its parser) with one that reads the cache first, and sets `regcomp.corpus.DATA`. Every call returns a fresh object read from the file, so no run can change what the next sees. A file that cannot be read is a cache miss, never an error. Pickles are only ever written by this process into a local folder.
- **Thread safety.** PyMuPDF is not thread-safe: every real parse, by the index or by the pipeline through the cache, holds `PARSE_LOCK` (two threads asking for the same document parse it once).
- **Rebuilding is explicit.** `POST /api/index/rebuild` (the frontend's "Rebuild index" button on the Find page) parses everything again (`force`), builds the new cards and documents next to the old ones and replaces them at the end; searches keep using the old index meanwhile, and a failed rebuild leaves the old one in place. Only one build runs at a time (`409` otherwise). Nothing else ever re-parses.
- **Staleness is reported, not acted on.** `GET /api/status` compares the manifest with the disk: `stale` when the parser changed, a PDF changed or disappeared, or a regulation has no entry yet, each with a sentence in `staleReasons`. A stale index still works (a missing document is parsed on demand and stored). Only a missing index is built automatically (first start).
- **States:** `missing` (nothing built; a first build starts by itself), `building` (with `progress`: phase `cards` or `parsing`, done, total, current regulation), `ready`, `stale`, `failed` (with `error`).
- Not persisted on purpose: the model's answers (the pipeline's own `runs/_llm_cache` does that), the latest versions (section 9).

## 6. Jobs

`POST /api/analyses` stores the upload, creates a job and answers `202` at once; the work takes minutes, so the frontend polls `GET /api/analyses/{id}` every 1.5 s.

```
runs/web/<id>/
  job.json      state, written atomically; reloaded at startup
  input/        spec.md, drawing.<ext>: the case folder handed to the pipeline
  run/          the pipeline's run folder
  result.json   the adapter's output, kept once the job is done
  job.log       the pipeline's log lines and, on a failure, the traceback (never sent to the user)
```

- **One worker** runs the jobs in turn (`ThreadPoolExecutor(1)`): PyMuPDF is single-threaded and a run costs money. A job that waits, also for the first index build, is `queued`.
- **Uploads** (`uploads.py`): the pipeline wants one text spec and one image, so text files (UTF-8, no NUL bytes) become `spec.md` (several are joined in upload order under a `## <file name>` heading, at most 200,000 characters) and the first image becomes `drawing.<ext>`. The kind of a file is decided by its content (PNG, JPEG or WebP magic bytes, then a strict UTF-8 decode), never by its name; Pillow checks the image is not damaged. Refused with a clear message: a second image (400), PDF or Word files (415), binary or non-UTF-8 text (415), empty (400), over 10 MB (413), more than 20 files (400). File names are only used, cleaned, as headings in `spec.md`, never as paths.
- **Progress needs no change to the pipeline:** a stage is done when its artifact exists in `run/` (vision.json, profile.json, regulations.json, sections.json, submission.json, component_map.json); the first stage not done is `running`; `detail` is read from the artifact ("7 components found on the drawing", the chosen codes, "317 requirements").
- **Failures** end the job in `failed` with a plain `error` and the stage that was running marked `failed`: spending limit reached (`BudgetExceeded`), the model declined (`Refused`), key missing or rejected, rate limit, no connection, missing PDFs, anything else a generic line. The traceback is in `job.log`. A job that was queued or running when the process died is failed at the next start ("restarted while this search was running").
- **Cost:** each job gets `Settings.from_env(max_cost_usd=WEB_MAX_COST_USD)`; the pipeline stops before a call that would start above it.
- The `example` analysis (`/api/analyses/example`) is always finished and needs no key: the demo's safety net. It is built by the same adapter from `outputs/dev-rear-lamp-image/` (or from `src/backend/fixtures/example/` if a full recorded run is kept there), with hand-written regulation reasons and hand-measured dot positions (a live result puts a dot at the centre of the model's box, up to about 0.1 of the image off the leader line).

## 7. API

| Method and path | Request | Response |
|---|---|---|
| `GET /api/status` | | `{ apiKey, index: IndexStatus }` |
| `POST /api/index/rebuild` | | `202 IndexStatus`; `409` when a build is running |
| `POST /api/analyses` | `multipart/form-data`, field `files` repeated | `202 { id }` and a `Location` header; `400`, `413`, `415` (section 6); `503` without a key or without PDFs |
| `GET /api/analyses/{id}` | | `Analysis`: `status` (`queued`, `running`, `done`, `failed`), `stages`, `createdAt`, `error`, `result` when done; `404` for an unknown id (also for malformed ones: ids are 32 hex digits, or `example`) |
| `GET /api/analyses/{id}/drawing` | | the uploaded image; `404` if none |

Errors are `{ "detail": "<sentence>" }`. Optional fields are left out of the JSON, not sent as `null`. The models in `models.py` validate every response, so a field the frontend does not expect fails in a test rather than in the browser.

## 8. The result adapter (`adapter.py`)

A pure function of the run folder: no model, no network.

| Field | Source |
|---|---|
| `product` | `profile.json`: `product`, `summary`, `vehicle_categories` (without `unspecified`) |
| `regulations[]` | regulations that have at least one emitted requirement, in the order of `regulations.json` `selected[]`, then those added by the citation hop |
| `code`, `level`, `confidence`, `reason` | the `selected` entry. A regulation added by the citation hop has no level (the field is left out) and gets `medium`, which is what the pipeline treats it as |
| `title`, `version` | `regcomp.corpus` (`regulations/index.json`): the title and the **base** version label |
| `covers` | `selected[].covers` holds profile keys (`F1`, `P2`, `T1`), resolved to names with `profile.json` |
| `requirements[]` | `submission.json` grouped by regulation, in file order (document order) |
| `applies`, `kind` | `trace.json` entry with the same id; `unlikely` is never shown |
| `sectionTitle` | the breadcrumb of the node (`6 Individual specifications › 6.10 Rear position lamp › 6.10.4 Position › 6.10.4.2`) from the parse cache, cut at the segment that has the section's number: "Rear position lamp". Same grouping rule as the frontend (`6.10.4.2` is section `6.10`, `Annex 8 2.1` is `Annex 8`). None when the section has no heading of its own |
| `components[]` | `component_map.json`: `id`, `name`, `requirement_ids` (only ids that exist), `marker` = centre of the model's box for the component's `C*` key in `vision.json` |
| `wholeProductRequirementIds` | `component_map.json` |
| `drawing` | `/api/analyses/<id>/drawing` when an image was uploaded |
| `warnings` | one sentence per entry of `failures` in `run.json` (a failed section walk or extraction chunk, a failed component map) and per walk in `sections.json` with `finished: false`. The pipeline carries on after such a failure and returns what it has, which for a regulation may be less than there is, so the frontend says "This list may be incomplete". The error text stays on the server |

A failing title lookup (PDF missing) loses the titles, not the result.

## 9. Versioning and the sub-goal: what the parser supports (for the team)

The sub-goal of the challenge: given requirements derived from one version of a regulation and a later version, say which requirements change and why. **Nothing in the parser was changed**; this is what it already supports, checked on UN R175 (the sub-goal's dev regulation) with the base PDF from this checkout and the `latest` PDF fetched for the check.

**What the parser gives.** `regcomp.parse.Node` has what a version comparison needs at node level:
- `label` (the paragraph number in the gold's format), `page_start/page_end`, `path` (breadcrumb), `body`, and **`text_hash`**: a hash of what the node says that "ignores what a new version renumbers or re-sets": the number of a footnote, line breaks, whether a list is set inline. It is documented as built for telling a changed paragraph from a renumbered or re-flowed one.
- Base and latest PDFs parse the same way. R175 base (`0.1.0`): 17 pages, 195 paragraphs and tables; latest (`1.0.0`): 19 pages, 229. Footers agree with the physical pages in both (0 mismatches).
- Of the 195 base nodes, **180 keep both label and hash** in the latest version; 159 of those 180 moved to another page, so a diff by page would flag them and a diff by hash does not. 1 label exists only in base, 35 only in latest (the added provisions). This matches the 180 SAME / 13 MODIFIED / 2 REMOVED / 36 ADDED that `spec/finding/drift-agent.md` reports for the whole alignment.

**Where the versioning logic lives.** Not in the parser: in `src/ai_agent/drift.py` and `run_drift.py` (alignment by label and hash, then a similarity assignment for moved or edited paragraphs, then a model judge only for changed paragraphs that carry a requirement, then reasons built from a word diff). Measured by its authors: on the dev case 7 of 7 changed requirements flagged, 5 false flags among 87 unchanged, about $0.1 per run; on ten generated cases flagged recall 0.80 and precision 0.88 (`spec/finding/drift-agent.md`; golds of the generated cases are noisy).

**What is missing, to decide with the team** (none of it is a parser defect):
1. **The parser has no notion of a version.** Version labels come from `regulations/index.json` (`base`, `latest`; 36 of the 56 regulations have a `latest`). The footer of every page carries `UN R175, version 0.1.0 | page 4 of 17`, but the parser's footer rule matches the version and keeps only the page number. A check that the footer's version equals the index's label would catch a wrong file; it is not done.
2. **Only two versions per regulation exist** (base and latest): no history, so a requirement set derived from a middle version cannot be compared. The sub-goal as given needs only two.
3. **This checkout has only the base PDFs** (56). The latest PDFs (36 regulations) are not on disk, and the regulation index parses base only, because the main goal cites the base version (a page of the latest version counts as a different page). To serve the sub-goal from the same index, `KnowledgeIndex` would also parse `latest` (the key already has the role in it) and the PDFs would have to be fetched (`python tools/fetch_regulations.py --role latest`).
4. **The drift agent needs `requirements_old.json` as input** (the requirements derived from the old version, in the platform's format). This product does not keep requirement sets by version: a search result is not saved as such an input. A UI for the sub-goal would also have to ask for the old requirements or reuse a saved search.
5. **No API or UI for it yet**, and `drift.py` needs `scipy` and `numpy` (`linear_sum_assignment`), which `requirements.txt` does not list because the main flow does not use them; the repo's own drift tests fail without them (6 of 47 in `eval/test_ai_agent.py --unit` on this machine, all `ModuleNotFoundError: scipy`).
6. **Parser coverage:** the rules were written from five regulations and widened after a run over all 92 PDFs; `eval/health.py` flags 14 of them (`src/README.md`). Whether those include `latest` versions that matter for a hidden sub-goal case was not checked.

## 10. How it was checked

- **60 tests** (`python -m pytest src/backend/tests`): uploads (content sniffing, every refusal), the adapter (invariants on the recorded dev run: 317 requirements, 4 regulations, 7 markers, ids unique and all references resolve), the index on two real PDFs (first build, restart, forced rebuild, staleness by PDF and by parser, corrupt cache, thread safety, only one build), the jobs and API with a fake pipeline (stages while running, queue, failure messages, key never in a response, restart recovery, 404s, rebuild, serving the frontend), and **one test that runs the real `run_case` with a scripted model behind the API** over UN R150 (and UN R3, which it redirects to R150) and checks the adapter against the files the pipeline actually wrote, including that every citation's page lies in the page range of the node with that label.
- **Real runs on this machine:** the first start built the index from the 56 PDFs by itself (108 s, no problems, 16 MB); a restart found it ready and parsed nothing; a forced rebuild through the endpoint worked, refused a second one with 409, and replaced the files; the frontend (real mode is its default) read the status through the Vite proxy, showed the rebuild's progress and the example result with section titles from the parsed PDFs; a full upload in the browser ran against this backend with its pipeline replaced by a fake that writes the recorded dev run stage by stage (a 32-digit job id, progress details from the artifacts, 317 requirements, the drawing served by the backend, the result still there after a reload); one tiny call through `ai_agent.llm` confirmed the key and model work ($0.0005).
- **Not run:** a full analysis with the real model and a real drawing. The first one will show how the live dot positions look and whether the real component map and section titles read well.

## 11. Gotchas

- `KnowledgeIndex.install()` changes two globals of the pipeline (`corpus.DATA`, `store._parser`); the entry points call it, tests restore them (`conftest.isolate`).
- `GET /api/status` computes staleness from the disk each time (about 56 `stat` calls): cheap, but do not poll it faster than the frontend does (1.5 s while building, once otherwise).
- A reload of the dev server kills a running job; the job is marked failed at the next start.
- `uvicorn --reload` without `--reload-dir` watches `runs/` and restarts on every file a job writes.
- The first status after a start may say `building` for a moment before the first progress arrives (`progress.total` is 0 until the PDFs are listed).
- Do not call `Catalog().load()` or `parse_pdf` from another thread without `PARSE_LOCK`.

## 12. Next steps

1. **One real run** of the dev case through the UI (about $4, 7 minutes): check live dots, section titles, progress details, and keep the run's files in `src/backend/fixtures/example/` so the example shows a real live result.
2. Add the `anchor` point of a component to `vision.py`'s schema (where the leader line meets the part); the adapter would prefer it to the box centre. Small change in `ai_agent`, backward compatible.
3. Page images: `GET /api/regulations/{reg}/pages/{n}.png` rendered with PyMuPDF under `PARSE_LOCK`, cached under `runs/_pages/`, and a dialog in the frontend; `trace.json` has the verbatim `quote` to highlight with `page.search_for`.
4. Decide with the team what to do about the sub-goal (section 9) and whether the index should also hold the latest versions.
5. More inputs: PDF text extraction into the specification (PyMuPDF is already a dependency), several drawings (the pipeline uses one).
6. Decide how to treat `possible` requirements (hide by default in the UI, or a stricter emission policy through a request parameter): the dev case returns 317 against 190 expected.
7. Cancel a running job (the pipeline has no cancellation; skipping it is fine for the demo).
8. If the demo ever runs anywhere but localhost, put authentication in front: every upload spends money.
