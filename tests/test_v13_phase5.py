"""v1.3 Phase 5 (PIDKG_UPGRADE.md): review register, the T7 gate and the PDF markup.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

An engineer accepts. Decisions live in reports/review_register_<unit>.xlsx and survive a re-load;
safety-relevant templates see only trusted facts; pending facts are marked up on the drawing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402
from pid_graph import ontology as O  # noqa: E402
from pid_graph import queries as Q  # noqa: E402
from pid_graph import review as RV  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.records import TrustedView  # noqa: E402

DATA = ROOT / "data"
PDF = DATA / "U100-PIDS-TX-0057.pdf"
FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
COLUMNS = ["fact_id", "type", "from", "to", "sheet", "bbox", "confidence", "flags", "review", "reviewer", "reviewed_on", "comment", "detail"]
VISION_WRITABLE = {"MEASURES", "INSTALLED_ON", "SHOWN_ON", "SEGMENT_OF", "FLOWS_TO", "SIGNAL_TO", "MEMBER_OF"}
GREEN, AMBER, RED = RV.COLOURS["accepted"], RV.COLOURS["pending"], RV.COLOURS["rejected"]


def _store():
    return build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                       srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                       curated=DATA / "curated" / "compensating_measures_U-100.csv", topology=DATA / "pid_audit_U100_topology.csv",
                       pdf=PDF, transmittal="TX-0057", load_run="TX-0057-BASELINE")[0]


def _reconcile(review=None, store=None):
    store = store or _store()
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE", review=review), store


@pytest.fixture(scope="module")
def result():
    return _reconcile()[0]


def _sheet_rows(path):
    from openpyxl import load_workbook
    ws = load_workbook(path)["Review"]
    rows = list(ws.iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def _decide(path, fact_id, review, reviewer="AB", comment=""):
    """What an engineer does in Excel: fill review / reviewer / comment on one row and save."""
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb["Review"]
    head = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        if row[head.index("fact_id")].value == fact_id:
            row[head.index("review")].value = review
            row[head.index("reviewer")].value = reviewer
            row[head.index("reviewed_on")].value = "2026-11-10"
            row[head.index("comment")].value = comment
    wb.save(path)


# ---- T5 flags ---------------------------------------------------------------------
def test_priority_flags_follow_T5(result):
    rows = RV.rows(result)
    by_id = {r["fact_id"]: r for r in rows}
    facts = {x["props"]["fact_id"]: x for x in result["nodes"] + result["rels"]}
    inline = {json.dumps(n["key"]) for n in result["nodes"] if n["label"] == "InlineItem"}
    assert any(r["flags"] for r in rows) and any(not r["flags"] for r in rows)
    for fid, row in by_id.items():
        f, p = facts[fid], facts[fid]["props"]
        flags = set(filter(None, row["flags"].split("; ")))
        assert ("low_confidence" in flags) == (p["confidence"] < 0.85)
        assert ("inferred_direction" in flags) == (p.get("flow_direction") == "inferred")
        assert ("off_page" in flags) == (p.get("off_page") is True)
        touches = f.get("label") == "InlineItem" or any(json.dumps(f.get(k)) in inline for k in ("start_key", "end_key"))
        assert ("inline_item" in flags) == touches
    assert Counter(f for r in rows for f in r["flags"].split("; ") if f)["off_page"] == 2
    flagged = [bool(r["flags"]) for r in rows]
    assert flagged == sorted(flagged, reverse=True)                      # priority rows come first


def test_one_row_per_vision_node_and_relationship(result):
    rows = RV.rows(result)
    expect = [x for x in result["nodes"] + result["rels"] if x.get("type") != "SHOWN_ON"]
    assert sorted(r["fact_id"] for r in rows) == sorted(x["props"]["fact_id"] for x in expect)
    assert all(list(r) == COLUMNS for r in rows)
    assert all(r["review"] == "pending" and not r["reviewer"] for r in rows)
    seg = next(r for r in rows if r["type"] == "Segment")
    assert seg["from"].startswith("Segment L-") and seg["to"] == "" and seg["sheet"].startswith("PID-100-")
    sig = next(r for r in rows if r["type"] == "SIGNAL_TO")
    assert sig["from"].startswith("Instrument ") and "trip" in sig["detail"] and "via I-" in sig["detail"]
    item = next(r for r in rows if r["type"] == "InlineItem")
    assert re.fullmatch(r"[\d.]+,[\d.]+,[\d.]+,[\d.]+", item["bbox"]) and item["detail"]


# ---- the register file --------------------------------------------------------------
def test_register_has_the_exception_registers_format(tmp_path, result):
    from openpyxl import load_workbook
    path = RV.write_register(result, tmp_path / "review_register_U-100.xlsx", unit="U-100")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Summary", "Review"]
    assert [c.value for c in wb["Summary"][1]] == ["Metric", "Value"] and wb["Summary"]["A1"].font.bold
    assert [c.value for c in wb["Review"][1]] == COLUMNS and all(c.font.bold for c in wb["Review"][1])
    summary = {r[0]: r[1] for r in wb["Summary"].iter_rows(min_row=2, values_only=True)}
    rows = RV.rows(result)
    assert summary["unit"] == "U-100" and summary["facts"] == len(rows) and summary["pending"] == len(rows)
    assert summary["accepted"] == 0 and summary["rejected"] == 0
    assert summary["pending_priority"] == sum(1 for r in rows if r["flags"])
    assert json.loads(summary["pending_by_sheet"]) == dict(sorted(Counter(r["sheet"] for r in rows).items()))


def test_decisions_survive_a_reload_and_a_rejected_fact_leaves_the_graph(tmp_path):
    path = tmp_path / "review_register_U-100.xlsx"
    res, store = _reconcile()
    RV.write_register(res, path, unit="U-100")
    seg = next(n for n in res["nodes"] if n["label"] == "Segment" and n["key"]["segment_id"] == "L-101.2")
    trip = next(r for r in res["rels"] if r["type"] == "SIGNAL_TO" and r["start_key"]["tag"] == "PT-1001A" and r["end_key"]["tag"] == "XV-1001")
    flow = next(r for r in res["rels"] if r["type"] == "FLOWS_TO" and r["end_key"].get("tag") == "FLARE-HDR")
    _decide(path, seg["props"]["fact_id"], "accepted")
    _decide(path, trip["props"]["fact_id"], "accepted", comment="agrees with the C&E")
    _decide(path, flow["props"]["fact_id"], "rejected", comment="flag is the flare KO drum, not the header")

    register, problems = RV.read_register(path)
    assert problems == []
    decisions = RV.decisions(register)
    assert decisions == {seg["props"]["fact_id"]: "accepted", trip["props"]["fact_id"]: "accepted", flow["props"]["fact_id"]: "rejected"}

    res2, store2 = _reconcile(review=decisions)                          # the next load
    ids = {x["props"]["fact_id"]: x for x in res2["nodes"] + res2["rels"]}
    assert ids[seg["props"]["fact_id"]]["props"]["review"] == "accepted" and ids[trip["props"]["fact_id"]]["props"]["review"] == "accepted"
    assert flow["props"]["fact_id"] not in ids                           # T8: removed from the graph
    LP.apply(store2, res2)
    assert not any(r["props"].get("fact_id") == flow["props"]["fact_id"] for r in store2.rels("FLOWS_TO"))

    RV.write_register(res2, path, unit="U-100", previous=register)       # ...and the register is written back
    rows = {r["fact_id"]: r for r in _sheet_rows(path)}
    kept = rows[flow["props"]["fact_id"]]                                # T8: stays in the register with reviewer and reason
    assert kept["review"] == "rejected" and kept["reviewer"] == "AB" and "flare KO drum" in kept["comment"] and kept["to"] == "Equipment FLARE-HDR"
    assert rows[trip["props"]["fact_id"]]["comment"] == "agrees with the C&E" and rows[trip["props"]["fact_id"]]["reviewed_on"] == "2026-11-10"
    assert Counter(r["review"] for r in rows.values()) == {"pending": len(rows) - 3, "accepted": 2, "rejected": 1}
    assert len(rows) == len(RV.rows(res))                                # nothing lost, nothing duplicated
    again, _ = RV.read_register(path)
    assert RV.decisions(again) == decisions                              # stable over a second round trip


def test_a_decision_needs_a_named_reviewer_and_a_closed_value(tmp_path, result):
    path = RV.write_register(result, tmp_path / "review_register_U-100.xlsx", unit="U-100")
    rows = RV.rows(result)
    _decide(path, rows[0]["fact_id"], "accepted", reviewer="")
    _decide(path, rows[1]["fact_id"], "ok")
    register, problems = RV.read_register(path)
    assert RV.decisions(register) == {}
    assert len(problems) == 2 and any("reviewer" in p for p in problems) and any("'ok'" in p for p in problems)


def test_register_is_not_rewritten_when_nothing_changed(tmp_path, result):
    path = RV.write_register(result, tmp_path / "review_register_U-100.xlsx", unit="U-100")
    before = path.read_bytes()
    register, _ = RV.read_register(path)
    RV.write_register(result, path, unit="U-100", previous=register)
    assert path.read_bytes() == before


def test_missing_register_reads_as_empty(tmp_path):
    assert RV.read_register(tmp_path / "nope.xlsx") == ({}, [])


def test_committed_register_matches_the_fixture(result):
    """reports/review_register_U-100.xlsx is the one committed file in reports/: it must list today's facts."""
    path = ROOT / "reports" / "review_register_U-100.xlsx"
    assert path.is_file()
    register, problems = RV.read_register(path)
    assert problems == [] and set(register) >= {r["fact_id"] for r in RV.rows(result)}


# ---- T7: the gate -------------------------------------------------------------------
def test_trusted_truth_table():
    for by in ("table", "manual", "pid_audit"):
        assert O.trusted({"extracted_by": by}) and O.trusted({"extracted_by": by, "review": "pending"})
    assert not O.trusted({"extracted_by": "pidkg_vision", "review": "pending"})
    assert not O.trusted({"extracted_by": "pidkg_vision", "review": "rejected"})
    assert not O.trusted({"extracted_by": "pidkg_vision"}) and not O.trusted({"extracted_by": "llm"}) and not O.trusted({})
    assert O.trusted({"extracted_by": "pidkg_vision", "review": "accepted"}) and O.trusted({"extracted_by": "llm", "review": "accepted"})


def test_a_pending_segment_is_invisible_to_safety_and_visible_to_exploration():
    res, store = _reconcile()
    LP.apply(store, res)
    safe = TrustedView(store)
    assert store.nodes("Segment") and safe.nodes("Segment") == [] and safe.nodes("InlineItem") == [] and safe.nodes("ControlLoop") == []
    assert safe.counts()["nodes"] == 49 and safe.counts()["rels"] == 164      # exactly the v1.2 graph
    assert not any(r["end_label"] == "Segment" for r in safe.rels("MEASURES")) and safe.rels("FLOWS_TO") == [] and safe.rels("SIGNAL_TO") == []
    assert safe.left_out() == {"nodes": len(res["nodes"]), "rels": len(res["rels"])}

    seg = next(n for n in res["nodes"] if n["label"] == "Segment" and n["key"]["segment_id"] == "L-101.3")
    measures = next(r for r in res["rels"] if r["type"] == "MEASURES" and r["start_key"]["tag"] == "PT-1001A")
    res2, store2 = _reconcile(review={seg["props"]["fact_id"]: "accepted", measures["props"]["fact_id"]: "accepted"})
    LP.apply(store2, res2)
    safe2 = TrustedView(store2)
    assert [n["key"]["segment_id"] for n in safe2.nodes("Segment")] == ["L-101.3"]
    assert [(r["start_key"]["tag"], r["end_key"]["segment_id"]) for r in safe2.rels("MEASURES") if r["end_label"] == "Segment"] == [("PT-1001A", "L-101.3")]
    assert safe2.rels("FLOWS_TO") == []                                  # its flow relationships are still pending


def test_an_accepted_relationship_to_a_pending_node_stays_hidden():
    res, _ = _reconcile()
    measures = next(r for r in res["rels"] if r["type"] == "MEASURES" and r["start_key"]["tag"] == "PT-1005")
    res2, store2 = _reconcile(review={measures["props"]["fact_id"]: "accepted"})
    LP.apply(store2, res2)
    assert not any(r["end_label"] == "Segment" for r in TrustedView(store2).rels("MEASURES"))


def _patterns(cypher: str):
    """(variable, types, variable_length) for every relationship pattern in a Cypher text."""
    for m in re.finditer(r"\[\s*(\w*)\s*:\s*([A-Za-z_|%]+)\s*(\*[^\]]*)?\]", cypher):
        yield m.group(1), set(m.group(2).split("|")), bool(m.group(3))


def _cypher_sources():
    out = {name: getattr(Q, name) for name in dir(Q) if name.startswith("Q_")}
    out["Q_MOC"] = Q.Q_MOC % (Q.IMPACT_RELS, 3)
    return out


def test_every_safety_template_filters_what_vision_can_write():
    """Static check (runs without Neo4j): a pattern over a relationship type the vision loader can write
    must name the relationship and test it with the T7 predicate; a variable-length path must test all of them."""
    assert Q.trusted_rel("r") == "(r.extracted_by IN ['table', 'manual', 'pid_audit'] OR r.review = 'accepted')"
    sources = _cypher_sources()
    assert {"Q_AS_INITIATOR", "Q_CANDIDATE_COMPENSATION", "Q_SHELVE", "Q_SHELVE_COVER", "Q_MOC", "Q_TRIP"} <= set(sources)
    checked = 0
    for name, cypher in sources.items():
        for var, types, varlen in _patterns(cypher):
            if varlen:
                assert re.search(r"all\(\s*\w+ IN relationships\(\w+\) WHERE \(\w+\.extracted_by IN", cypher), f"{name}: unfiltered path {types}"
                checked += 1
            elif types & VISION_WRITABLE:
                assert var, f"{name}: [{':'.join(types)}] has no variable to filter on"
                assert Q.trusted_rel(var) in cypher, f"{name}: relationship {var}:{types} is not filtered (T7)"
                checked += 1
    assert checked == 11
    # report.py builds its Cypher inline, so the same rule is checked on its source text
    report = (ROOT / "pid_graph" / "report.py").read_text(encoding="utf-8")
    seen = 0
    for var, types, varlen in _patterns(report):
        assert not varlen
        if types & VISION_WRITABLE:
            assert var and f'trusted_rel("{var}")' in report, f"report.py: relationship {var}:{types} is not filtered (T7)"
            seen += 1
    assert seen == 4


def test_templates_and_the_python_gate_use_the_same_rule():
    assert set(re.findall(r"'(\w+)'", Q.trusted_rel("r").split(" OR ")[0])) == set(O.TRUSTED_EXTRACTED_BY)
    assert "pidkg_vision" not in O.TRUSTED_EXTRACTED_BY and "llm" not in O.TRUSTED_EXTRACTED_BY


def test_exploratory_output_says_it_may_use_pending_facts():
    assert "pending" in Q.EXPLORATORY_NOTE and "exploration only" in Q.EXPLORATORY_NOTE
    src = (ROOT / "pid_graph" / "mcp_server.py").read_text(encoding="utf-8")
    assert "EXPLORATORY_NOTE" in src and "review=pending" in src


def test_explorer_leaves_pending_facts_out_unless_asked():
    from pid_graph.explorer import build
    res, store = _reconcile()
    LP.apply(store, res)
    page = build(store, "U-100", "t")
    assert '"label": "Segment"' not in page and "pending vision facts left out" in page
    full = build(store, "U-100", "t", include_pending=True)
    assert '"label": "Segment"' in full and "EXPLORATION" in full


# ---- markup -------------------------------------------------------------------------
def _annots(path):
    import pymupdf
    with pymupdf.open(path) as doc:
        return [(p.number + 1, a.type[1], tuple(round(c, 2) for c in (a.colors.get("stroke") or ())), a.info.get("content", ""))
                for p in doc for a in p.annots()]


def test_markup_colours_pending_accepted_rejected_and_exceptions(tmp_path):
    res, _ = _reconcile()
    before = hashlib.sha256(PDF.read_bytes()).hexdigest()
    out = RV.markup(PDF, res, tmp_path / "review_markup_U-100.pdf")
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == before        # the controlled document is never touched
    annots = _annots(out)
    colours = Counter(a[2] for a in annots if a[1] != "FreeText")
    assert colours[AMBER] > 20 and colours[RED] >= len([e for e in res["exceptions"] if "bbox=" in e["refs"]]) and colours[GREEN] == 0
    assert {a[0] for a in annots} == {2, 3, 4}                           # every drawing page carries a legend at least
    text = " ".join(a[3] for a in annots)
    assert "X21" in text and "X29" in text and "L-101.2" in text and "trip" in text
    ids = {x["props"]["fact_id"] for x in res["nodes"] + res["rels"]}
    assert sum(1 for i in ids if i in text) > 40                         # annotations carry the fact ids of the register

    seg = next(n for n in res["nodes"] if n["key"].get("segment_id") == "L-101.2")
    flows = [r for r in res["rels"] if r["type"] == "FLOWS_TO" and "L-101.2" in json.dumps([r["start_key"], r["end_key"]])]
    item = next(n for n in res["nodes"] if n["label"] == "InlineItem")
    review = {seg["props"]["fact_id"]: "accepted", **{f["props"]["fact_id"]: "accepted" for f in flows}, item["props"]["fact_id"]: "rejected"}
    register = {item["props"]["fact_id"]: {**next(r for r in RV.rows(res) if r["fact_id"] == item["props"]["fact_id"]),
                                          "review": "rejected", "reviewer": "AB"}}
    res2, _ = _reconcile(review=review)
    colours2 = Counter(a[2] for a in _annots(RV.markup(PDF, res2, tmp_path / "m2.pdf", register=register)) if a[1] != "FreeText")
    assert colours2[GREEN] >= 1 and colours2[RED] == colours[RED] + 1 and colours2[AMBER] < colours[AMBER]


def test_pipeline_writes_register_and_markup_and_reads_decisions_back(tmp_path):
    from pid_graph.run_all import main
    args = ["--unit", "U-100", "--backend", "memory", "--pdf", str(PDF), "--transmittal", "TX-0057", "--load-run", "TX-0057-BASELINE",
            "--pidkg", str(FIXTURE), "--out", str(tmp_path)]
    assert main(args) == 0
    reg = tmp_path / "review_register_U-100.xlsx"
    assert reg.is_file() and (tmp_path / "review_markup_U-100.pdf").is_file()
    row = next(r for r in _sheet_rows(reg) if r["type"] == "Segment")
    _decide(reg, row["fact_id"], "accepted")
    assert main(args) == 0
    graph = json.loads((tmp_path / "graph_U-100.json").read_text(encoding="utf-8"))
    reviews = Counter(n["props"]["review"] for n in graph["nodes"] if n["label"] == "Segment")
    assert reviews["accepted"] == 1 and reviews["pending"] == sum(reviews.values()) - 1
    rep = json.loads((tmp_path / "load_report_U-100.json").read_text(encoding="utf-8"))
    assert rep["review"]["accepted"] == 1 and rep["review"]["problems"] == []
