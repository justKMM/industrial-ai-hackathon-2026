import io
import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import settings
from backend.jobs import JobStore
from backend.main import create_app
from backend.models import Analysis, BackendStatus
from conftest import make_config

KEY = "sk-ant-test-secret-123"


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG")
    return buffer.getvalue()


class FakePipeline:
    """Stands for ai_agent.pipeline.run_case: writes the files of a run one stage at a time and waits at a gate in the middle."""

    def __init__(self):
        self.gate, self.reached, self.calls, self.fail = threading.Event(), threading.Event(), [], None
        self.gate.set()

    def hold(self):
        self.gate.clear()
        self.reached.clear()

    def __call__(self, *, case_dir, settings, run_dir, log, catalog):
        self.calls.append({"case": sorted(p.name for p in case_dir.iterdir()), "max_cost": settings.max_cost_usd, "regulations": len(catalog.cards)})
        run_dir.mkdir(parents=True, exist_ok=True)
        write = lambda name, data: (run_dir / name).write_text(json.dumps(data), encoding="utf-8")  # noqa: E731
        log("[run] started")
        if self.fail:
            raise self.fail
        if any(p.name.startswith("drawing.") for p in case_dir.iterdir()):
            write("vision.json", {"components": [{"key": "C1", "region": {"x0": 0.1, "y0": 0.1, "x1": 0.3, "y1": 0.5}}]})
        write("profile.json", {"product": "Test lamp", "summary": "A lamp.", "vehicle_categories": ["M1"], "functions": [{"key": "F1", "name": "Signalling", "detail": ""}],
                               "parts": [{"key": "P1", "name": "Lens", "role": "", "materials": []}], "technologies": []})
        self.reached.set()
        assert self.gate.wait(30), "the test never released the pipeline"
        write("regulations.json", {"selected": [{"regulation": "UN R42", "level": "device", "confidence": "high", "covers": ["P1"], "reason": "Bumpers."}], "rejected": [], "redirects": {}, "dropped": []})
        write("sections.json", {"UN R42": {"provisions": 12}})
        write("submission.json", {"requirements": [{"id": "R-001", "text": "The bumper shall hold.", "source": {"regulation": "UN R42", "version": "9.9", "page": 3, "paragraph": "5.1"}}]})
        write("trace.json", [{"id": "R-001", "applies": "certain", "kind": "design"}])
        write("component_map.json", {"components": [{"id": "K1", "name": "Lens", "keys": ["P1", "C1"], "requirement_ids": ["R-001"]}], "whole_product_requirement_ids": []})
        return SimpleNamespace(problems=[], failures=[], ledger={"spent_usd": 0.12})


@pytest.fixture
def pipeline():
    return FakePipeline()


@pytest.fixture
def client(tmp_path, small_data, monkeypatch, pipeline):
    monkeypatch.setenv("AI_AGENT_KEY", KEY)
    app = create_app(make_config(tmp_path, small_data, web_max_cost_usd=3.5), pipeline=pipeline)
    with TestClient(app) as test_client:
        test_client.app_state = app.state.services
        yield test_client


def upload(client, *files):
    return client.post("/api/analyses", files=[("files", f) for f in files])


SPEC = ("spec.md", b"# spec: Test lamp\n\nA lamp.", "text/markdown")
DRAWING = ("view.png", png(), "image/png")


def wait_for(client, analysis_id, done, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/analyses/{analysis_id}").json()
        if done(body):
            return body
        time.sleep(0.05)
    raise AssertionError(f"timed out: {body}")


def ids(body):
    return {s["id"]: s["status"] for s in body["stages"]}


def test_status_tells_whether_there_is_a_key_and_never_what_it_is(client, monkeypatch):
    body = client.get("/api/status").json()
    BackendStatus.model_validate(body)
    assert body["apiKey"] is True and KEY not in json.dumps(body)
    monkeypatch.delenv("AI_AGENT_KEY")
    assert client.get("/api/status").json()["apiKey"] is False


def test_a_key_added_to_env_while_the_backend_runs_is_found_without_a_restart(client, monkeypatch):
    monkeypatch.setenv("AI_AGENT_KEY", "")  # what an empty `AI_AGENT_KEY=` line leaves in the environment
    monkeypatch.setattr(settings, "load_env", lambda *a, **k: __import__("os").environ.setdefault("AI_AGENT_KEY", "sk-pasted-later"))
    assert client.get("/api/status").json()["apiKey"] is True


def test_without_a_key_a_search_is_refused_but_the_example_still_opens(client, monkeypatch):
    monkeypatch.delenv("AI_AGENT_KEY")
    answer = upload(client, SPEC)
    assert answer.status_code == 503 and "AI_AGENT_KEY" in answer.json()["detail"]
    assert client.get("/api/analyses/example").status_code == 200


def test_an_upload_is_accepted_at_once_and_followed_through_its_stages_to_the_result(client, pipeline):
    pipeline.hold()
    answer = upload(client, SPEC, DRAWING)
    assert answer.status_code == 202
    analysis_id = answer.json()["id"]
    assert answer.headers["location"] == f"/api/analyses/{analysis_id}"

    assert pipeline.reached.wait(30)
    running = client.get(f"/api/analyses/{analysis_id}").json()
    Analysis.model_validate(running)
    assert running["status"] == "running" and "result" not in running
    assert ids(running) == {"vision": "done", "profile": "done", "regulations": "running", "sections": "pending", "obligations": "pending", "components": "pending"}
    assert running["stages"][0]["detail"] == "1 components found on the drawing" and running["stages"][1]["detail"] == "1 parts, 1 functions"

    pipeline.gate.set()
    done = wait_for(client, analysis_id, lambda b: b["status"] == "done")
    Analysis.model_validate(done)
    assert all(s == "done" for s in ids(done).values())
    result = done["result"]
    assert result["product"] == {"name": "Test lamp", "summary": "A lamp.", "vehicleCategories": ["M1"]}
    regulation = result["regulations"][0]
    assert (regulation["code"], regulation["level"], regulation["covers"], regulation["version"]) == ("UN R42", "device", ["Lens"], regulation["version"])
    assert regulation["requirements"][0]["applies"] == "certain"
    assert result["components"] == [{"id": "K1", "name": "Lens", "marker": {"x": 0.2, "y": 0.3}, "requirementIds": ["R-001"]}]
    assert result["drawing"]["url"] == f"/api/analyses/{analysis_id}/drawing"

    drawing = client.get(result["drawing"]["url"])
    assert drawing.status_code == 200 and drawing.headers["content-type"] == "image/png" and drawing.content == png()

    # what the pipeline was given: the case folder, the web budget, the loaded catalog
    assert pipeline.calls[0] == {"case": ["drawing.png", "spec.md"], "max_cost": 3.5, "regulations": 2}
    folder = client.app_state.store.dir(analysis_id)
    assert (folder / "result.json").is_file() and json.loads((folder / "job.json").read_text())["status"] == "done"
    assert "[run] started" in (folder / "job.log").read_text()


def test_a_text_only_upload_skips_the_drawing_stage(client):
    analysis_id = upload(client, SPEC).json()["id"]
    done = wait_for(client, analysis_id, lambda b: b["status"] == "done")
    assert ids(done)["vision"] == "skipped" and "drawing" not in done["result"]
    assert client.get(f"/api/analyses/{analysis_id}/drawing").status_code == 404


def test_jobs_run_one_at_a_time_and_the_second_waits_in_the_queue(client, pipeline):
    pipeline.hold()
    first = upload(client, SPEC).json()["id"]
    assert pipeline.reached.wait(30)
    second = upload(client, SPEC).json()["id"]
    waiting = client.get(f"/api/analyses/{second}").json()
    assert waiting["status"] == "queued" and set(ids(waiting).values()) == {"pending", "skipped"}
    assert client.get(f"/api/analyses/{first}").json()["status"] == "running"
    pipeline.gate.set()
    assert wait_for(client, second, lambda b: b["status"] == "done")["status"] == "done"
    assert client.get(f"/api/analyses/{first}").json()["status"] == "done"
    assert len(pipeline.calls) == 2


def test_a_pipeline_that_stops_for_the_budget_fails_the_job_with_a_plain_message(client, pipeline):
    from ai_agent.llm import BudgetExceeded

    pipeline.fail = BudgetExceeded("spent $3.51 of the $3.50 budget")
    analysis_id = upload(client, SPEC).json()["id"]
    failed = wait_for(client, analysis_id, lambda b: b["status"] == "failed")
    Analysis.model_validate(failed)
    assert "spending limit" in failed["error"] and "Traceback" not in failed["error"] and "result" not in failed
    assert ids(failed)["profile"] == "failed" and ids(failed)["vision"] == "skipped" and ids(failed)["components"] == "pending"
    assert "BudgetExceeded" in (client.app_state.store.dir(analysis_id) / "job.log").read_text()  # the details stay on the server


def test_the_api_key_never_reaches_a_response_or_the_log(client, pipeline):
    pipeline.fail = RuntimeError(f"401 with key {KEY}")
    analysis_id = upload(client, SPEC).json()["id"]
    failed = wait_for(client, analysis_id, lambda b: b["status"] == "failed")
    assert KEY not in json.dumps(failed) and "went wrong" in failed["error"]
    assert KEY not in (client.app_state.store.dir(analysis_id) / "job.log").read_text()


def test_refused_uploads_say_why(client):
    assert upload(client, DRAWING, ("two.png", png(), "image/png")).status_code == 400
    assert upload(client, ("bom.docx", b"PK\x03\x04zip", "application/zip")).status_code == 415
    assert upload(client, ("a.md", b"", "text/markdown")).status_code == 400
    assert client.post("/api/analyses").status_code == 422  # no files field at all
    assert client.app_state.store._jobs == {}  # nothing was queued


def test_unknown_and_malformed_ids_are_not_found(client):
    for bad in ("nope", "0" * 32, "..%2F..%2Fetc", "example2"):
        assert client.get(f"/api/analyses/{bad}").status_code == 404, bad
        assert client.get(f"/api/analyses/{bad}/drawing").status_code == 404, bad


def test_the_example_is_a_finished_analysis_with_its_drawing(client):
    body = client.get("/api/analyses/example").json()
    Analysis.model_validate(body)
    assert body["status"] == "done" and len(body["result"]["regulations"]) == 4
    drawing = client.get(body["result"]["drawing"]["url"])
    assert drawing.status_code == 200 and drawing.headers["content-type"] == "image/png"


def test_optional_fields_are_left_out_instead_of_null(client):
    text = client.get("/api/analyses/example").text
    assert "null" not in text


def test_unfinished_jobs_of_a_dead_process_are_failed_when_the_backend_starts(tmp_path):
    store = JobStore(tmp_path / "web")
    running = store.create([{"name": "spec.md", "role": "specification", "bytes": 4}], has_drawing=False)
    running.status = "running"
    store.save(running)
    finished = store.create([], has_drawing=False)
    finished.status = "done"
    store.save(finished)

    restarted = JobStore(tmp_path / "web")
    assert restarted.load_existing() == 2
    assert restarted.get(running.id).status == "failed" and "restarted" in restarted.get(running.id).error
    assert restarted.get(finished.id).status == "done"


def test_the_index_can_be_rebuilt_on_request_but_not_twice_at_once(client, monkeypatch):
    knowledge = client.app_state.knowledge
    release = threading.Event()
    real_build = type(knowledge)._build
    monkeypatch.setattr(type(knowledge), "_build", lambda self, force: (release.wait(30), real_build(self, force))[1])
    answer = client.post("/api/index/rebuild")
    assert answer.status_code == 202 and answer.json()["state"] == "building"
    assert client.post("/api/index/rebuild").status_code == 409
    assert client.get("/api/status").json()["index"]["state"] == "building"
    release.set()
    knowledge._done.wait(60)
    assert client.get("/api/status").json()["index"]["state"] == "ready"


def test_a_search_started_before_the_first_index_exists_waits_for_it(client, pipeline):
    assert client.app_state.knowledge.status()["state"] == "missing"
    analysis_id = upload(client, SPEC).json()["id"]  # the job asks for the catalog, which builds the cards
    done = wait_for(client, analysis_id, lambda b: b["status"] == "done")
    assert done["status"] == "done" and pipeline.calls[0]["regulations"] == 2


def test_the_built_frontend_can_be_served_by_the_backend(tmp_path, small_data):
    dist = tmp_path / "root" / "src" / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>regal.ai</html>", encoding="utf-8")
    config = make_config(tmp_path, small_data, root=tmp_path / "root", serve_frontend=True)
    with TestClient(create_app(config)) as served:
        assert "regal.ai" in served.get("/").text
        assert served.get("/api/status").status_code == 200  # the API routes win over the static files
    with TestClient(create_app(make_config(tmp_path, small_data))) as plain:
        assert plain.get("/").json()["docs"] == "/docs"
