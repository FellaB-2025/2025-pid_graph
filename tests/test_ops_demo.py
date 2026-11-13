"""Operations documents in the graph, the cross-document checks (C1-C16) and the scenario demonstrator.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Everything here is relative to the documents in data/ and to the batch 1 answer key: the expected findings
are the planted items, read from the key, never a count typed into a test. The exceptions are a few named
showcase verdicts, which are the point of the demonstration.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import demo, ontology as O, ops_checks as OC  # noqa: E402
from pid_graph.demo_page import render  # noqa: E402

KEY = json.loads(demo.ANSWER_KEY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built():
    return demo.build_demo_store()


@pytest.fixture(scope="module")
def data():
    return demo.build()


def _codes(findings, code):
    return [f for f in findings if f["code"] == code]


# ---------------------------------------------------------------- the graph
def test_the_operations_documents_add_no_label_and_no_relationship(built):
    store, _ = built
    counts = store.counts()
    assert set(counts["by_label"]) <= set(O.LABELS) and set(counts["by_rel"]) <= set(O.RELS)
    assert len(O.LABELS) == 11 and len(O.RELS) == 19                      # v1.3 is untouched (D-V13-12)
    assert {n["props"]["doc_type"] for n in store.nodes("Document")} <= set(O.DOC_TYPES)
    assert not store.conflicts                                           # claims sit side by side, not on one property


def test_the_default_build_does_not_load_them():
    f = {k: v for k, v in demo.DEFAULT_FILES.items() if k not in demo.OPS_DOCS}
    store, reports = demo.build_store(unit="U-100", load_run="t", **f)
    assert not any(k in reports for k in demo.OPS_DOCS)
    assert not any(n["props"].get("doc_type") in ("MADB", "CFG", "SILV", "MOC", "REG") for n in store.nodes("Document"))
    assert not any(k.endswith(("_cfg", "_madb", "_silv")) for n in store.nodes() for k in n["props"])


def test_every_loader_reports_what_it_could_not_place(built):
    _, reports = built
    not_in_index = set(KEY["not_in_index"])
    assert set(reports["config"]["cfg_only_points"]) <= not_in_index
    assert {u["tag"] for u in reports["silv"]["unknown_tags"]} == {"LT-1002C"} and "LT-1002C" in not_in_index
    assert {t["tag"] for t in reports["moc"]["tags_not_in_graph"]} <= not_in_index
    assert reports["docreg"]["unresolved"] == [] and reports["docreg"]["unknown_types"] == []
    assert all(not reports[k].get("skipped") for k in ("madb", "config", "silv", "moc"))


def test_every_document_in_the_register_is_a_node(built):
    store, reports = built
    registered = {n["key"]["doc_no"] for n in store.nodes("Document") if n["props"].get("registered") == "yes"}
    assert registered and len(registered) == reports["docreg"]["documents"]
    covers = [r for r in store.rels("SHOWN_ON") if r["props"].get("basis") == "document register: covers"]
    assert len(covers) == reports["docreg"]["links"] and {r["end_key"]["doc_no"] for r in covers} <= registered


def test_a_moc_is_a_document_linked_to_the_tags_it_names(built):
    store, _ = built
    mocs = [n for n in store.nodes("Document") if n["props"].get("doc_type") == "MOC" and "documents_to_revise" in n["props"]]
    assert mocs and all(n["props"]["stage"] in ("proposed", "approved", "implemented", "closed", "cancelled") for n in mocs)
    for n in mocs:
        linked = [r for r in store.rels("SHOWN_ON") if r["end_key"]["doc_no"] == n["key"]["doc_no"]]
        named = len(n["props"]["tags_affected"]) - len(n["props"]["tags_not_in_graph"]) - len(n["props"].get("loops_named", []))
        assert len(linked) == named, n["key"]


# ---------------------------------------------------------------- the checks
def test_every_planted_problem_is_surfaced_by_a_check_of_its_kind(data):
    sc = data["scorecard"]
    assert sc["planted"] == len(KEY["items"])
    assert [i["id"] for i in sc["items"] if not i["found"]] == []
    assert {i["kind"] for i in KEY["items"]} <= set(OC.KIND_TO_CODES)


def test_every_check_fires_on_the_test_documents_and_names_its_sources(data):
    ops = [f for f in data["findings"] if f["code"].startswith("C")]
    # Changed on 12 Nov 2026 with Alan's agreement (the one exception to rule 12): C17-C26 came from the blind test on U-200,
    # and eight of them have nothing to fire on in U-100, so the test documents are now those of both units.
    u200 = [f for f in demo.build(unit="U-200")["findings"] if f["code"].startswith("C")]
    assert {f["code"] for f in ops + u200} == set(OC.TITLES) - {"C1"}     # C1: the register names nothing unknown
    assert {f["code"] for f in ops} >= {f"C{i}" for i in range(2, 17)}    # U-100 alone still exercises every original check
    assert all(f["title"] == OC.TITLES[f["code"]] and f["detail"] and f["sources"] for f in ops)


def test_the_checks_stay_quiet_where_the_documents_agree(data):
    ops = [f for f in data["findings"] if f["code"].startswith("C")]
    assert not [f for f in _codes(ops, "C5") if f["id"] == "PAH-1005"]
    assert not [f for f in _codes(ops, "C10") if f["id"] == "SIF-100-01"]
    assert not [f for f in _codes(ops, "C12") if "SIF-100-01" in f["tags"]]
    assert not [f for f in _codes(ops, "C8") if f["id"] != "PAH-1005"]     # only the alarm at the end of its span
    assert not [f for f in _codes(ops, "C15") if f["id"] in ("MOC-2026-012", "MOC-2026-018")]   # temporary / cancelled


def test_an_out_of_service_entry_clears_the_unrecorded_findings(built):
    store, _ = built
    base = OC.run(store, [])["findings"]
    assert _codes(base, "C13") and _codes(base, "C6")
    rows = [{"element": "MOS-1001B", "status": "active"}, {"element": "LT-1006.LAL", "status": "active"}]
    after = OC.run(store, rows)["findings"]
    assert not _codes(after, "C13") and not _codes(after, "C6")
    assert len(base) - len(after) == len(_codes(base, "C13")) + len(_codes(base, "C6"))


def test_moc_impact_follows_the_written_rules(built):
    store, _ = built
    g = OC.Graph(OC.TrustedView(store))
    imp = OC.moc_impact(g, "MOC-2026-016")                              # an instrument re-range
    assert {e["id"] for e in imp["elements"]} == {"PT-1005"} | set(g.alarms_of("PT-1005"))      # I1, I2
    assert {"U100-SRS-001", "COMPENSATING-MEASURES-U-100"} <= set(imp["missed"])                # I3
    alarm_only = OC.moc_impact(g, "MOC-2026-009")                       # names an alarm and its source
    assert [e["label"] for e in alarm_only["elements"]] == ["Alarm"]                            # I1
    assert "U100-LOPA-001" in alarm_only["missed"] and "U100-SRS-001" in alarm_only["missed"]   # I3, I4
    assert not any(g.doc_type(d) in OC.NOT_TO_REVISE for i in (imp, alarm_only) for d in i["documents"])


def test_the_design_exceptions_are_the_pipelines_own(data):
    x = [f for f in data["findings"] if f["code"].startswith("X")]
    assert x and all(re.fullmatch(r"X([1-9]|[12]\d|3[0-6])", f["code"]) for f in x)
    assert len(_codes(x, "X10")) == 1 and len(_codes(x, "X11")) == 1    # not multiplied by the configuration's relationships


# ---------------------------------------------------------------- the scenarios
def test_every_scenario_is_complete_and_points_only_at_the_graph(data):
    nodes = {n["id"] for n in data["graph"]["nodes"]}
    rels = {r["id"] for r in data["graph"]["rels"]}
    keys = {f["key"] for f in data["findings"]}
    docs = {d["doc_no"] for d in data["documents"]}
    ids = [s["id"] for s in data["scenarios"]]
    assert len(ids) == len(set(ids))
    for s in data["scenarios"]:
        assert s["steps"] and s["verdict"]["level"] in ("stop", "warn", "ok", "info") and s["verdict"]["text"], s["id"]
        assert s["kind"] in demo.KINDS and s["question"].startswith("Q")
        for st in s["steps"]:
            assert st["title"] and st["text"], s["id"]
            assert set(st["nodes"]) <= nodes and set(st["rels"]) <= rels and set(st["docs"]) <= docs, (s["id"], st["title"])
        assert set(s["findings"]) <= keys


def test_every_kind_runs_for_every_element_it_applies_to(data, built):
    store, _ = built
    by_kind = {}
    for s in data["scenarios"]:
        by_kind.setdefault(s["kind"], set()).add(s["element"])
    assert set(by_kind) == set(demo.KINDS)
    assert by_kind["sif_out"] == by_kind["trip"] == {n["key"]["sif_id"] for n in store.nodes("SIF")}
    assert by_kind["shelve"] == {n["key"]["alarm_id"] for n in store.nodes("Alarm") if not n["props"].get("stub")}
    initiators = {r["start_key"]["tag"] for r in store.rels("INITIATES")}
    assert by_kind["bypass"] == {t for t in initiators if not store.get_node("Instrument", {"tag": t})["props"].get("stub")}
    assert by_kind["moc"] == {n["key"]["doc_no"] for n in store.nodes("Document") if "documents_to_revise" in n["props"]}


def test_the_showcase_covers_every_question_and_gives_the_verdicts_shown_to_colleagues(data):
    by = {s["id"]: s for s in data["scenarios"]}
    assert len(data["showcase"]) == len(demo.SHOWCASE) and set(data["showcase"]) <= set(by)
    asked = {q for sid in data["showcase"] for q in by[sid]["question"].split("/")}
    assert asked == {f"Q{i}" for i in range(1, 9)}
    level = {sid.split(":")[0]: by[sid]["verdict"]["level"] for sid in data["showcase"]}
    assert level["bypass"] == level["shelve"] == level["sif_out"] == level["closeout"] == level["now"] == "stop"
    assert level["where_used"] == "info"
    codes = {f["code"] for f in data["findings"] if f["key"] in by["bypass:PT-1001B"]["findings"]}
    assert {"C13", "C8", "C5", "C11"} <= codes                           # the combined picture, B1-23


def test_a_compensating_alarm_on_the_bypassed_transmitter_is_called_invalid(data):
    by = {s["id"]: s for s in data["scenarios"]}
    text = lambda sid: " ".join(st["text"] for st in by[sid]["steps"])     # noqa: E731
    assert "INVALID while bypassed" in text("bypass:PT-1001A")             # PAH-1001 comes from PT-1001A itself
    assert "INVALID while bypassed" not in text("bypass:PT-1001B")


def test_the_run_is_deterministic():
    a, b = demo.build(), demo.build()
    dump = lambda d: json.dumps(d, sort_keys=True, default=str)            # noqa: E731
    assert dump(a["scenarios"]) == dump(b["scenarios"]) and dump(a["findings"]) == dump(b["findings"])


# ---------------------------------------------------------------- the page
def test_the_page_is_self_contained_in_both_forms(data):
    full, frag = render(data, standalone=True), render(data, standalone=False)
    assert full.startswith("<!doctype html>") and "<html" not in frag and "<body" not in frag
    for page in (full, frag):
        assert "<title>U-100 Scenario Explorer</title>" in page[:8000]
        assert "© 2026 Alan Bowden — Bowden Simulators. All rights reserved." in page
        assert page.count("<script") == 2 and "http://" not in page and "https://" not in page   # no external load
        assert all(sid in page for sid in data["showcase"])
        assert "color-scheme:light" in page
    payload = full.split('<script type="application/json" id="data">')[1].split("</script>")[0]
    assert json.loads(payload)["showcase"] == data["showcase"]


# ---------------------------------------------------------------- the documents say what the code does
def test_the_documents_list_the_check_codes_and_document_types():
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    onto = (ROOT / "PID_GRAPH_ONTOLOGY_V1_3.md").read_text(encoding="utf-8")
    decisions = (ROOT / "PID_GRAPH_DECISIONS.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "DEMO_GUIDE.md").read_text(encoding="utf-8")
    assert "C1–C16" in claude and "D-V13-12" in claude and "D-V13-12" in decisions and "D-V13-12" in onto
    for t in O.DOC_TYPES:
        assert f"`{t}`" in claude and f"`{t}`" in onto, t
    for code, title in OC.TITLES.items():
        assert f"| {code} | {title} |" in guide, code
    for kind, (name, _, _) in demo.KINDS.items():
        assert name in guide, kind
