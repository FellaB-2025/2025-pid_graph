"""v1.3 Phase 9 (PIDKG_UPGRADE.md): the no-master, report-only mode for drawings with no registers.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Real public drawings are extracted for a stress test only. There is no instrument index for
those plants, so nothing can be reconciled or applied: the loader only counts. The drawings,
renders and extracted graphs are never committed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"


@pytest.fixture(scope="module")
def graph() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_report_counts_what_the_extraction_holds(graph):
    r = LP.report_only(graph)
    assert r["applied"] is False and r["generator"] == graph["generator"]
    assert r["nodes"] == len(graph["nodes"]) and r["nodes_by_type"] == dict(sorted(Counter(n["type"] for n in graph["nodes"]).items()))
    assert r["relationships"] == len(graph["edges"]) and r["relationships_by_type"] == dict(sorted(Counter(e["type"] for e in graph["edges"]).items()))
    assert [(s["drawing_number"], s["revision"], s["page"]) for s in r["sheets"]] == [("PID-100-001", "D", 2), ("PID-100-002", "B", 3), ("PID-100-003", "A", 4)]
    comps = [n for n in graph["nodes"] if n["type"] == "Component"]
    assert r["tagged"]["components"] == sum(1 for c in comps if c.get("tag")) and r["tagged"]["components_untagged"] == sum(1 for c in comps if not c.get("tag"))
    assert r["segments"] == {"total": 27, "on_a_numbered_line": 21}                       # the six utility segments have no line number
    assert r["off_page_connectors"] == {"total": 4, "paired": 4, "unpaired": 0} and r["unreadable"] == 0
    assert r["qa_issues"] == {"total": 1, "by_severity": {"warning": 1}, "by_code": {"loop_no_final_element": 1}}


def test_t5_flag_rate_without_a_master(graph):
    t5 = LP.report_only(graph)["t5"]
    assert t5["flagged"] <= t5["facts"] and t5["flag_rate"] == round(t5["flagged"] / t5["facts"], 3)
    assert t5["by_flag"]["off_page"] == 2 and t5["by_flag"]["inline_item"] > 0
    # more is flagged than after the gate (20 of 120): with no index nothing is filtered out first
    assert t5["facts"] > 120 and t5["flagged"] > 20
    g = json.loads(json.dumps(graph))
    for e in g["edges"]:
        if e["type"] == "FLOWS_TO":
            e["attributes"]["flow_direction"] = "inferred"
            e["confidence"] = 0.7
    worse = LP.report_only(g)["t5"]
    assert worse["flag_rate"] > t5["flag_rate"] and worse["by_flag"]["inferred_direction"] > 0 and worse["by_flag"]["low_confidence"] > 1


def test_cli_reports_and_applies_nothing(tmp_path, capsys, monkeypatch):
    import pid_graph.pipeline as pipeline
    monkeypatch.setattr(pipeline, "build_store", lambda **kw: (_ for _ in ()).throw(AssertionError("no registers may be read")))
    out = tmp_path / "report.json"
    assert LP.main(["--graph", str(FIXTURE), "--no-master", "--report-only", "--report-json", str(out), "--out", str(tmp_path / "never")]) == 0
    text = capsys.readouterr().out
    assert "REPORT ONLY" in text and "nothing applied" in text and "T5:" in text
    assert json.loads(out.read_text(encoding="utf-8"))["nodes"] == 84 and not (tmp_path / "never").exists()


@pytest.mark.parametrize("args", [["--no-master"], ["--report-only"], ["--no-master", "--report-only", "--apply"]])
def test_the_two_flags_go_together_and_never_with_apply(args):
    with pytest.raises(SystemExit):
        LP.main(["--graph", str(FIXTURE), *args])


@pytest.mark.parametrize("path", ["data/external/pahala.pdf", "data/external/gold/pahala_p12.json", "work/pahala/kg/graph.json",
                                  "work/virden/pages/page_05/overview.png", "reports/review_markup_pahala.pdf"])
def test_stress_test_material_can_never_be_committed(path):
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    run = subprocess.run(["git", "check-ignore", path], cwd=ROOT, capture_output=True, text=True)
    assert run.stdout.strip() == path
    assert subprocess.run(["git", "ls-files", "data/external", "work"], cwd=ROOT, capture_output=True, text=True).stdout.strip() == ""


# ---- what the stress test is allowed to leave in the repository ---------------------------------
def test_committed_scores_are_numbers_only_and_say_they_are_unverified():
    scores = json.loads((ROOT / "eval" / "stress_test_scores.json").read_text(encoding="utf-8"))
    assert scores["gold_verified_by_engineer"] is False and "NOT yet checked by an engineer" in scores["note"]
    assert set(scores["sets"]) == {"pahala", "virden"}

    def leaves(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from leaves(v)
        elif isinstance(x, list):
            for v in x:
                yield from leaves(v)
        else:
            yield x
    for name, s in scores["sets"].items():
        for part in ("report_only", "scores"):
            assert all(isinstance(v, (int, float)) or v is None for v in leaves(s[part])), f"{name}.{part} holds text from a drawing"
        assert s["report_only"]["t5"]["flag_rate"] == round(s["report_only"]["t5"]["flagged"] / s["report_only"]["t5"]["facts"], 3)
    doc = (ROOT / "docs" / "STRESS_TEST.md").read_text(encoding="utf-8")
    for needle in ("pilot", "not checked by an engineer", "No OCR", "agreement between two", "0.388", "0.248", "81 of 81"):
        assert needle in doc, needle


def test_no_drawing_material_is_tracked():
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.lower()
    assert "pahala" not in tracked and "virden" not in tracked and "data/external" not in tracked
