"""v1.3 Phase 8 (PIDKG_UPGRADE.md): topology gold set and eval.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The numbers pinned here are the baseline of the frozen Phase 3 extraction against the gold set.
They were worked out by hand from the drawings before the scorer was written. No pass threshold
is set by the plan; these tests guard the scorer, not the extraction.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval import make_topology_gold as MG  # noqa: E402
from eval import topology_eval as TE  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
GOLD = ROOT / "eval" / "gold_topology_U-100.json"
GOLD_PIDKG = ROOT / "eval" / "gold_pidkg_U-100.json"


@pytest.fixture(scope="module")
def graph() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gold() -> dict:
    return json.loads(GOLD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def scores(graph, gold) -> dict:
    return TE.score(graph, gold)


# ---- the gold set ---------------------------------------------------------------------
def test_gold_files_are_what_the_generator_builds(gold):
    built, pidkg = MG.build(json.loads(MG.SOURCE.read_text(encoding="utf-8")))
    assert built == gold and pidkg == json.loads(GOLD_PIDKG.read_text(encoding="utf-8"))


def test_gold_covers_what_phase_8_asks_for(gold):
    assert {k: len(v) for k, v in gold["tags"].items()} == {"PID-100-001": 17, "PID-100-002": 4, "PID-100-003": 0}
    assert "TT-1003" not in json.dumps(gold) and "PT-1001D" not in json.dumps(gold)          # not drawn, so not gold
    placed = {p["tag"]: p for p in gold["placements"]}
    assert len(placed) == 11                                                                # every bubble that senses something
    assert placed["PT-1001A"] == {"tag": "PT-1001A", "sheet": "PID-100-001", "on": "line", "line": "L-101", "after": "XV-1001",
                                  "before": "FT-1004", "in_line": False}
    assert placed["FT-1004"]["in_line"] and placed["FT-1004"]["before"] == "V-1002"
    assert placed["LT-1006"] == {"tag": "LT-1006", "sheet": "PID-100-001", "on": "equipment", "equipment": "V-1002"}
    assert placed["PT-1005"]["after"] == "off-page" and placed["PT-1005"]["before"] == "gate_valve"
    assert not ({"LIC-1006", "FIC-1004", "PIC-1005"} & set(placed))                           # controllers sense nothing
    assert len(gold["flow_pairs"]) == 7
    assert {"from": "V-1002", "to": "BL-200", "via_lines": ["L-102"]} in gold["flow_pairs"]      # joined across the off-page connector
    assert gold["loops"] == {"F-1004": ["FIC-1004", "FT-1004"], "L-1002": ["LT-1002A", "LT-1002B", "XV-1001", "XV-1002"],
                             "L-1006": ["LIC-1006", "LT-1006", "LV-1006"], "P-1001": ["BDV-1001", "PT-1001A", "PT-1001B", "PT-1001C", "XV-1001"],
                             "P-1005": ["PIC-1005", "PT-1005", "PV-1005"]}


# ---- baseline scores of the frozen extraction ---------------------------------------------
def test_tags(scores):
    t = scores["tags"]
    assert (t["gold"], t["predicted"], t["tp"]) == (21, 23, 21) and t["recall"] == 1.0 and t["precision"] == 0.913
    assert t["spurious"] == ["PID-100-001 I-1", "PID-100-001 I-2"] and t["missed"] == []     # the interlock diamonds read as tags
    assert scores["tags_by_sheet"]["PID-100-002"]["precision"] == 1.0 and scores["tags_by_sheet"]["PID-100-003"]["gold"] == 0


def test_flow(scores):
    f = scores["flow"]
    assert (f["gold"], f["predicted"], f["tp"]) == (7, 7, 7) and f["precision"] == 1.0 and f["recall"] == 1.0
    assert scores["flow_lines"] == {"pairs_with_lines": 5, "lines_correct": 5}


def test_instrument_placement(scores):
    p = scores["placement"]
    assert (p["total"], p["correct"], p["accuracy"]) == (11, 11, 1.0) and p["errors"] == []
    assert (p["line_correct"], p["line_accuracy"]) == (11, 1.0)


def test_loops(scores):
    lp = scores["loops"]
    assert (lp["loops"]["gold"], lp["loops"]["predicted"], lp["loops"]["tp"]) == (5, 7, 5) and lp["loops"]["recall"] == 1.0
    assert lp["loops"]["spurious"] == ["I-1", "I-2"] and lp["loops"]["precision"] == 0.714
    m = lp["members"]
    assert (m["gold"], m["predicted"], m["tp"]) == (17, 25, 17) and m["recall"] == 1.0 and m["precision"] == 0.68
    assert {"L-1002 LG-1002", "P-1001 PI-1001"} <= set(m["spurious"])                         # gauges pulled in by tag number


# ---- the scorer notices when the extraction is wrong ------------------------------------------
def test_a_missed_tag_a_misplaced_tap_and_a_wrong_flow_lower_the_scores(graph, gold):
    g = copy.deepcopy(graph)
    g["nodes"] = [n for n in g["nodes"] if n["id"] != "PI-1001"]
    g["edges"] = [e for e in g["edges"] if "PI-1001" not in (e["source"], e["target"])]
    next(e for e in g["edges"] if e["type"] == "MEASURES" and e["source"] == "PT-1001A")["target"] = "P02.L1.2"   # before XV-1001
    feeds = next(e for e in g["edges"] if e["type"] == "FEEDS" and e["target"] == "BOUNDARY:LIQUID TO BL-103")
    feeds["target"] = "BOUNDARY:FEED GAS TO BL-200"
    s = TE.score(g, gold)
    assert s["tags"]["missed"] == ["PID-100-001 PI-1001"] and s["tags"]["recall"] == round(20 / 21, 3)
    assert s["placement"]["correct"] == 9 and {e["tag"] for e in s["placement"]["errors"]} == {"PI-1001", "PT-1001A"}
    err = next(e for e in s["placement"]["errors"] if e["tag"] == "PT-1001A")
    assert err["expected"]["after"] == "XV-1001" and err["got"]["after"] == "HV-1001" and err["got"]["before"] == "XV-1001"
    assert s["placement"]["line_correct"] == 10                                              # PT-1001A is still on L-101
    assert s["flow"]["missed"] == ["V-1002 BL-103"] and s["flow"]["tp"] == 6


# ---- review workload ------------------------------------------------------------------------------
def test_review_workload_from_the_loader_result(graph):
    w = TE.workload(graph)
    assert w["facts"] == 120 and w["flagged"] == 20 and w["flag_share"] == 0.167
    assert w["by_flag"] == {"inline_item": 18, "off_page": 2}                                # nothing loaded is below 0.85 confidence
    assert w["pending_by_sheet"] == {"PID-100-001": 85, "PID-100-002": 35} and w["pending"] == 120
    assert w["loaded"]["nodes"] == 32 and w["exceptions_by_code"]["X21"] == 4


def test_cli_prints_and_writes_a_report(tmp_path, capsys):
    assert TE.main(["--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "tags" in out and "placement" in out and "flagged for priority review" in out
    rep = json.loads((tmp_path / "topology_eval_U-100.json").read_text(encoding="utf-8"))
    assert rep["scores"]["flow"]["f1"] == 1.0 and rep["workload"]["facts"] == 120 and rep["thresholds"] is None


# ---- pid-to-kg's own scorer, for comparison -----------------------------------------------------------
def test_pidkg_own_eval_agrees_on_the_same_gold():
    script = ROOT / "third_party" / "pid-to-kg" / "skills" / "pid-to-kg" / "scripts" / "eval_kg.py"
    py = ROOT / ".venv-pidkg" / "Scripts" / "python.exe"
    if not script.is_file() or not py.is_file() or shutil.which("git") is None:
        pytest.skip("pid-to-kg is not set up on this machine (THIRD_PARTY_NOTICES.md)")
    res = TE.run_pidkg_eval(FIXTURE, GOLD_PIDKG)
    assert res["tags"]["recall"] == 1.0 and res["tags"]["false_positives"] == ["I-1", "I-2"]
    assert res["flow"]["precision"] == 1.0 and res["flow"]["recall"] == 1.0
    assert res["instrument_placement"]["correct"] == res["instrument_placement"]["total"] == 11
    assert res["loops"]["recall"] == 1.0 and res["loops"]["mean_member_jaccard"] < 1.0
    clone = script.parents[3]
    assert subprocess.run(["git", "-C", str(clone), "status", "--porcelain"], capture_output=True, text=True).stdout.strip() == ""


def test_baseline_document_records_both_scorers():
    text = (ROOT / "eval" / "TOPOLOGY_BASELINE.md").read_text(encoding="utf-8")
    for needle in ("0.913", "0.714", "0.68", "11 / 11", "20 of 120", "eval_kg.py", "No pass threshold"):
        assert needle in text, needle
