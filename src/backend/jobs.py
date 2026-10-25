"""Analyses as background jobs: stored on disk, run one at a time, followed through the files the pipeline writes.

    runs/web/<id>/
      job.json      the job's state (written atomically; reloaded at startup)
      input/        the case folder handed to the pipeline: spec.md, drawing.<ext>
      run/          the pipeline's run folder (profile.json, regulations.json, ..., submission.json)
      result.json   the adapter's output, kept once the job is done
      job.log       the pipeline's log lines, and the traceback of a failure (never shown to the user)

One worker runs the jobs in turn: PyMuPDF is not thread-safe, and a run costs real money. A job that is waiting is `queued`.
Progress needs no change to the pipeline: a stage is done when its artifact exists in the run folder.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_agent.config import MissingKey, Settings

from backend.adapter import build_result, load_artifacts
from backend.fsutil import read_json, write_json
from backend.knowledge import IndexNotReady, KnowledgeIndex
from backend.settings import Config, redact

log = logging.getLogger("regal.jobs")

STAGES = ("vision", "profile", "regulations", "sections", "obligations", "components")
ARTIFACT = {"vision": "vision.json", "profile": "profile.json", "regulations": "regulations.json", "sections": "sections.json",
            "obligations": "submission.json", "components": "component_map.json"}
JOB_ID = re.compile(r"^[0-9a-f]{32}$")


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    created_at: float
    status: str = "queued"  # queued, running, done, failed
    files: list[dict] = field(default_factory=list)
    has_drawing: bool = False
    finished_at: float | None = None
    error: str | None = None
    failed_stage: str | None = None
    problems: list[str] = field(default_factory=list)  # what validate.py found in the submission (the operator's information)
    failures: list[dict] = field(default_factory=list)  # stages of the pipeline that failed without losing the run
    spent_usd: float | None = None


class JobStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    # paths ---------------------------------------------------------------------------------------------------------------
    def dir(self, job_id: str) -> Path:
        if not JOB_ID.match(job_id):
            raise KeyError(job_id)  # an id is generated here; anything else is never turned into a path
        return self.root / job_id

    def input_dir(self, job_id: str) -> Path:
        return self.dir(job_id) / "input"

    def run_dir(self, job_id: str) -> Path:
        return self.dir(job_id) / "run"

    def drawing_path(self, job_id: str) -> Path | None:
        folder = self.input_dir(job_id)
        return next((p for p in sorted(folder.glob("drawing.*")) if p.is_file()), None) if folder.is_dir() else None

    # state ---------------------------------------------------------------------------------------------------------------
    def create(self, files: list[dict], has_drawing: bool) -> Job:
        job = Job(id=uuid.uuid4().hex, created_at=time.time(), files=files, has_drawing=has_drawing)
        self.dir(job.id).mkdir(parents=True, exist_ok=True)
        self.save(job)
        return job

    def save(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            write_json(self.dir(job.id) / "job.json", asdict(job))

    def get(self, job_id: str) -> Job | None:
        if not JOB_ID.match(job_id):
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def load_existing(self) -> int:
        """Read the jobs of earlier runs of the backend. One that was still queued or running died with the process: it is failed."""
        count = 0
        for file in sorted(self.root.glob("*/job.json")) if self.root.is_dir() else []:
            data = read_json(file)
            if not isinstance(data, dict) or not JOB_ID.match(str(data.get("id", ""))):
                continue
            job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
            if job.status in ("queued", "running"):
                job.failed_stage = first_unfinished(self.run_dir(job.id), job.has_drawing)
                job.status, job.error, job.finished_at = "failed", "The backend was restarted while this search was running. Start it again.", time.time()
                self.save(job)
            self._jobs[job.id] = job
            count += 1
        return count


# ------------------------------------------------------------------------------------------------------------------ stages
def _done(run_dir: Path, stage: str) -> bool:
    return (run_dir / ARTIFACT[stage]).is_file()


def first_unfinished(run_dir: Path, has_drawing: bool) -> str | None:
    """The first stage whose artifact is not there yet (the stage a failure or the current work belongs to)."""
    for stage in STAGES:
        if stage == "vision" and not has_drawing:
            continue
        if not _done(run_dir, stage):
            return stage
    return None


def _detail(run_dir: Path, stage: str) -> str | None:
    """A short fact about a finished stage, read from its artifact."""
    data = read_json(run_dir / ARTIFACT[stage])
    if data is None:
        return None
    if stage == "vision":
        return f"{len(data.get('components', []))} components found on the drawing"
    if stage == "profile":
        return f"{len(data.get('parts', []))} parts, {len(data.get('functions', []))} functions"
    if stage == "regulations":
        return ", ".join(s["regulation"] for s in data.get("selected", [])) or "none"
    if stage == "sections":
        return f"{sum(v.get('provisions', 0) for v in data.values() if isinstance(v, dict))} provisions selected"
    if stage == "obligations":
        return f"{len(data.get('requirements', []))} requirements"
    if stage == "components":
        return f"{len(data.get('components', []))} components"
    return None


def stages_of(job: Job, run_dir: Path) -> list[dict]:
    """The six stages with their status, from the job's state and the artifacts in the run folder."""
    out = []
    if job.status == "queued":
        return [{"id": s, "status": "skipped" if s == "vision" and not job.has_drawing else "pending"} for s in STAGES]
    current = job.failed_stage if job.status == "failed" else first_unfinished(run_dir, job.has_drawing)
    for stage in STAGES:
        if stage == "vision" and not job.has_drawing:
            out.append({"id": stage, "status": "skipped"})
        elif _done(run_dir, stage):
            out.append({"id": stage, "status": "done", "detail": _detail(run_dir, stage)})
        elif job.status == "done":  # finished without this artifact: the component map is the one the pipeline may lose
            out.append({"id": stage, "status": "skipped", "detail": "Not available for this run."})
        elif stage == current:
            out.append({"id": stage, "status": "failed" if job.status == "failed" else "running"})
        else:
            out.append({"id": stage, "status": "pending"})
    return out


# ------------------------------------------------------------------------------------------------------------------- errors
def explain(error: BaseException) -> str:
    """What the user is told when a job fails: plain words, never a traceback and never the API key."""
    try:
        from ai_agent.llm import BudgetExceeded, Refused

        if isinstance(error, BudgetExceeded):
            return f"The search was stopped because it reached its spending limit. {error}"
        if isinstance(error, Refused):
            return "The model declined to analyse these documents."
    except ImportError:  # the Anthropic SDK is not installed: the pipeline could not even start
        return "The backend is missing a dependency of the pipeline (pip install -r src/backend/requirements.txt)."
    if isinstance(error, MissingKey):
        return "The backend has no Anthropic API key. Add AI_AGENT_KEY to the .env file in the repository root and restart it."
    if isinstance(error, (IndexNotReady, FileNotFoundError)):
        return f"The regulation PDFs are not available. {error}"
    try:
        import anthropic

        if isinstance(error, anthropic.AuthenticationError):
            return "The Anthropic API rejected the key. Check AI_AGENT_KEY in the .env file."
        if isinstance(error, anthropic.RateLimitError):
            return "The Anthropic API is rate limiting this key. Try again in a few minutes."
        if isinstance(error, anthropic.APIConnectionError):
            return "The Anthropic API could not be reached. Check the internet connection and try again."
    except ImportError:
        pass
    return "Something went wrong while analysing the documents. The details are in the job log on the server."


# ------------------------------------------------------------------------------------------------------------------- runner
def run_pipeline(*, case_dir: Path, settings: Settings, run_dir: Path, log: Callable[[str], None], catalog) -> Any:
    """The real pipeline. Imported here so that importing the backend does not need the Anthropic SDK."""
    from ai_agent.pipeline import run_case

    return run_case(case_dir, settings, run_dir, log=log, catalog=catalog, component_map=True)


class Runner:
    def __init__(self, store: JobStore, knowledge: KnowledgeIndex, config: Config, pipeline: Callable[..., Any] = run_pipeline):
        self.store, self.knowledge, self.config, self.pipeline = store, knowledge, config, pipeline
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")

    def submit(self, job: Job) -> None:
        self._pool.submit(self._run, job.id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def drawing_url(self, job: Job) -> str | None:
        return f"/api/analyses/{job.id}/drawing" if job.has_drawing else None

    def build(self, job: Job) -> dict:
        return build_result(load_artifacts(self.store.run_dir(job.id)), self.drawing_url(job), self.knowledge.breadcrumbs)

    def _run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        job_dir = self.store.dir(job_id)
        log_file = job_dir / "job.log"
        lock = threading.Lock()  # the pipeline logs from several threads

        def write(line: str) -> None:
            with lock, log_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{time.strftime('%H:%M:%S')} {redact(line)}\n")

        try:
            catalog = self.knowledge.catalog()  # the first build of the index may still be running: the job stays queued until it is done
            settings = Settings.from_env(max_cost_usd=self.config.web_max_cost_usd)
            job.status = "running"
            self.store.save(job)
            outcome = self.pipeline(case_dir=self.store.input_dir(job_id), settings=settings, run_dir=self.store.run_dir(job_id), log=write, catalog=catalog)
            job.problems, job.failures = list(getattr(outcome, "problems", [])), list(getattr(outcome, "failures", []))
            job.spent_usd = (getattr(outcome, "ledger", None) or {}).get("spent_usd")
            write_json(job_dir / "result.json", self.build(job))
            job.status = "done"
        except Exception as error:  # a job must end in done or failed, whatever went wrong
            job.failed_stage = first_unfinished(self.store.run_dir(job_id), job.has_drawing)
            job.status, job.error = "failed", explain(error)
            with lock, log_file.open("a", encoding="utf-8") as handle:
                handle.write(redact(traceback.format_exc()))
            log.warning("analysis %s failed: %s", job_id, type(error).__name__)
        finally:
            job.finished_at = time.time()
            self.store.save(job)

    # the answer of GET /api/analyses/{id} ------------------------------------------------------------------------------------
    def view(self, job: Job) -> dict:
        view: dict[str, Any] = {"id": job.id, "status": job.status, "createdAt": iso(job.created_at),
                                "stages": stages_of(job, self.store.run_dir(job.id))}
        if job.status == "failed":
            view["error"] = job.error or "The search failed."
        if job.status == "done":
            cached = read_json(self.store.dir(job.id) / "result.json")
            view["result"] = cached if cached is not None else self.build(job)
        return view
