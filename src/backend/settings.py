"""Paths, limits and environment of the backend.

The Anthropic key is never handled here. It lives in the git-ignored `.env` at the repository root (`AI_AGENT_KEY`), which
`ai_agent.config` reads; this module only asks whether it is there (`api_key_present`) and never returns or logs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ai_agent.config import ROOT, load_env

MAX_FILE_BYTES = 10 * 1024 * 1024  # per uploaded file; the same constant as src/frontend/src/lib/upload.ts
MAX_TEXT_CHARS = 200_000  # all text files of one upload together: it goes to a model
MAX_FILES = 20
DEFAULT_WEB_MAX_COST_USD = 8.0  # the pipeline's own default is 25; a web run is stopped earlier


def resolve_data_dir() -> Path:
    """Where the regulation PDFs are. `regcomp.corpus` looks in regulations/data, but tools/fetch_regulations.py writes to regulations/pdf
    unless told otherwise, so a fresh checkout has them there: take regulations/data when it exists, else regulations/pdf.
    REGULATIONS_DIR overrides both."""
    configured = os.environ.get("REGULATIONS_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    for name in ("data", "pdf"):
        folder = ROOT / "regulations" / name
        if folder.is_dir():
            return folder
    return ROOT / "regulations" / "data"


def api_key_present() -> bool:
    """Whether AI_AGENT_KEY is set in the environment or in the repository's .env. Never returns the key.

    `load_env` never overrides a variable that is already set, and an empty `AI_AGENT_KEY=` line counts as set. So an empty value read
    earlier is dropped first: a key pasted into .env while the backend runs is found by the next request, without a restart."""
    if not os.environ.get("AI_AGENT_KEY", "").strip():
        os.environ.pop("AI_AGENT_KEY", None)
    load_env()
    return bool(os.environ.get("AI_AGENT_KEY", "").strip())


def redact(text: str) -> str:
    """Remove the API key from a message before it is stored or shown (an SDK error should never contain it, but a message is cheap to scrub)."""
    key = os.environ.get("AI_AGENT_KEY", "").strip()
    return text.replace(key, "***") if key and key in text else text


@dataclass(frozen=True)
class Config:
    root: Path = ROOT
    runs_dir: Path = ROOT / "runs"
    web_dir: Path = ROOT / "runs" / "web"  # one folder per analysis: input, run, job.json, result.json, job.log
    index_dir: Path = ROOT / "runs" / "_index"  # the persistent regulation index: cards, parsed documents, manifest
    data_dir: Path = field(default_factory=resolve_data_dir)
    outputs_dir: Path = ROOT / "outputs"
    cases_dir: Path = ROOT / "cases"
    web_max_cost_usd: float = DEFAULT_WEB_MAX_COST_USD
    auto_build_index: bool = True  # build the index at startup when there is none yet
    serve_frontend: bool = False  # serve src/frontend/dist at / (one process is the whole demo)

    @classmethod
    def from_env(cls) -> "Config":
        load_env()
        cost = os.environ.get("WEB_MAX_COST_USD", "").strip()
        return cls(
            web_max_cost_usd=float(cost) if cost else DEFAULT_WEB_MAX_COST_USD,
            serve_frontend=os.environ.get("SERVE_FRONTEND", "").strip().lower() in ("1", "true", "yes", "on"),
        )
