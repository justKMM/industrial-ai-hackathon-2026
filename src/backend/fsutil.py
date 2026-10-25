"""Small file helpers shared by the index and the jobs."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    """Write JSON so that a reader never sees half a file: a temporary file in the same folder, then an atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    """The JSON in `path`, or `default` when the file is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
