"""v1.3 Phase 3 (PIDKG_UPGRADE.md): the frozen pid-to-kg extraction of the synthetic U-100 P&IDs.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The fixture is an input file. These tests pin its shape and its internal consistency; they do
not test pid-to-kg, and counts are computed from the fixture rather than hard-coded.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "pidkg_U-100"
PINNED = "7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1"
SHEETS = {"PID-100-001": "D", "PID-100-002": "B", "PID-100-003": "A"}       # as issued under TX-0057
# Node and relationship types the Phase 4 mapping table knows about (PIDKG_UPGRADE.md, Phase 4).
KNOWN_NODE_TYPES = {"Sheet", "Equipment", "Boundary", "Instrument", "Component", "PipeSegment", "OffPageConnector",
                    "ControlLoop", "Plant"}
KNOWN_REL_TYPES = {"FLOWS_TO", "MEASURES", "SIGNAL_TO", "MEMBER_OF", "FEEDS", "ACTUATES", "TRIPS", "CASCADES_TO", "PART_OF"}


@pytest.fixture(scope="module")
def graph() -> dict:
    return json.loads((FIX / "graph.json").read_text(encoding="utf-8"))


def test_fixture_files_are_present():
    for name in ("graph.json", "qa_report.md", "RUN.md", "extract/page_02.json", "extract/page_03.json", "extract/page_04.json"):
        assert (FIX / name).is_file(), name


def test_run_record_states_model_date_runtime_and_tool():
    text = (FIX / "RUN.md").read_text(encoding="utf-8")
    for needle in ("| Model |", "| Date |", "| Run time |", PINNED, "U100-PIDS-TX-0057.pdf", "OCR was not installed"):
        assert needle in text, needle


def test_graph_shape_and_generator(graph):
    assert {"schema_version", "generator", "plant", "nodes", "edges", "stats", "issues"} <= set(graph)
    assert graph["generator"].startswith("pid-to-kg ")
    assert graph["stats"]["nodes"] == len(graph["nodes"]) and graph["stats"]["edges"] == len(graph["edges"])
    assert graph["stats"]["nodes_by_type"] == dict(sorted(Counter(n["type"] for n in graph["nodes"]).items()))
    assert graph["stats"]["edges_by_type"] == dict(sorted(Counter(e["type"] for e in graph["edges"]).items()))
    ids = [n["id"] for n in graph["nodes"]]
    assert len(ids) == len(set(ids))


def test_qa_report_has_zero_errors(graph):
    assert [i for i in graph["issues"] if i["severity"] == "error"] == []
    report = (FIX / "qa_report.md").read_text(encoding="utf-8")
    assert "**0 errors" in report
    warnings = [i for i in graph["issues"] if i["severity"] == "warning"]
    assert f"{len(warnings)} warnings" in report


def test_three_sheets_with_the_issued_revisions(graph):
    sheets = {n["attributes"]["drawing_number"]: n["attributes"] for n in graph["nodes"] if n["type"] == "Sheet"}
    assert {d: a["revision"] for d, a in sheets.items()} == SHEETS
    assert all(a["unreadable"] == [] for a in sheets.values())
    assert all(len(a["tiles_reviewed"]) == 12 for a in sheets.values())


def test_every_relationship_joins_two_nodes_of_the_graph(graph):
    ids = {n["id"] for n in graph["nodes"]}
    dangling = [(e["type"], e["source"], e["target"]) for e in graph["edges"] if e["source"] not in ids or e["target"] not in ids]
    assert dangling == []


def test_only_types_the_phase4_mapping_table_covers(graph):
    assert {n["type"] for n in graph["nodes"]} <= KNOWN_NODE_TYPES
    assert {e["type"] for e in graph["edges"]} <= KNOWN_REL_TYPES


def test_graph_is_what_the_page_files_hold(graph):
    """The three page files are the source of the graph: same sheets, and every tag they hold is a node."""
    labels = {n["label"] for n in graph["nodes"]}
    for page in ("page_02", "page_03", "page_04"):
        ex = json.loads((FIX / "extract" / f"{page}.json").read_text(encoding="utf-8"))
        assert ex["sheet"]["drawing_number"] in SHEETS
        for kind in ("equipment", "components", "instruments"):
            for item in ex.get(kind, []):
                if item.get("tag"):
                    assert item["tag"] in labels, f"{page}: {item['tag']} is not in the graph"


def test_fixture_exercises_every_branch_the_loader_needs(graph):
    by_type = Counter(n["type"] for n in graph["nodes"])
    comps = [n for n in graph["nodes"] if n["type"] == "Component"]
    tagged = [c for c in comps if c.get("tag")]
    assert tagged and len(tagged) < len(comps)                           # tagged valves and untagged fittings
    assert by_type["PipeSegment"] and by_type["ControlLoop"] and by_type["Boundary"] and by_type["Instrument"]
    assert by_type["OffPageConnector"] >= 2 and by_type["OffPageConnector"] % 2 == 0     # paired connectors
    purposes = {e["attributes"].get("purpose") for e in graph["edges"] if e["type"] == "SIGNAL_TO"}
    assert {"control", "measurement", "trip"} <= purposes
    assert any(e["type"] == "MEASURES" for e in graph["edges"])
    seg_lines = {n["attributes"].get("line_number") for n in graph["nodes"] if n["type"] == "PipeSegment"}
    assert any(seg_lines - {None, ""}) and (None in seg_lines or "" in seg_lines)         # numbered and unnumbered lines


def test_planted_discrepancies_reach_the_fixture(graph):
    labels = {n["label"] for n in graph["nodes"]}
    assert "TT-1003" not in labels and "PT-1001D" not in labels          # not drawn, so not extracted
    assert "FT-1006" in labels and "XV-1002" in labels
    by_label = {n["label"]: n for n in graph["nodes"]}
    sheet_no = {n["id"]: n["attributes"]["drawing_number"] for n in graph["nodes"] if n["type"] == "Sheet"}
    assert [sheet_no[s] for s in by_label["XV-1002"]["sheets"]] == ["PID-100-001"]        # index says PID-100-002
    assert [sheet_no[s] for s in by_label["FT-1006"]["sheets"]] == ["PID-100-002"]
