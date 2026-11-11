"""v1.3 Phase 6 (PIDKG_UPGRADE.md): reconciliation checks between vision and the registers.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The part neither tool has alone. Six checks, each naming both sources. The discrepancy fixture
plants exactly one finding per check; the unedited extraction must stay clean apart from the two
genuine findings it already holds.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402
from pid_graph import vision_checks as VC  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.reconcile import TITLES  # noqa: E402

DATA = ROOT / "data"
FIX = ROOT / "tests" / "fixtures" / "pidkg_U-100"
CODES = ("X30", "X31", "X32", "X33", "X34", "X35", "X36")


def _store():
    return build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                       srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                       curated=DATA / "curated" / "compensating_measures_U-100.csv", topology=DATA / "pid_audit_U100_topology.csv",
                       pdf=DATA / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="TX-0057-BASELINE")[0]


def _checks(name: str):
    store = _store()
    graph = json.loads((FIX / name).read_text(encoding="utf-8"))
    index = LP.index_tags(store)
    result = LP.reconcile(graph, index, store, unit="U-100", load_run="TX-0057-BASELINE")
    return VC.run(graph, result, store, index), result, store


@pytest.fixture(scope="module")
def clean():
    return _checks("graph.json")


@pytest.fixture(scope="module")
def planted():
    return _checks("graph_discrepancies.json")


def _ids(checks, code):
    return sorted(e["id"] for e in checks["exceptions"] if e["code"] == code)


def test_discrepancy_fixture_is_what_the_script_makes():
    spec = importlib.util.spec_from_file_location("mk", ROOT / "scripts" / "make_pidkg_discrepancies.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    graph = json.loads((FIX / "graph.json").read_text(encoding="utf-8"))
    assert mk.build(graph) == json.loads((FIX / "graph_discrepancies.json").read_text(encoding="utf-8"))
    assert len(mk.EDITS) == 6 and graph == json.loads((FIX / "graph.json").read_text(encoding="utf-8"))
    text = (FIX / "DISCREPANCIES.md").read_text(encoding="utf-8")
    assert all(code in text and ident.split(" ")[0] in text for _, code, ident, _ in mk.EDITS)


def test_codes_are_named_in_the_one_table():
    assert all(c in TITLES for c in CODES)
    assert len({TITLES[c] for c in CODES}) == len(CODES)


def test_unedited_extraction_has_only_its_two_genuine_findings(clean):
    checks, _, _ = clean
    assert Counter(e["code"] for e in checks["exceptions"]) == {"X30": 1, "X34": 1}
    assert _ids(checks, "X30") == ["XV-1002"] and _ids(checks, "X34") == ["SIF-100-03: PT-1001D -> XV-1001"]
    assert checks["conflicts"] == []


def test_each_planted_discrepancy_is_found_exactly_once(planted, clean):
    checks, result, _ = planted
    assert Counter(e["code"] for e in checks["exceptions"]) == {"X30": 1, "X31": 1, "X32": 1, "X33": 1, "X34": 1, "X35": 1, "X36": 1}
    assert _ids(checks, "X31") == ["L-104"] and _ids(checks, "X32") == ["PT-1005"] and _ids(checks, "X33") == ["LT-1006 -> XV-1002"]
    assert _ids(checks, "X35") == ["LV-1006"] and _ids(checks, "X36") == ["PV-1005"]
    assert [e["id"] for e in result["exceptions"] if e["code"] == "X22"] == ["PI-1001", "TT-1003"]      # check 1, raised by the loader
    assert _ids(checks, "X30") == _ids(clean[0], "X30") and _ids(checks, "X34") == _ids(clean[0], "X34")


def test_every_finding_names_both_sources_and_both_values(planted):
    checks, _, _ = planted
    by = {e["code"]: e for e in checks["exceptions"]}
    assert all(" vs " in e["sources"] and "pidkg_vision" in e["sources"] for e in checks["exceptions"])
    assert by["X31"]["sources"] == "pidkg_vision vs pid_audit" and "FLARE-HDR" in by["X31"]["detail"] and "BL-200" in by["X31"]["detail"]
    assert by["X32"]["sources"] == "pidkg_vision vs index" and "L-102" in by["X32"]["detail"] and "L-105" in by["X32"]["detail"]
    assert by["X33"]["sources"] == "pidkg_vision vs cause_effect" and by["X34"]["sources"] == "pidkg_vision vs cause_effect"
    assert "FO" in by["X35"]["detail"] and "Fail close" in by["X35"]["detail"] and by["X35"]["sources"] == "pidkg_vision vs index"
    assert "L-1006" in by["X36"]["detail"] and "PIC-1005" in by["X36"]["detail"]
    assert "PID-100-002" in by["X30"]["detail"] and "PID-100-001" in by["X30"]["detail"]
    assert all(e["title"] == TITLES[e["code"]] and e["label"] and e["detail"] for e in checks["exceptions"])


# ---- check 1: tag regions per sheet ---------------------------------------------------
def test_tag_check_reports_three_regions_per_sheet(clean, planted):
    tc = clean[0]["tag_check"]
    assert set(tc) == {"PID-100-001", "PID-100-002", "PID-100-003"}
    s1, s2, s3 = tc["PID-100-001"], tc["PID-100-002"], tc["PID-100-003"]
    assert s1["index_only"] == ["TT-1003"] and s1["vision_only"] == ["FIC-1004", "LIC-1006", "XV-1002"]
    assert s2["index_only"] == ["XV-1002"] and s2["vision_only"] == ["FT-1006", "PIC-1005"] and s2["both"] == ["PT-1005", "PV-1005"]
    assert s3 == {"both": [], "index_only": [], "vision_only": []}
    assert {"PT-1001A", "XV-1001", "LV-1006", "HV-1001", "PI-1001"} <= set(s1["both"]) and len(s1["both"]) == 13
    for s in tc.values():                                                # the regions never overlap
        assert not (set(s["both"]) & set(s["index_only"])) and not (set(s["both"]) & set(s["vision_only"]))
    assert planted[0]["tag_check"]["PID-100-001"]["index_only"] == ["PI-1001", "TT-1003"]


# ---- check 2: derived flow ---------------------------------------------------------------
def test_derived_feeds_walk_flows_to_between_equipment(clean, planted):
    feeds = {(f["from"], f["to"]): f for f in clean[0]["derived_feeds"]}
    assert set(feeds) == {("BL-100", "V-1002"), ("V-1002", "BL-200"), ("V-1002", "BL-103"), ("V-1002", "FLARE-HDR")}
    assert feeds[("BL-100", "V-1002")]["via_lines"] == ["L-101"] and feeds[("V-1002", "BL-200")]["via_lines"] == ["L-102"]
    assert feeds[("V-1002", "BL-200")]["off_page"] is True and feeds[("BL-100", "V-1002")]["off_page"] is False
    assert all(f["derived"] is True and f["review"] == "pending" for f in feeds.values())
    assert feeds[("BL-100", "V-1002")]["via_items"] == ["HV-1001", "XV-1001", "FT-1004"]
    assert ("V-1002", "FLARE-HDR") not in {(f["from"], f["to"]) for f in planted[0]["derived_feeds"]}


def test_derived_feeds_are_not_written_to_the_graph(clean):
    _, result, store = clean
    LP.apply(store, result)
    assert len(store.rels("FEEDS")) == 9 and not any(r["props"].get("derived") for r in store.rels("FEEDS"))


def test_pid_audit_feeds_are_read_as_equipment_pairs(clean):
    _, _, store = clean
    pairs = VC.pid_audit_feeds(store)
    assert pairs == {"L-101": {("BL-100", "V-1002")}, "L-102": {("V-1002", "BL-200")}, "L-103": {("V-1002", "BL-103")},
                     "L-104": {("V-1002", "FLARE-HDR")}}


# ---- checks 3-6, on small edits ------------------------------------------------------------
def test_c_and_e_pairs_expected_on_the_drawing(clean):
    _, _, store = clean
    pairs = VC.ce_pairs(store)
    assert pairs["SIF-100-03"] == {("PT-1001D", "XV-1001")}
    assert pairs["SIF-100-01"] == {(i, f) for i in ("PT-1001A", "PT-1001B", "PT-1001C") for f in ("XV-1001", "BDV-1001")}
    assert pairs["SIF-100-02"] == {(i, f) for i in ("LT-1002A", "LT-1002B") for f in ("XV-1001", "XV-1002")}


@pytest.mark.parametrize("remark,expected", [("Fail open", "FO"), ("Fail close, partial stroke test", "FC"), ("fail closed", "FC"),
                                             ("Fails last position", "FL"), ("Upstream of XV-1001", None), ("", None), (None, None)])
def test_fail_position_from_an_index_remark(remark, expected):
    assert VC.fail_from_remark(remark) == expected


@pytest.mark.parametrize("loop,expected", [("PIC-1005", "P-1005"), ("LIC-1006", "L-1006"), ("FIC-1004", "F-1004"), ("100-TIC-2001A", "T-2001"),
                                           ("", None), (None, None), ("SPARE", None)])
def test_loop_key_from_the_index_loop_number(loop, expected):
    assert VC.loop_key(loop) == expected


def test_manual_valve_drawn_with_an_actuator_is_a_finding():
    store = _store()
    graph = json.loads((FIX / "graph.json").read_text(encoding="utf-8"))
    next(n for n in graph["nodes"] if n["id"] == "HV-1001")["attributes"]["actuator"] = "pneumatic"
    index = LP.index_tags(store)
    checks = VC.run(graph, LP.reconcile(graph, index, store, unit="U-100", load_run="t"), store, index)
    row = next(e for e in checks["exceptions"] if e["code"] == "X35")
    assert row["id"] == "HV-1001" and "Manual ball valve" in row["detail"] and "pneumatic" in row["detail"]


# ---- pipeline ---------------------------------------------------------------------------------
def test_pipeline_puts_the_findings_in_the_exception_register(tmp_path):
    from openpyxl import load_workbook
    from pid_graph.run_all import main
    args = ["--unit", "U-100", "--backend", "memory", "--pdf", str(DATA / "U100-PIDS-TX-0057.pdf"), "--transmittal", "TX-0057",
            "--load-run", "TX-0057-BASELINE", "--pidkg", str(FIX / "graph_discrepancies.json"), "--out", str(tmp_path)]
    assert main(args) == 0
    rows = list(load_workbook(tmp_path / "exception_register_U-100.xlsx")["Exceptions"].iter_rows(min_row=2, values_only=True))
    assert Counter(r[0] for r in rows if r[0] in CODES) == {c: 1 for c in CODES}
    rep = json.loads((tmp_path / "load_report_U-100.json").read_text(encoding="utf-8"))
    assert rep["vision_checks"]["exceptions_by_code"] == {c: 1 for c in CODES}
    assert rep["vision_checks"]["tag_check"]["PID-100-002"]["index_only"] == ["XV-1002"]
    assert len(rep["vision_checks"]["derived_feeds"]) == 4 and rep["reconcile"]["exceptions_by_code"]["X36"] == 1


def test_loader_off_still_gives_no_vision_findings(tmp_path):
    from pid_graph.run_all import main
    assert main(["--unit", "U-100", "--backend", "memory", "--pdf", str(DATA / "U100-PIDS-TX-0057.pdf"), "--transmittal", "TX-0057",
                 "--out", str(tmp_path)]) == 0
    rep = json.loads((tmp_path / "load_report_U-100.json").read_text(encoding="utf-8"))
    assert "vision_checks" not in rep and not any(c in rep["reconcile"]["exceptions_by_code"] for c in CODES)
