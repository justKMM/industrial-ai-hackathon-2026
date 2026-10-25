"""Shared fixtures. No test calls the model or reads the real .env: the key is set (or removed) by the test itself."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_agent import store  # noqa: E402
from regcomp import corpus  # noqa: E402

from backend import settings  # noqa: E402
from backend.settings import Config  # noqa: E402

SMALL_REGULATIONS = ("UN R42", "UN R39")  # nine and thirteen pages: a build of both takes about a second


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """`KnowledgeIndex.install()` changes two module globals of the pipeline; put them back after every test. The real .env is never read."""
    data, parser = corpus.DATA, store._parser
    monkeypatch.setattr(settings, "load_env", lambda *a, **k: None)
    monkeypatch.setattr("ai_agent.config.load_env", lambda *a, **k: None)
    yield
    corpus.DATA, store._parser = data, parser


def _real_pdf_folder() -> Path | None:
    folder = settings.resolve_data_dir()
    return folder if (folder / "UN_R42" / "base").is_dir() else None


@pytest.fixture
def small_data(tmp_path) -> Path:
    """A regulations folder with two small PDFs in the layout tools/fetch_regulations.py writes."""
    real = _real_pdf_folder()
    if real is None:
        pytest.skip("the regulation PDFs are not on this machine (python tools/fetch_regulations.py)")
    target = tmp_path / "data"
    for reg in SMALL_REGULATIONS:
        entry = corpus.entry_for(reg)
        name = entry["versions"][0]["files"][0]["name"]
        slug = corpus.slug(reg)
        (target / slug / "base").mkdir(parents=True)
        shutil.copy(real / slug / "base" / name, target / slug / "base" / name)
    return target


def make_config(tmp_path: Path, data_dir: Path, **overrides) -> Config:
    return Config(runs_dir=tmp_path / "runs", web_dir=tmp_path / "runs" / "web", index_dir=tmp_path / "runs" / "_index", data_dir=data_dir,
                  auto_build_index=False, **overrides)
