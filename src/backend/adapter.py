"""A finished pipeline run to the `AnalysisResult` the frontend shows (src/frontend/src/lib/analysis/types.ts).

A pure function of the files in the run folder: no model, no network. Every regulation, version, page and paragraph in the answer is copied
from `submission.json`, which `ai_agent.emit` fills in from the parsed nodes; nothing is written or guessed here.

    artifacts = load_artifacts(run_dir)
    result = build_result(artifacts, drawing_url="/api/analyses/<id>/drawing", breadcrumbs=knowledge.breadcrumbs)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from regcomp import corpus

from backend.fsutil import read_json

SECTION_SEPARATOR = " › "  # regcomp.parse.Node.path
APPLIES = ("certain", "likely", "possible")
KINDS = ("design", "performance", "marking", "installation", "test-procedure", "conformity-of-production", "admin")
FILES = {
    "profile": "profile.json",
    "regulations": "regulations.json",
    "hop": "citation_hop.json",
    "submission": "submission.json",
    "trace": "trace.json",
    "components": "component_map.json",
    "vision": "vision.json",
    "sections": "sections.json",
    "run": "run.json",
}
Breadcrumbs = Callable[[str], dict[str, str]]


def load_artifacts(run_dir: Path) -> dict[str, Any]:
    """The JSON files of a run folder by role; a file that is not there is None."""
    return {role: read_json(Path(run_dir) / name) for role, name in FILES.items()}


def section_key(paragraph: str) -> str:
    """The part of a paragraph label that names its section: `6.10.4.2` is `6.10`, `Annex 8 2.1. Table A8-1` is `Annex 8`.
    The same rule as src/frontend/src/lib/analysis/sections.ts, so the title found here belongs to the group the frontend makes."""
    annex = re.match(r"^(Annex\s+\S+)", paragraph, re.I)
    if annex:
        return annex.group(1)
    number = re.match(r"^(\d+)(?:\.(\d+))?", paragraph)
    if not number:
        return paragraph
    return f"{number.group(1)}.{number.group(2)}" if number.group(2) else number.group(1)


def section_title(path: str, paragraph: str) -> str | None:
    """The heading of the section a paragraph sits in, from its breadcrumb: `6 Individual specifications › 6.10 Rear position lamp ›
    6.10.4 Position › 6.10.4.2` and paragraph `6.10.4.2` give "Rear position lamp". None when the section has no heading of its own."""
    key = section_key(paragraph)
    for segment in path.split(SECTION_SEPARATOR):
        if section_key(segment) == key:
            title = re.sub(r"^(?:Annex\s+\S+|[\d.]+)\s*[-–:.]?\s*", "", segment, flags=re.I).strip()
            return title[:90] or None
    return None


def _names(profile: dict) -> dict[str, str]:
    """Profile key (F1, P2, T1) to the name of the function, part or technology."""
    return {item["key"]: item["name"] for group in ("functions", "parts", "technologies") for item in profile.get(group, [])}


def _marker(vision: dict | None, keys: list[str]) -> dict[str, float] | None:
    """Where to put the dot of a component on the drawing: the centre of the box the model drew round the part (the C* key of the component)."""
    regions = {c["key"]: c.get("region") for c in (vision or {}).get("components", [])}
    for key in keys:
        box = regions.get(key)
        if key.startswith("C") and box:
            x = min(1.0, max(0.0, (box["x0"] + box["x1"]) / 2))
            y = min(1.0, max(0.0, (box["y0"] + box["y1"]) / 2))
            return {"x": round(x, 3), "y": round(y, 3)}
    return None


def warnings_of(artifacts: dict[str, Any]) -> list[str]:
    """Sentences for what went wrong without losing the run: the pipeline goes on after a failed section walk or extraction chunk and
    returns what it has, which for a regulation may be less than there is. The user must not take such a list for complete."""
    found: list[str] = []
    for failure in (artifacts.get("run") or {}).get("failures", []):
        stage, regulation = failure.get("stage"), failure.get("regulation")
        if stage == "sections" and regulation:
            found.append(f"{regulation}: the search for its relevant sections failed, so requirements may be missing.")
        elif stage == "obligations" and regulation:
            found.append(f"{regulation}: part of its text could not be turned into requirements, so some may be missing.")
        elif stage == "components":
            found.append("The requirements could not be linked to the components.")
        else:
            found.append(f"Part of the analysis failed ({stage or 'unknown stage'}), so the list may be incomplete.")
    for regulation, walk in (artifacts.get("sections") or {}).items():
        if isinstance(walk, dict) and walk.get("finished") is False:
            found.append(f"{regulation}: the search for its relevant sections did not finish, so requirements may be missing.")
    return list(dict.fromkeys(found))


def build_result(artifacts: dict[str, Any], drawing_url: str | None = None, breadcrumbs: Breadcrumbs | None = None) -> dict[str, Any]:
    submission = artifacts.get("submission")
    if not submission or "requirements" not in submission:
        raise ValueError("the run has no submission.json: nothing to show")
    profile = artifacts.get("profile") or {}
    selected = {s["regulation"]: s for s in (artifacts.get("regulations") or {}).get("selected", [])}
    hop_added = {a["regulation"]: a for a in ((artifacts.get("hop") or {}).get("vetted") or {}).get("add", [])}
    trace = {t["id"]: t for t in artifacts.get("trace") or []}
    names = _names(profile)

    by_regulation: dict[str, list[dict]] = {}
    for requirement in submission["requirements"]:
        by_regulation.setdefault(requirement["source"]["regulation"], []).append(requirement)

    regulations = []
    for code, requirements in by_regulation.items():
        try:
            entry = corpus.entry_for(code)
            title, version = entry["title"], corpus.version_label(entry, "base") or requirements[0]["source"]["version"]
        except KeyError:
            title, version = code, requirements[0]["source"]["version"]
        paths: dict[str, str] = {}
        if breadcrumbs is not None:
            try:
                paths = breadcrumbs(code)
            except Exception:  # the titles are a nicety: a PDF that cannot be read must not lose the result
                paths = {}
        info = selected.get(code)
        if info:
            level, confidence, reason = info.get("level"), info.get("confidence", "medium"), info.get("reason", "")
            covers = [names[k] for k in info.get("covers", []) if k in names]
        else:  # added by the citation hop: the pipeline treats it as medium confidence and gives no level
            level, confidence, reason, covers = None, "medium", hop_added.get(code, {}).get("reason", "Cited by a provision of another selected regulation."), []
        items = []
        for requirement in requirements:
            source = requirement["source"]
            extra = trace.get(requirement["id"], {})
            item: dict[str, Any] = {"id": requirement["id"], "text": requirement["text"],
                                    "source": {"regulation": code, "version": source["version"], "page": source["page"], "paragraph": source.get("paragraph") or ""}}
            if extra.get("applies") in APPLIES:
                item["applies"] = extra["applies"]
            if extra.get("kind") in KINDS:
                item["kind"] = extra["kind"]
            path = paths.get(source.get("paragraph") or "")
            if path and (heading := section_title(path, source["paragraph"])):
                item["sectionTitle"] = heading
            items.append(item)
        regulations.append({"code": code, "title": title, "version": version, "level": level, "confidence": confidence, "reason": reason,
                            "covers": covers, "requirements": items})

    known = {r["id"] for reg in regulations for r in reg["requirements"]}
    component_map = artifacts.get("components") or {}
    components = [{"id": c["id"], "name": c["name"], "marker": _marker(artifacts.get("vision"), c.get("keys", [])),
                   "requirementIds": [rid for rid in c.get("requirement_ids", []) if rid in known]}
                  for c in component_map.get("components", [])]
    result: dict[str, Any] = {
        "product": {"name": profile.get("product") or "Product", "summary": profile.get("summary", ""),
                    "vehicleCategories": [c for c in profile.get("vehicle_categories", []) if c.lower() != "unspecified"]},
        "regulations": regulations,
        "components": components,
        "wholeProductRequirementIds": [rid for rid in component_map.get("whole_product_requirement_ids", []) if rid in known],
    }
    if warnings := warnings_of(artifacts):
        result["warnings"] = warnings
    if drawing_url:
        result["drawing"] = {"url": drawing_url, "alt": f"Drawing of the {profile.get('product') or 'product'}"}
    return result
