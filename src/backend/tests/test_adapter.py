import copy
import json

import pytest

from backend.adapter import build_result, load_artifacts, section_key, section_title
from backend.example import Example
from backend.fsutil import read_json
from backend.models import AnalysisResult

from conftest import ROOT, make_config

SAMPLE = ROOT / "outputs" / "dev-rear-lamp-image"


def requirement(rid, regulation="UN R48", paragraph="6.10.4.2", page=50, version="9.3.0", text="The lamp shall be red."):
    return {"id": rid, "text": text, "source": {"regulation": regulation, "version": version, "page": page, "paragraph": paragraph}}


def artifacts(**extra):
    base = {
        "profile": {"product": "Test lamp", "summary": "A lamp.", "vehicle_categories": ["M1", "unspecified"],
                    "functions": [{"key": "F1", "name": "Rear position signalling", "detail": ""}],
                    "parts": [{"key": "P1", "name": "Outer lens", "role": "", "materials": []}], "technologies": []},
        "regulations": {"selected": [{"regulation": "UN R48", "level": "vehicle", "confidence": "high", "covers": ["F1", "P1", "X9"], "reason": "Installation."}]},
        "hop": {"cited": {}, "vetted": {"add": [{"regulation": "UN R10", "reason": "Cited by R48."}], "skip": []}},
        "submission": {"requirements": [requirement("R-001"), requirement("R-002", paragraph="5.15", page=24),
                                        requirement("R-003", "UN R10", "6.1.1.2", 9, "7.2.0", "ESA shall be tested.")]},
        "trace": [{"id": "R-001", "applies": "likely", "kind": "installation"}, {"id": "R-002", "applies": "unlikely", "kind": "nonsense"}],
        "components": {"components": [{"id": "K1", "name": "Outer lens", "keys": ["P1", "C1"], "requirement_ids": ["R-001", "R-404"]},
                                      {"id": "K2", "name": "Housing", "keys": ["P2"], "requirement_ids": ["R-002"]}],
                       "whole_product_requirement_ids": ["R-003", "R-999"]},
        "vision": {"components": [{"key": "C1", "region": {"x0": 0.0, "y0": 0.2, "x1": 0.2, "y1": 0.6}}]},
    }
    base.update(extra)
    return base


def test_section_key_matches_the_frontends_grouping():
    assert section_key("6.10.4.2") == "6.10"
    assert section_key("5.2.1. Table 4") == "5.2"
    assert section_key("5") == "5"
    assert section_key("Annex 8 2.1. Table A8-1") == "Annex 8"
    assert section_key("Annex 4 Part 1 1.2") == "Annex 4"
    assert section_key("Figure 3") == "Figure 3"


def test_the_section_title_is_the_heading_of_the_section_not_of_its_parent():
    path = "6 Individual specifications › 6.10 Rear position lamp › 6.10.4 Position › 6.10.4.2"
    assert section_title(path, "6.10.4.2") == "Rear position lamp"
    assert section_title("5 General specifications › 5.15", "5.15") is None  # a section without a heading of its own
    annex = "Annex 4 Photometric and colorimetric measurements › Part 1 - Photometric measurements › 1 Test procedures › 1.2"
    assert section_title(annex, "Annex 4 Part 1 1.2") == "Photometric and colorimetric measurements"


def test_requirements_come_from_the_submission_in_regulation_order_with_their_citation():
    result = build_result(artifacts())
    assert [r["code"] for r in result["regulations"]] == ["UN R48", "UN R10"]
    first = result["regulations"][0]
    assert first["requirements"][0] == {"id": "R-001", "text": "The lamp shall be red.", "applies": "likely", "kind": "installation",
                                         "source": {"regulation": "UN R48", "version": "9.3.0", "page": 50, "paragraph": "6.10.4.2"}}
    assert first["version"] == "9.3.0" and first["title"] == "Installation of lighting and light-signalling devices"
    AnalysisResult.model_validate(result)  # the answer fits the API's models


def test_unknown_labels_are_dropped_instead_of_shown():
    second = build_result(artifacts())["regulations"][0]["requirements"][1]
    assert "applies" not in second and "kind" not in second  # `unlikely` is never shown; neither is an unknown kind


def test_a_regulation_added_by_the_citation_hop_has_no_level_and_medium_confidence():
    hop_added = build_result(artifacts())["regulations"][1]
    assert hop_added["level"] is None and hop_added["confidence"] == "medium" and hop_added["reason"] == "Cited by R48."


def test_covers_are_names_and_unknown_profile_keys_are_ignored():
    assert build_result(artifacts())["regulations"][0]["covers"] == ["Rear position signalling", "Outer lens"]


def test_components_keep_only_requirements_that_exist_and_get_a_marker_from_the_drawing_boxes():
    result = build_result(artifacts(), drawing_url="/api/analyses/x/drawing")
    lens, housing = result["components"]
    assert lens["requirementIds"] == ["R-001"] and lens["marker"] == {"x": 0.1, "y": 0.4}
    assert housing["marker"] is None  # a part of the specification only: no box on the drawing
    assert result["wholeProductRequirementIds"] == ["R-003"]
    assert result["drawing"]["url"] == "/api/analyses/x/drawing"


def test_without_a_component_map_the_result_has_no_components():
    result = build_result(artifacts(components=None, vision=None, trace=None))
    assert result["components"] == [] and result["wholeProductRequirementIds"] == [] and "drawing" not in result


def test_section_titles_come_from_the_breadcrumbs_and_a_failing_lookup_does_not_lose_the_result():
    paths = {"6.10.4.2": "6 Individual specifications › 6.10 Rear position lamp › 6.10.4 Position › 6.10.4.2"}
    titled = build_result(artifacts(), breadcrumbs=lambda reg: paths if reg == "UN R48" else {})
    assert titled["regulations"][0]["requirements"][0]["sectionTitle"] == "Rear position lamp"
    assert "sectionTitle" not in titled["regulations"][0]["requirements"][1]

    def broken(reg):
        raise RuntimeError("PDF missing")

    assert "sectionTitle" not in build_result(artifacts(), breadcrumbs=broken)["regulations"][0]["requirements"][0]


def test_a_run_without_a_submission_is_an_error():
    with pytest.raises(ValueError):
        build_result({"submission": None})


def test_the_input_is_not_changed():
    data = artifacts()
    before = copy.deepcopy(data)
    build_result(data, "/x")
    assert data == before


@pytest.mark.skipif(not (SAMPLE / "submission.json").is_file(), reason="outputs/dev-rear-lamp-image is not in this checkout")
def test_the_recorded_dev_run_has_the_shape_the_frontend_relies_on(tmp_path):
    example = Example(make_config(tmp_path, tmp_path)).analysis()
    assert example["id"] == "example" and example["status"] == "done"
    result = example["result"]
    AnalysisResult.model_validate(result)
    assert {r["code"] for r in result["regulations"]} == {"UN R10", "UN R148", "UN R150", "UN R48"}
    ids = [r["id"] for reg in result["regulations"] for r in reg["requirements"]]
    assert len(ids) == len(set(ids)) == 317
    known = set(ids)
    assert all(set(c["requirementIds"]) <= known for c in result["components"])
    assert set(result["wholeProductRequirementIds"]) <= known
    assert all(0 <= c["marker"]["x"] <= 1 and 0 <= c["marker"]["y"] <= 1 for c in result["components"] if c["marker"])
    assert sum(1 for c in result["components"] if c["marker"]) == 7  # the seven callouts of the drawing
    assert {c["name"]: (c["marker"]["x"], c["marker"]["y"]) for c in result["components"] if c["marker"]}["Housing"] == (0.345, 0.767)  # measured, not a box centre
    assert all(r["source"]["version"] == reg["version"] for reg in result["regulations"] for r in reg["requirements"])
    assert [s["id"] for s in example["stages"]] == ["vision", "profile", "regulations", "sections", "obligations", "components"]
    # the same file the frontend's mock reads: the numbers must agree with it
    sample = read_json(SAMPLE / "submission.json")
    assert len(sample["requirements"]) == 317 and json.dumps(sorted(ids)) == json.dumps(sorted(r["id"] for r in sample["requirements"]))
    assert load_artifacts(SAMPLE)["submission"] is not None


def test_failures_of_the_run_become_warnings_so_a_partial_list_is_not_taken_for_complete():
    run = {"failures": [{"stage": "sections", "regulation": "UN R10", "error": "boom"},
                        {"stage": "obligations", "regulation": "UN R48", "chunk": 3, "error": "boom"},
                        {"stage": "obligations", "regulation": "UN R48", "chunk": 4, "error": "boom"},
                        {"stage": "components", "error": "boom"}, {"stage": "odd"}]}
    sections = {"UN R148": {"finished": False, "reason": "max turns"}, "UN R48": {"finished": True}}
    result = build_result(artifacts(run=run, sections=sections))
    warnings = result["warnings"]
    assert len(warnings) == len(set(warnings)) == 5  # the two chunks of UN R48 are one sentence
    assert any(w.startswith("UN R10") for w in warnings) and any(w.startswith("UN R148") and "did not finish" in w for w in warnings)
    assert "boom" not in " ".join(warnings)  # the error text stays on the server
    AnalysisResult.model_validate(result)
    assert "warnings" not in build_result(artifacts(run={"failures": []}))
