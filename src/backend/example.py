"""The `example` analysis: a recorded run of the dev case (a rear lamp) that is always finished and needs no API key.

It is what the frontend's "View an example result" opens, and the demo's safety net when the key or the network fails. It is built by the
same adapter as a live result, from the first of these that exists:

  1. src/backend/fixtures/example/    the files of a full run (profile.json, regulations.json, trace.json, submission.json, ...), kept after a real run
  2. outputs/dev-rear-lamp-image/     the recorded run in the repository (submission, component map, vision, profile.md): the profile and the reason
                                      each regulation applies are not in it, so they are filled in below (the same text as the frontend's mock)
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.adapter import Breadcrumbs, build_result, load_artifacts
from backend.fsutil import read_json
from backend.settings import Config

EXAMPLE_ID = "example"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "example"

# Where the leader lines of exploded_view.png end (the black dots of the drawing), 0 to 1 from the top left, measured by hand. A live result
# puts each dot at the centre of the box the model drew round the part, which can be 0.1 of the image away; the example is a showpiece, so
# its dots sit exactly on the drawing.
MARKERS = {
    "Outer lens": (0.08, 0.248),
    "Retro-reflector": (0.229, 0.267),
    "Seal / gasket": (0.162, 0.351),
    "Reflector": (0.286, 0.39),
    "LED modules on PCB": (0.2845, 0.617),
    "Housing": (0.345, 0.767),
    "Fasteners / clips": (0.37, 0.879),
}

REGULATIONS = {
    "UN R48": ("vehicle", "high", "Sets how the lamps and the retro-reflector are installed on an M1 vehicle: number, position, visibility angles, colour and electrical connections."),
    "UN R148": ("device", "high", "Approves the rear position, stop and reversing lamp functions as devices: photometry, colour, markings and test procedures. It combines the older R7 and R23."),
    "UN R150": ("device", "high", "Approves the retro-reflector as a device: photometric and colorimetric performance, physical tests and markings. It replaces the older R3."),
    "UN R10": ("horizontal", "medium", "The LED modules on a circuit board make the lamp an electronic sub-assembly, so the electromagnetic compatibility requirements apply."),
}


def _profile_line(markdown: str, label: str) -> str:
    match = re.search(rf"^{label}:\s*(.+)$", markdown, re.M)
    return match.group(1).strip() if match else ""


class Example:
    def __init__(self, config: Config, breadcrumbs: Breadcrumbs | None = None):
        self.config, self.breadcrumbs = config, breadcrumbs
        self.sample_dir = config.outputs_dir / "dev-rear-lamp-image"
        self._analysis: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def drawing_path(self) -> Path | None:
        path = self.config.cases_dir / "dev-rear-lamp" / "exploded_view.png"
        return path if path.is_file() else None

    def _artifacts(self) -> tuple[dict[str, Any], float] | None:
        if (FIXTURE_DIR / "submission.json").is_file():
            return load_artifacts(FIXTURE_DIR), (FIXTURE_DIR / "submission.json").stat().st_mtime
        submission = read_json(self.sample_dir / "submission.json")
        if not submission:
            return None
        components = read_json(self.sample_dir / "component_map.json") or {}
        vision = read_json(self.sample_dir / "vision.json")
        try:
            markdown = (self.sample_dir / "profile.md").read_text(encoding="utf-8")
        except OSError:
            markdown = ""
        parts = [{"key": c["id"], "name": c["name"]} for c in components.get("components", [])]
        codes = list(dict.fromkeys(r["source"]["regulation"] for r in submission["requirements"]))
        selected = []
        for code in codes:
            level, confidence, reason = REGULATIONS.get(code, (None, "medium", "Selected for this product."))
            covers = [c["id"] for c in components.get("components", []) if code in c.get("regulations", {})]
            selected.append({"regulation": code, "level": level, "confidence": confidence, "covers": covers, "reason": reason})
        profile = {"product": _profile_line(markdown, "Product") or "Rear lamp", "summary": _profile_line(markdown, "Summary"),
                   "vehicle_categories": [c.strip() for c in _profile_line(markdown, "Vehicle categories").split(",") if c.strip()],
                   "functions": [], "parts": parts, "technologies": []}
        artifacts = {"profile": profile, "regulations": {"selected": selected}, "hop": None, "submission": submission, "trace": None,
                     "components": components or None, "vision": vision}
        return artifacts, (self.sample_dir / "submission.json").stat().st_mtime

    def analysis(self) -> dict[str, Any] | None:
        """The finished Analysis (src/backend/models.py), or None when the recorded run is not in the repository."""
        with self._lock:
            if self._analysis is None:
                found = self._artifacts()
                if found is None:
                    return None
                artifacts, mtime = found
                drawing_url = f"/api/analyses/{EXAMPLE_ID}/drawing" if self.drawing_path() else None
                result = build_result(artifacts, drawing_url, self.breadcrumbs)
                for component in result["components"]:
                    if component["name"] in MARKERS:
                        component["marker"] = dict(zip(("x", "y"), MARKERS[component["name"]]))
                details = {
                    "vision": f"{len((artifacts.get('vision') or {}).get('components', []))} components found on the drawing",
                    "profile": f"{len(artifacts['profile'].get('parts', []))} parts",
                    "regulations": ", ".join(r["code"] for r in result["regulations"]),
                    "sections": None,
                    "obligations": f"{sum(len(r['requirements']) for r in result['regulations'])} requirements",
                    "components": f"{len(result['components'])} components",
                }
                stages = [{"id": s, "status": "done", **({"detail": d} if (d := details[s]) else {})}
                          for s in ("vision", "profile", "regulations", "sections", "obligations", "components")]
                self._analysis = {"id": EXAMPLE_ID, "status": "done", "createdAt": datetime.fromtimestamp(mtime, timezone.utc).isoformat(timespec="seconds"),
                                  "stages": stages, "result": result}
            return self._analysis
