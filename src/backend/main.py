"""regal.ai backend: the HTTP layer between the frontend and the pipeline in src/ai_agent.

Run it from the repository root (so that src/ is importable), or from this folder with `fastapi dev main.py`:

    uvicorn backend.main:app --app-dir src --reload --reload-dir src/backend --reload-dir src/ai_agent --reload-dir src/regcomp

The Anthropic key is read from the git-ignored `.env` in the repository root (`AI_AGENT_KEY=sk-ant-...`); see spec.md.

    GET  /api/status                    key present? state of the regulation index
    POST /api/index/rebuild             parse every regulation PDF again (the only thing that ever does)
    POST /api/analyses                  upload documents, start an analysis (202 with its id)
    GET  /api/analyses/{id}             progress, then the result. `example` is a recorded run that needs no key
    GET  /api/analyses/{id}/drawing     the uploaded drawing

The business logic is in the modules next to this file; the handlers below only translate between HTTP and them.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1])
if _SRC not in sys.path:  # when started as `main:app` from this folder, `backend` is not importable yet
    sys.path.insert(0, _SRC)

import logging  # noqa: E402
import mimetypes  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any, Callable  # noqa: E402

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from backend import models  # noqa: E402
from backend.example import EXAMPLE_ID, Example  # noqa: E402
from backend.jobs import JobStore, Runner, run_pipeline  # noqa: E402
from backend.knowledge import KnowledgeIndex  # noqa: E402
from backend.settings import MAX_FILE_BYTES, Config, api_key_present  # noqa: E402
from backend.uploads import UploadError, clean_name, prepare  # noqa: E402

NO_KEY = "The backend has no Anthropic API key. Add AI_AGENT_KEY to the .env file in the repository root and restart it."


@dataclass
class Services:
    config: Config
    knowledge: KnowledgeIndex
    store: JobStore
    runner: Runner
    example: Example


def _services(request: Request) -> Services:
    return request.app.state.services


def create_app(config: Config | None = None, pipeline: Callable[..., Any] = run_pipeline) -> FastAPI:
    """Build the app. `config` and `pipeline` exist for the tests (temporary folders, a pipeline that does not call the model)."""
    config = config or Config.from_env()
    logger = logging.getLogger("regal")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        knowledge = KnowledgeIndex(config.data_dir, config.index_dir)
        knowledge.install()
        store = JobStore(config.web_dir)
        store.load_existing()
        app.state.services = Services(config, knowledge, store, Runner(store, knowledge, config, pipeline), Example(config, knowledge.breadcrumbs))
        knowledge.ensure_started(config.auto_build_index)  # the first start builds the index; later ones leave it alone
        if not api_key_present():
            logger.warning("AI_AGENT_KEY is not set: searches are refused until it is added to .env (the example still works)")
        yield
        app.state.services.runner.shutdown()

    app = FastAPI(title="regal.ai backend", lifespan=lifespan)

    @app.get("/api/status", response_model=models.BackendStatus, response_model_exclude_none=True)
    def status(request: Request):
        """Whether searches can run (the API key) and how the regulation index stands. Never returns the key."""
        return {"apiKey": api_key_present(), "index": _services(request).knowledge.status()}

    @app.post("/api/index/rebuild", status_code=202, response_model=models.IndexStatus, response_model_exclude_none=True)
    def rebuild_index(request: Request):
        """Parse every regulation PDF again and replace the stored index. Searches keep working on the old one meanwhile."""
        knowledge = _services(request).knowledge
        if not knowledge.start_build(force=True):
            raise HTTPException(409, "The regulation index is already being built.")
        return knowledge.status()

    @app.post("/api/analyses", status_code=202, response_model=models.StartedAnalysis)
    async def start_analysis(request: Request, response: Response, files: list[UploadFile] = File(...)):
        """Store the uploaded documents and queue an analysis. Answers at once; the work takes minutes (follow it with GET)."""
        services = _services(request)
        if not api_key_present():
            raise HTTPException(503, NO_KEY)
        index = services.knowledge.status()
        if index["total"] == 0:
            raise HTTPException(503, index.get("error") or "No regulation PDFs were found. Fetch them with: python tools/fetch_regulations.py --out regulations/data")
        received: list[tuple[str, bytes]] = []
        for upload in files:
            data = await upload.read(MAX_FILE_BYTES + 1)  # one byte more than allowed is enough to refuse it
            received.append((upload.filename or "file", data))
        try:
            prepared = prepare(received)
        except UploadError as error:
            raise HTTPException(error.status, error.detail) from None
        job = services.store.create(prepared.files, has_drawing=prepared.image is not None)
        prepared.write(services.store.input_dir(job.id))
        services.runner.submit(job)
        response.headers["Location"] = f"/api/analyses/{job.id}"
        return {"id": job.id}

    @app.get("/api/analyses/{analysis_id}", response_model=models.Analysis, response_model_exclude_none=True)
    def get_analysis(analysis_id: str, request: Request):
        """The state of an analysis: its stages while it runs, the result when it is done, the error when it failed."""
        services = _services(request)
        if analysis_id == EXAMPLE_ID:
            example = services.example.analysis()
            if example is None:
                raise HTTPException(404, "The example run is not in the repository (outputs/dev-rear-lamp-image).")
            return example
        job = services.store.get(analysis_id)
        if job is None:
            raise HTTPException(404, "This analysis no longer exists.")
        return services.runner.view(job)

    @app.get("/api/analyses/{analysis_id}/drawing")
    def get_drawing(analysis_id: str, request: Request):
        """The drawing that was uploaded with the analysis."""
        services = _services(request)
        if analysis_id == EXAMPLE_ID:
            path = services.example.drawing_path()
        else:
            job = services.store.get(analysis_id)
            path = services.store.drawing_path(job.id) if job else None
        if path is None:
            raise HTTPException(404, "No drawing was uploaded for this analysis.")
        return FileResponse(path, media_type=mimetypes.guess_type(clean_name(path.name))[0] or "application/octet-stream")

    dist = config.root / "src" / "frontend" / "dist"
    if config.serve_frontend and (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")  # last: the routes above win
    else:

        @app.get("/")
        def root():
            return {"name": "regal.ai backend", "docs": "/docs", "status": "/api/status"}

    return app


app = create_app()
