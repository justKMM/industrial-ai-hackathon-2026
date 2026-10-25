"""The backend around the real pipeline: `ai_agent.pipeline.run_case` runs for real (the graph, the tools, the grounding check, the emission
policy, the component map, the files it writes); only the model is a script. The run folder it leaves is then read by the adapter, which is
the check that the adapter matches what the pipeline really writes and not what the documentation says it writes."""

from __future__ import annotations

import json
import re
import shutil
import time

import pytest
from ai_agent import store
from ai_agent.config import Settings
from ai_agent.llm import LLM, Reply
from ai_agent.pipeline import run_case
from fastapi.testclient import TestClient
from PIL import Image
from regcomp import corpus

from backend import settings
from backend.main import create_app
from backend.models import Analysis
from conftest import make_config

PROFILE = {"product": "test lamp", "summary": "A lamp for the test.", "vehicle_categories": ["M1"], "functions": [{"key": "F1", "name": "Retro-reflection", "detail": ""}],
           "parts": [{"key": "P1", "name": "Reflector", "role": "r", "materials": ["PMMA"]}], "technologies": [{"key": "T1", "name": "t", "regulatory_concepts": ["c"]}],
           "attributes": [{"name": "colour", "value": "red", "source": "inferred"}], "regulatory_concepts": ["rc"], "not_present": ["np"]}


class Scripted(LLM):
    """The real LLM class with `call` replaced by a script: complete_json, the tool loop and everything above them run for real."""

    def __init__(self, script, config):
        super().__init__(Settings(api_key="sk-test", cache_dir=None, workers=2, fallbacks=False, max_cost_usd=config.max_cost_usd), client=object())
        self.script = script

    def call(self, *, stage, label, system, messages, tools=None, schema=None, effort=None, max_tokens=16_000, auto_cache=False):
        content, stop = self.script(stage, label, system, messages, tools, schema)
        reply = Reply(content, stop, "scripted", {"input_tokens": 100, "output_tokens": 50, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
        self.ledger.add(stage, reply.usage, 0.0, cached=False)
        return reply


def text(payload):
    return [{"type": "text", "text": json.dumps(payload)}]


def tool(uid, name, args):
    return {"type": "tool_use", "id": uid, "name": name, "input": args}


def make_script(section):
    def script(stage, label, system, messages, tools_, schema):
        if stage == "profile":
            return text(PROFILE), "end_turn"
        if stage == "regulations" and label == "select":  # R3 is superseded by R150: the pipeline merges the two
            pick = lambda reg: {"regulation": reg, "level": "device", "confidence": "high", "covers": ["P1", "T1", "Z9"], "reason": f"{reg} is about the reflector."}
            return text({"selected": [pick("UN R3"), pick("UN R150")], "close_calls": []}), "end_turn"
        if stage == "regulations":
            return text({"add": [], "skip": []}), "end_turn"
        if stage == "sections":
            if len(messages) == 1:
                return [tool("t1", "get_toc", {"node": section, "depth": 1})], "tool_use"
            return [tool("t2", "select_sections", {"selections": [{"node": section, "category": "function", "reason": "r"}]})], "tool_use"
        if stage == "obligations":
            body = messages[0]["content"][1]["text"]
            found = re.findall(r'<node id="([^"]+)"[^>]*>\n(.*?)\n</node>', body, re.S)
            repair = "left out of your answer" in body
            entries = []
            for k, (nid, node_text) in enumerate(found):
                if k % 7 == 6 and not repair:
                    continue
                items = []
                if len(node_text.split()) > 8:
                    items = [{"quote": " ".join(node_text.split()[1:7]), "text": f"The device shall satisfy {nid}.", "modality": "obligation", "addressee": "product",
                              "kind": ("design", "marking", "performance")[k % 3], "applies": ("certain", "likely", "possible", "unlikely")[k % 4], "why": "w"}]
                entries.append({"node": nid, "obligations": items})
            return text({"nodes": entries}), "end_turn"
        if stage == "components":
            if label == "group":
                return text({"components": [{"id": "K1", "name": "Reflector", "keys": ["P1"]}]}), "end_turn"
            ids_ = re.findall(r"^(R-\d+) \|", messages[0]["content"], re.M)
            return text({"assignments": [{"requirement": rid, "components": ["K1"] if k % 2 == 0 else []} for k, rid in enumerate(ids_)]}), "end_turn"
        raise AssertionError(stage)

    return script


@pytest.fixture
def reflector_data(tmp_path):
    real = settings.resolve_data_dir()
    if not (real / "UN_R150" / "base").is_dir():
        pytest.skip("the regulation PDFs are not on this machine")
    target = tmp_path / "data"
    for reg in ("UN R3", "UN R150"):
        name = corpus.entry_for(reg)["versions"][0]["files"][0]["name"]
        (target / corpus.slug(reg) / "base").mkdir(parents=True)
        shutil.copy(real / corpus.slug(reg) / "base" / name, target / corpus.slug(reg) / "base" / name)
    return target


def png_bytes() -> bytes:
    import io

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_a_search_runs_the_real_pipeline_and_the_adapter_reads_what_it_wrote(tmp_path, reflector_data, monkeypatch):
    monkeypatch.setenv("AI_AGENT_KEY", "sk-test")
    config = make_config(tmp_path, reflector_data, web_max_cost_usd=2.0)
    seen = {}

    def pipeline(*, case_dir, settings, run_dir, log, catalog):
        seen["max_cost"] = settings.max_cost_usd
        real = store.RegGraph("UN R150", grids=False)
        section = max(((n.label, real.sub_content[i]) for i, n in enumerate(real.nodes) if n.kind == "para" and not n.scope and len(n.num) == 2 and n.num[0] >= 3),
                      key=lambda item: item[1])[0]
        seen["section"] = section
        # the drawing is not read (no vision model here): the case folder is used as the text-only case it is for the pipeline
        return run_case(case_dir, Settings(api_key="sk-test", cache_dir=None, workers=2, fallbacks=False), run_dir, log=log, llm=Scripted(make_script(section), settings),
                        catalog=catalog, use_image=False, component_map=True)

    with TestClient(create_app(config, pipeline=pipeline)) as client:
        answer = client.post("/api/analyses", files=[("files", ("spec.md", b"# spec: test lamp\n\nA lamp.", "text/markdown"))])
        assert answer.status_code == 202
        analysis_id = answer.json()["id"]
        deadline = time.time() + 120
        while True:
            body = client.get(f"/api/analyses/{analysis_id}").json()
            if body["status"] in ("done", "failed") or time.time() > deadline:
                break
            time.sleep(0.2)
        assert body["status"] == "done", body.get("error")
        Analysis.model_validate(body)

        assert seen["max_cost"] == 2.0
        result = body["result"]
        assert result["product"]["name"] == "test lamp" and result["product"]["vehicleCategories"] == ["M1"]
        (regulation,) = result["regulations"]
        assert regulation["code"] == "UN R150" and regulation["version"] == "1.2.1" and regulation["level"] == "device"
        assert regulation["covers"] == ["Reflector", "t"]  # profile keys resolved to names; the unknown key Z9 is dropped
        requirements = regulation["requirements"]
        assert requirements and all(r["source"]["version"] == "1.2.1" and r["source"]["regulation"] == "UN R150" for r in requirements)
        assert {r["applies"] for r in requirements} <= {"certain", "likely", "possible"}  # `unlikely` was dropped by the emission policy
        assert {r["kind"] for r in requirements} <= {"design", "marking", "performance"}

        # citations come from the parsed nodes: the page lies in the page range of the node with that label
        graph = store.RegGraph("UN R150", grids=False)
        by_label = {n.label: n for n in graph.nodes}
        for r in requirements:
            node = by_label[r["source"]["paragraph"]]
            assert node.page_start <= r["source"]["page"] <= node.page_end

        # section titles come from the breadcrumbs of the parsed document
        titled = [r for r in requirements if r.get("sectionTitle")]
        assert titled and all(len(r["sectionTitle"]) <= 90 for r in titled)

        # the component map: one component, half of the requirements are about it, the rest about the whole product
        (component,) = result["components"]
        assert component["name"] == "Reflector" and "marker" not in component  # no drawing: no dot
        known = {r["id"] for r in requirements}
        assert set(component["requirementIds"]) | set(result["wholeProductRequirementIds"]) == known
        assert not set(component["requirementIds"]) & set(result["wholeProductRequirementIds"])

        stages = {s["id"]: s["status"] for s in body["stages"]}
        assert stages == {"vision": "skipped", "profile": "done", "regulations": "done", "sections": "done", "obligations": "done", "components": "done"}
        assert body["stages"][2]["detail"] == "UN R150"  # R3 was redirected to its successor

        regulations_json = json.loads((tmp_path / "runs" / "web" / analysis_id / "run" / "regulations.json").read_text(encoding="utf-8"))
        assert regulations_json["redirects"] == {"UN R3": "UN R150"}
