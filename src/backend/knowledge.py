"""The persistent regulation index: what the parser learned from the PDFs, built once and kept on disk.

Two things are expensive and are kept:

  * the regulation cards (`ai_agent.catalog`): title, scope, table of contents and supersession of every regulation, which the
    pipeline reads in one prompt to choose the regulations. Stored as JSON by `ai_agent.catalog.Catalog`.
  * the parsed documents (`regcomp.parse.ParsedDocument`: every paragraph and table with label, page range, breadcrumb and text) of the
    base version of every regulation, which `ai_agent.store.RegGraph` builds its graph from on every run. Pickled, one file per PDF.

Everything lives under `runs/_index/` and is keyed by the parser: the hash of the parser's source file is part of the folder name, so
changing the parser makes the old files unreachable by itself. A PDF that changes on disk gets a new file too (its size and time are in
the file name). Nothing is rebuilt otherwise: only `start_build()` re-parses, which the frontend's "Rebuild index" button calls.

The pipeline is not touched. `install()` makes it use this cache by replacing `ai_agent.store._parser`, the function `RegGraph` asks for
its parser, with one that reads the cache first; and points `regcomp.corpus.DATA` at the folder that really holds the PDFs.

PyMuPDF is not thread-safe, so every real parse (here, and by the pipeline through the cache) holds PARSE_LOCK.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import regcomp.parse as parse_module
from ai_agent import catalog as catalog_module
from ai_agent import store
from ai_agent.catalog import Catalog
from regcomp import corpus

from backend.fsutil import read_json, write_json
from backend.settings import redact

log = logging.getLogger("regal.index")

PARSE_LOCK = threading.RLock()
MANIFEST_VERSION = 1

# `store._parser` as the pipeline ships it. Kept once, so that installing the cache twice (tests build several apps) never wraps a wrapper.
_ORIGINAL_PARSER = getattr(store._parser, "_regal_original", store._parser)
_CARD_LINE = re.compile(r"^\[catalog\] card (\d+)/(\d+): (.+)$")


class IndexNotReady(RuntimeError):
    """There is nothing to run the pipeline on: no regulation PDFs could be found."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parser_fingerprint() -> tuple[str, str]:
    """(parser name, hash of its source). The name follows REGCOMP_PARSER as `ai_agent.store` does."""
    name = os.environ.get("REGCOMP_PARSER", "rules")
    folder = Path(parse_module.__file__).parent
    digest = hashlib.sha1((folder / "parse.py").read_bytes())
    if name == "marker":
        digest.update((folder / "parse_marker.py").read_bytes())
    return name, digest.hexdigest()[:8]


class KnowledgeIndex:
    def __init__(self, data_dir: Path, index_dir: Path):
        self.data_dir = Path(data_dir)
        self.index_dir = Path(index_dir)
        self.cards_dir = self.index_dir / "cards"
        self.manifest_path = self.index_dir / "manifest.json"
        self.parser_name, self.parser_hash = parser_fingerprint()
        self.parser_id = f"{self.parser_name}-{self.parser_hash}"
        self.parsed_dir = self.index_dir / "parsed" / self.parser_id

        self._lock = threading.Lock()  # guards the build state below
        self._catalog_lock = threading.Lock()
        self._building = False
        self._done = threading.Event()
        self._done.set()
        self._progress: dict[str, Any] | None = None
        self._error: str | None = None
        self._catalog: Catalog | None = None

    # ------------------------------------------------------------------------------------------------------------ wiring
    def install(self) -> None:
        """Make the pipeline read its PDFs from `data_dir` and its parsed documents from this index. Idempotent; the entry points below
        call it, so an index that is used without the app (a script, a test) cannot look in the wrong folder."""
        corpus.DATA = self.data_dir

        def patched():
            return self.parse

        patched._regal_original = _ORIGINAL_PARSER  # type: ignore[attr-defined]
        store._parser = patched

    def ensure_started(self, auto_build: bool = True) -> None:
        """At startup: when there is no index at all, build it in the background. An existing one is left alone, even a stale one."""
        if auto_build and self._read_manifest() is None and not self._building:
            self.start_build(force=False)

    # ------------------------------------------------------------------------------------------------------- parse cache
    def _parsed_file(self, path: Path, grids: bool) -> Path:
        stat = path.stat()
        name = f"{path.parent.parent.name}__{path.parent.name}__{'grids' if grids else 'text'}__{stat.st_size}-{stat.st_mtime_ns}.pkl"
        return self.parsed_dir / name

    @staticmethod
    def _load(file: Path):
        try:
            with file.open("rb") as handle:
                return pickle.load(handle)
        except FileNotFoundError:
            return None
        except Exception:  # a truncated or incompatible file is a cache miss, never an error
            log.warning("unreadable parse cache file %s: parsing again", file.name)
            return None

    def _store(self, file: Path, doc) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(f".{threading.get_ident()}.tmp")
        with tmp.open("wb") as handle:
            pickle.dump(doc, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, file)

    def parse(self, path: str | Path, grids: bool = True, refresh: bool = False):
        """`regcomp.parse.parse_pdf` through the cache: the stored document when there is one, else parse, store and return.
        `refresh` parses again and overwrites. Every call returns a fresh object (the file is read each time), so no run can change
        what the next one sees."""
        path = Path(path)
        file = self._parsed_file(path, grids)
        if not refresh:
            doc = self._load(file)
            if doc is not None:
                return doc
        with PARSE_LOCK:
            if not refresh:
                doc = self._load(file)  # parsed by another thread while this one waited for the lock
                if doc is not None:
                    return doc
            doc = _ORIGINAL_PARSER()(path, grids=grids)
            self._store(file, doc)
        return doc

    def breadcrumbs(self, regulation: str) -> dict[str, str]:
        """Paragraph label to breadcrumb path ("6 Individual specifications › 6.10 Rear position lamp › 6.10.4 Position › 6.10.4.2") for
        every paragraph and table of the base version of a regulation. Empty when its PDF is not there."""
        try:
            path = corpus.pdf_path(corpus.entry_for(regulation), "base")
        except KeyError:
            return {}
        if path is None:
            return {}
        paths: dict[str, str] = {}
        for node in self.parse(path, grids=True).nodes:  # grids=True: the entry the pipeline's RegGraph already stored
            if node.kind in ("para", "table") and node.label and node.label not in paths:
                paths[node.label] = node.path
        return paths

    # ----------------------------------------------------------------------------------------------------------- catalog
    def catalog(self, timeout: float | None = None) -> Catalog:
        """The loaded regulation cards. Waits for a build that is running; builds the cards if the index has none."""
        if self._catalog is not None:
            return self._catalog
        self.install()
        if self._building:
            self._done.wait(timeout)
        with self._catalog_lock:
            if self._catalog is None:
                catalog = Catalog(cache_dir=self.cards_dir)
                if not catalog.names:
                    raise IndexNotReady(f"No regulation PDFs found in {self.data_dir}. Fetch them with: python tools/fetch_regulations.py --out regulations/data")
                with PARSE_LOCK:
                    catalog.load(log=self._on_catalog_log)
                self._catalog = catalog
            return self._catalog

    def _on_catalog_log(self, message: str) -> None:
        match = _CARD_LINE.match(message)
        if match:
            self._set_progress("cards", int(match.group(1)) - 1, int(match.group(2)), match.group(3))

    # ------------------------------------------------------------------------------------------------------------ build
    def start_build(self, force: bool = False) -> bool:
        """Build the index in a background thread. False when a build is already running. `force` parses everything again."""
        self.install()
        with self._lock:
            if self._building:
                return False
            self._building = True
            self._done.clear()
            self._error = None
            self._progress = {"phase": "cards", "done": 0, "total": 0}
        threading.Thread(target=self._build, args=(force,), name="index-build", daemon=True).start()
        return True

    def _set_progress(self, phase: str, done: int, total: int, current: str | None = None) -> None:
        with self._lock:
            if self._building:
                self._progress = {"phase": phase, "done": done, "total": total, **({"current": current} if current else {})}

    def _build(self, force: bool) -> None:
        started = time.time()
        try:
            entries = [(e["regulation"], corpus.pdf_path(e, "base")) for e in corpus.load_index()]
            entries = [(reg, path) for reg, path in entries if path is not None]
            if not entries:
                raise IndexNotReady(f"No regulation PDFs found in {self.data_dir}. Fetch them with: python tools/fetch_regulations.py --out regulations/data")

            # 1. the cards. A forced build reads every PDF again and replaces the file at the end; the old file stays usable until then.
            self._set_progress("cards", 0, len(entries))
            cards_file = self.cards_dir / f"cards-{catalog_module.parser_hash()}.json"
            if force or not cards_file.is_file():
                fresh = Catalog(cache_dir=None)
                with PARSE_LOCK:
                    fresh.load(log=self._on_catalog_log)
                write_json(cards_file, fresh.cards)
                catalog = fresh
            else:
                catalog = Catalog(cache_dir=self.cards_dir)
                with PARSE_LOCK:
                    catalog.load(log=self._on_catalog_log)

            # 2. the parsed documents, one pickle per PDF; a failure is recorded and the build goes on
            regulations: dict[str, dict] = {}
            problems: list[str] = []
            for k, (reg, path) in enumerate(entries):
                self._set_progress("parsing", k, len(entries), reg)
                t0 = time.time()
                try:
                    doc = self.parse(path, grids=True, refresh=force)
                    stat = path.stat()
                    regulations[reg] = {"role": "base", "pages": doc.pages, "nodes": len(doc.nodes), "seconds": round(time.time() - t0, 2),
                                        "size": stat.st_size, "mtimeNs": stat.st_mtime_ns}
                except Exception as error:
                    problems.append(f"{reg}: {type(error).__name__}: {redact(str(error))}")
                    log.exception("could not parse %s", reg)

            write_json(self.manifest_path, {
                "version": MANIFEST_VERSION, "parser": self.parser_name, "parserHash": self.parser_hash, "builtAt": _now(),
                "seconds": round(time.time() - started, 1), "dataDir": str(self.data_dir), "regulations": regulations, "problems": problems})
            self._catalog = catalog
            self._forget_old_parsers()
            log.info("regulation index built: %d regulations in %.0f s, %d problems", len(regulations), time.time() - started, len(problems))
        except Exception as error:
            self._error = redact(str(error)) or type(error).__name__
            log.exception("regulation index build failed")
        finally:
            with self._lock:
                self._building = False
                self._progress = None
                self._done.set()

    def _forget_old_parsers(self) -> None:
        """Delete what other versions of the parser stored: it can never be read again."""
        parsed_root = self.parsed_dir.parent
        if parsed_root.is_dir():
            for folder in parsed_root.iterdir():
                if folder.is_dir() and folder.name != self.parser_id:
                    shutil.rmtree(folder, ignore_errors=True)
        keep = f"cards-{catalog_module.parser_hash()}.json"
        if self.cards_dir.is_dir():
            for file in self.cards_dir.glob("cards-*.json"):
                if file.name != keep:
                    file.unlink(missing_ok=True)

    # ----------------------------------------------------------------------------------------------------------- status
    def _read_manifest(self) -> dict | None:
        manifest = read_json(self.manifest_path)
        return manifest if isinstance(manifest, dict) and manifest.get("version") == MANIFEST_VERSION else None

    def _current_pdfs(self) -> dict[str, Path]:
        try:
            pairs = [(e["regulation"], corpus.pdf_path(e, "base")) for e in corpus.load_index()]
        except Exception:
            return {}
        return {reg: path for reg, path in pairs if path is not None}

    def _stale_reasons(self, manifest: dict, current: dict[str, Path]) -> list[str]:
        reasons: list[str] = []
        if manifest.get("parserHash") != self.parser_hash or manifest.get("parser") != self.parser_name:
            reasons.append("The parser changed since the index was built.")
        built = manifest.get("regulations", {})
        changed = []
        for reg, entry in built.items():
            path = current.get(reg)
            if path is None:
                changed.append(reg)
                continue
            stat = path.stat()
            if stat.st_size != entry.get("size") or stat.st_mtime_ns != entry.get("mtimeNs"):
                changed.append(reg)
        if changed:
            reasons.append(f"{len(changed)} regulation PDF(s) changed or disappeared: {', '.join(sorted(changed)[:6])}{' …' if len(changed) > 6 else ''}.")
        new = sorted(set(current) - set(built))
        if new:
            reasons.append(f"{len(new)} regulation(s) are not in the index yet: {', '.join(new[:6])}{' …' if len(new) > 6 else ''}.")
        return reasons

    def status(self) -> dict:
        """The index as the frontend shows it (camelCase keys, see backend.models.IndexStatus)."""
        with self._lock:
            building, progress, error = self._building, dict(self._progress) if self._progress else None, self._error
        manifest = self._read_manifest()
        current = self._current_pdfs()
        base: dict[str, Any] = {"parser": self.parser_id, "total": len(current), "regulations": len((manifest or {}).get("regulations", {})),
                                "staleReasons": [], "problems": list((manifest or {}).get("problems", []))}
        if manifest:
            base["builtAt"] = manifest.get("builtAt")
            base["seconds"] = manifest.get("seconds")
        if building:
            return {**base, "state": "building", "progress": progress}
        if error:
            return {**base, "state": "failed", "error": error}
        if manifest is None:
            return {**base, "state": "missing",
                    "error": None if current else f"No regulation PDFs found in {self.data_dir}. Fetch them with: python tools/fetch_regulations.py --out regulations/data"}
        reasons = self._stale_reasons(manifest, current)
        return {**base, "state": "stale" if reasons else "ready", "staleReasons": reasons}
