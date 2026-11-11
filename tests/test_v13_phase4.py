"""v1.3 Phase 4 (PIDKG_UPGRADE.md): load_pidkg.py, the adapter from pid-to-kg's graph.json.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Vision proposes, the instrument index disposes, an engineer accepts. Every row of the mapping
table in the module docstring has a case here. Expected counts are computed from the frozen
Phase 3 fixture, never typed in; rows the fixture cannot show are made by editing a copy of it.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402
from pid_graph import ontology as O  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.tags import canonical_tag  # noqa: E402

DATA = ROOT / "data"
FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
V12_DUMP = ROOT / "tests" / "fixtures" / "graph_U-100_v1_2.json"
NEW_LABELS = {"Segment", "InlineItem", "ControlLoop"}
SAFETY_RELS = set(O.INLINE_ITEM_BANNED_RELS)


def _store(pdf: bool = True):
    store, _ = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                           srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                           curated=DATA / "curated" / "compensating_measures_U-100.csv",
                           topology=DATA / "pid_audit_U100_topology.csv",
                           pdf=DATA / "U100-PIDS-TX-0057.pdf" if pdf else None, transmittal="TX-0057" if pdf else None,
                           load_run="TX-0057-BASELINE")
    return store


def _run(graph, store=None, **kw):
    store = store or _store()
    return LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE", **kw), store


@pytest.fixture(scope="module")
def pidkg() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def result(pidkg):
    return _run(pidkg)[0]


@pytest.fixture(scope="module")
def facts(pidkg):
    """What the fixture holds, worked out here independently of the loader."""
    store = _store()
    index = LP.index_tags(store)
    nodes = {n["id"]: n for n in pidkg["nodes"]}
    of = lambda t: [n for n in pidkg["nodes"] if n["type"] == t]
    lines = {n["key"]["line_no"] for n in store.nodes("Line")}
    equipment = {n["key"]["tag"] for n in store.nodes("Equipment")}
    sig = [e for e in pidkg["edges"] if e["type"] == "SIGNAL_TO"]
    interlocks = {n["id"] for n in of("Instrument") if canonical_tag(n.get("tag")) not in index
                  and any(e["target"] == n["id"] for e in sig) and any(e["source"] == n["id"] for e in sig)
                  and all(e["attributes"].get("purpose") == "trip" for e in sig if n["id"] in (e["source"], e["target"]))}
    return {"store": store, "index": index, "nodes": nodes, "of": of, "lines": lines, "equipment": equipment, "sig": sig,
            "interlocks": interlocks,
            "tagged_not_in_index": {canonical_tag(n["tag"]) for n in of("Instrument") + of("Component")
                                    if n.get("tag") and n["id"] not in interlocks and canonical_tag(n["tag"]) not in index},
            "untagged_components": [n for n in of("Component") if not n.get("tag")],
            "numbered_segments": [n for n in of("PipeSegment") if canonical_tag(n["attributes"].get("line_number")) in lines],
            "unnumbered_lines": {(n["sheets"][0], n["attributes"]["line_id"]) for n in of("PipeSegment")
                                 if canonical_tag(n["attributes"].get("line_number")) not in lines}}


def _by(result, code):
    return [e for e in result["exceptions"] if e["code"] == code]


def _rels(result, typ):
    return [r for r in result["rels"] if r["type"] == typ]


# ---- the index and the shape of the result ---------------------------------------
def test_index_is_the_instrument_index_not_the_graph(facts):
    index = facts["index"]
    assert {"PT-1001A", "XV-1001", "TT-1003", "PV-1005"} <= index
    assert "FT-1006" not in index and "PT-1001D" not in index          # stubs from the P&ID and the C&E are not index rows
    assert len(index) == 17


def test_result_shape(result):
    assert {"nodes", "rels", "exceptions", "skipped", "conflicts", "seen", "drawn_trips", "summary"} <= set(result)
    assert {n["label"] for n in result["nodes"]} <= NEW_LABELS          # the loader never creates a v1.2 node
    for item in result["nodes"] + result["rels"]:
        p = item["props"]
        assert p["extracted_by"] == "pidkg_vision" and p["review"] == "pending"
        assert p["source_doc"].startswith("PID-100-") and p["source_rev"] in ("A", "B", "D") and p["load_run"] == "TX-0057-BASELINE"
        assert p["source_ref"].startswith("U100-PIDS-TX-0057.pdf:p") and p["fact_id"] and 0 < p["confidence"] <= 1
    ids = [x["props"]["fact_id"] for x in result["nodes"] + result["rels"]]
    assert len(ids) == len(set(ids))


# ---- mapping table, row by row -----------------------------------------------------
def test_sheet_matches_document_by_number_and_revision(pidkg, result):
    assert _by(result, "X23") == []
    g = copy.deepcopy(pidkg)
    next(n for n in g["nodes"] if n["id"] == "SHEET:PID-100-002")["attributes"]["revision"] = "Z"
    r, _ = _run(g)
    assert [e["id"] for e in _by(r, "X23")] == ["PID-100-002 rev Z"]
    assert all(x["props"]["source_doc"] != "PID-100-002" for x in r["nodes"] + r["rels"])     # nothing from an unmatched sheet


def test_sheet_without_title_block_pass_is_an_exception(pidkg):
    r, _ = _run(pidkg, _store(pdf=False))                                # Documents are rev UNKNOWN: no sheet matches
    assert len(_by(r, "X23")) == 3 and r["nodes"] == [] and r["rels"] == []


def test_tagged_equipment_maps_to_existing_equipment(pidkg, result, facts):
    assert not any(n["label"] == "Equipment" for n in result["nodes"])
    assert any(r["start_label"] == "Equipment" and r["start_key"] == {"tag": "V-1002"} for r in _rels(result, "FLOWS_TO"))
    g = copy.deepcopy(pidkg)
    g["nodes"].append({"id": "V-9999", "type": "Equipment", "label": "V-9999", "tag": "V-9999", "kind": "vessel",
                       "sheets": ["SHEET:PID-100-001"], "confidence": 0.9, "attributes": {},
                       "provenance": [{"sheet": "SHEET:PID-100-001", "page": 2, "bbox": [0.1, 0.1, 0.2, 0.2]}]})
    r, _ = _run(g)
    assert ("Equipment", "V-9999") in {(e["label"], e["id"]) for e in _by(r, "X21")}


def test_boundary_maps_onto_battery_limit_equipment_by_the_tag_in_its_text(pidkg, result, facts):
    names = [n["name"] for n in facts["of"]("Boundary")]
    expect_miss = sorted(n for n in names if not any(t in n.upper().replace(",", " ").split() for t in facts["equipment"]))
    assert sorted(e["id"] for e in _by(result, "X24")) == expect_miss
    assert "FUTURE FUEL GAS" in expect_miss and "FEED GAS FROM BL-100" not in expect_miss
    ends = {(r["start_label"], tuple(r["start_key"].values())[0]) for r in _rels(result, "FLOWS_TO")} | \
           {(r["end_label"], tuple(r["end_key"].values())[0]) for r in _rels(result, "FLOWS_TO")}
    assert {("Equipment", "BL-100"), ("Equipment", "FLARE-HDR"), ("Equipment", "BL-103"), ("Equipment", "BL-200")} <= ends


def test_tagged_instruments_and_valves_must_be_in_the_index(result, facts):
    x21 = {e["id"] for e in _by(result, "X21")}
    assert x21 == facts["tagged_not_in_index"]
    assert {"FT-1006", "LIC-1006", "FIC-1004", "PIC-1005"} <= x21
    used = {tuple(k.values())[0] for r in result["rels"] for lab, k in ((r["start_label"], r["start_key"]), (r["end_label"], r["end_key"]))
            if lab == "Instrument"}
    assert used <= facts["index"] and not (used & x21)                  # T1: no fact touches a tag outside the index
    assert {"XV-1001", "LV-1006", "PV-1005", "HV-1001"} <= used         # tagged Components became Instruments, not InlineItems
    assert not any(n["label"] == "Instrument" for n in result["nodes"])


def test_untagged_components_become_inline_items(result, facts):
    items = [n for n in result["nodes"] if n["label"] == "InlineItem"]
    loaded_docs = {s["props"]["source_doc"] for s in result["nodes"] if s["label"] == "Segment"}
    sheet_doc = {n["id"]: n["attributes"]["drawing_number"] for n in facts["of"]("Sheet")}
    expect = [c for c in facts["untagged_components"] if sheet_doc[c["sheets"][0]] in loaded_docs]
    assert len(items) == len(expect) > 0
    for it in items:
        assert it["key"]["item_id"].split(".")[0] in loaded_docs and it["props"]["indexed"] is False
        assert it["props"]["kind"] and it["props"]["normal_position"]
    assert {"check_valve", "reducer", "gate_valve"} <= {it["props"]["kind"] for it in items}
    lo = [it for it in items if it["props"]["normal_position"] == "open"]
    assert len(lo) == 1 and lo[0]["props"]["source_doc"] == "PID-100-001"          # the locked-open valve on L-104


def test_pipe_segments_become_segments_of_their_line(result, facts):
    segs = [n for n in result["nodes"] if n["label"] == "Segment"]
    assert len(segs) == len(facts["numbered_segments"]) > 0
    per_line = Counter(canonical_tag(n["attributes"]["line_number"]) for n in facts["numbered_segments"])
    assert Counter(s["props"]["line_no"] for s in segs) == per_line
    for line, n in per_line.items():                                    # <line_no>.<k>, numbered 1..n across sheets
        assert {s["key"]["segment_id"] for s in segs if s["props"]["line_no"] == line} == {f"{line}.{k}" for k in range(1, n + 1)}
    of = {(r["start_key"]["segment_id"], r["end_key"]["line_no"]) for r in _rels(result, "SEGMENT_OF")}
    assert of == {(s["key"]["segment_id"], s["props"]["line_no"]) for s in segs}
    assert all(s["props"]["size"] and s["props"]["service"] for s in segs)
    l102 = {s["props"]["source_doc"] for s in segs if s["props"]["line_no"] == "L-102"}
    assert l102 == {"PID-100-001", "PID-100-002"}                       # one line drawn on two sheets, no key collision


def test_unknown_line_is_an_exception_not_a_segment(pidkg, result, facts):
    assert len(_by(result, "X25")) == len(facts["unnumbered_lines"]) == 2
    g = copy.deepcopy(pidkg)
    for n in g["nodes"]:
        if n["type"] == "PipeSegment" and n["attributes"].get("line_number") == "L-104":
            n["attributes"]["line_number"] = "L-999"
    r, _ = _run(g)
    assert any("L-999" in e["id"] for e in _by(r, "X25"))
    assert not any(s["props"]["line_no"] in ("L-104", "L-999") for s in r["nodes"] if s["label"] == "Segment")


def test_off_page_connectors_are_not_nodes(pidkg, result, facts):
    assert not any("OPC" in json.dumps(n["key"]) for n in result["nodes"])
    off = [r for r in _rels(result, "FLOWS_TO") if r["props"].get("off_page") is True]
    pairs = [e for e in pidkg["edges"] if e["type"] == "FLOWS_TO" and e["attributes"].get("off_page")]
    assert len(off) == len(pairs) == 2
    for r in off:
        assert r["start_label"] == r["end_label"] == "Segment"
        assert r["start_key"]["segment_id"].split(".")[0] == r["end_key"]["segment_id"].split(".")[0]      # same line both sides
    assert _by(result, "X26") == []
    g = copy.deepcopy(pidkg)
    g["edges"] = [e for e in g["edges"] if not (e["source"] == "P02.OPC1" and e["target"] == "P03.OPC1")]
    r, _ = _run(g)
    assert len(_by(r, "X26")) == 2 and len([x for x in _rels(r, "FLOWS_TO") if x["props"].get("off_page") is True]) == 1


def test_flows_to_carries_direction_and_confidence(pidkg, result, facts):
    flows = _rels(result, "FLOWS_TO")
    assert flows and all(r["props"]["flow_direction"] in O.FLOW_DIRECTIONS for r in flows)
    assert all(r["start_label"] in O.RELS["FLOWS_TO"][0] and r["end_label"] in O.RELS["FLOWS_TO"][1] for r in flows)
    # L-101, in order: BL-100 -> seg -> HV-1001 -> seg -> XV-1001 -> seg -> (FT-1004 is in the index) -> seg -> V-1002
    nxt = {(r["start_label"], tuple(r["start_key"].values())[0]): (r["end_label"], tuple(r["end_key"].values())[0]) for r in flows
           if "L-101" in json.dumps([r["start_key"], r["end_key"]]) or r["props"]["source_doc"] == "PID-100-001"}
    walk, at = [], ("Equipment", "BL-100")
    while at in nxt and at != ("Equipment", "V-1002") and len(walk) < 20:
        walk.append(at[1]); at = nxt[at]
    walk.append(at[1])
    assert [w for w in walk if not w.startswith("L-101.")] == ["BL-100", "HV-1001", "XV-1001", "FT-1004", "V-1002"]


def test_measures_on_a_segment_is_loaded_and_on_equipment_is_compared(pidkg, result, facts):
    seg = _rels(result, "MEASURES")
    expect = [e for e in pidkg["edges"] if e["type"] == "MEASURES" and facts["nodes"][e["target"]]["type"] == "PipeSegment"
              and canonical_tag(facts["nodes"][e["source"]]["tag"]) in facts["index"]]
    assert len(seg) == len(expect) > 0 and all(r["end_label"] == "Segment" for r in seg)
    assert {r["start_key"]["tag"] for r in seg} >= {"PT-1001A", "PT-1005", "PI-1001"}
    on_eq = [e for e in pidkg["edges"] if e["type"] == "MEASURES" and facts["nodes"][e["target"]]["type"] == "Equipment"]
    assert result["skipped"]["MEASURES on Equipment: agrees with the index"] == len(on_eq) > 0 and result["conflicts"] == []
    g = copy.deepcopy(pidkg)                                             # vision puts LT-1006 on another vessel
    g["nodes"].append({"id": "V-1003", "type": "Equipment", "label": "V-1003", "tag": "V-1002X", "kind": "vessel",
                       "sheets": ["SHEET:PID-100-001"], "confidence": 0.9, "attributes": {}, "provenance": []})
    next(e for e in g["edges"] if e["type"] == "MEASURES" and e["source"] == "LT-1006")["target"] = "BOUNDARY:LIQUID TO BL-103"
    r, _ = _run(g)
    assert [(c["key"], c["prop"]) for c in r["conflicts"]] == [({"tag": "LT-1006"}, "MEASURES")]
    assert "V-1002" in r["conflicts"][0]["existing"] and "BL-103" in r["conflicts"][0]["incoming"]


def test_interlock_symbols_are_collapsed_into_direct_trip_signals(pidkg, result, facts):
    sig = _rels(result, "SIGNAL_TO")
    expect = set()
    for i in facts["interlocks"]:
        ins = [e["source"] for e in facts["sig"] if e["target"] == i]
        outs = [e["target"] for e in facts["sig"] if e["source"] == i]
        expect |= {(a, b, facts["nodes"][i]["tag"]) for a in ins for b in outs}
    got = {(r["start_key"]["tag"], r["end_key"]["tag"], r["props"]["via"]) for r in sig if r["props"]["purpose"] == "trip"}
    assert got == expect and len(expect) == 10
    assert ("PT-1001A", "BDV-1001", "I-1") in got and ("LT-1002B", "XV-1002", "I-2") in got
    assert {r["props"]["via_name"] for r in sig if r["props"]["purpose"] == "trip"} == {"SIF-100-01", "SIF-100-02"}
    assert sorted(e["id"] for e in _by(result, "X29")) == ["I-1", "I-2"]            # one row per diamond, nothing hidden
    assert not ({"I-1", "I-2"} & {e["id"] for e in _by(result, "X21")})
    assert sorted((t["from"], t["to"], t["via"]) for t in result["drawn_trips"]) == sorted(expect)
    # control and measurement signals all touch a DCS controller that is not in the index, so none is loaded
    other = [e for e in facts["sig"] if e["attributes"]["purpose"] != "trip"]
    assert all(canonical_tag(facts["nodes"][x]["tag"]) not in facts["index"] for e in other for x in (e["source"], e["target"])
               if facts["nodes"][x]["tag"] in ("LIC-1006", "FIC-1004", "PIC-1005")) and len(sig) == len(expect)
    assert result["skipped"]["SIGNAL_TO: an end is not loaded"] == len(other)


def test_control_loops_and_membership(pidkg, result, facts):
    loops = {n["key"]["loop_key"]: n for n in result["nodes"] if n["label"] == "ControlLoop"}
    assert set(loops) == {"P-1001", "L-1002", "L-1006", "P-1005", "F-1004"}       # not the diamonds' own loops I-1 / I-2
    assert loops["P-1005"]["props"]["loop_type"] == "control" and loops["L-1002"]["props"]["loop_type"] == "interlock"
    members = {(r["start_key"]["tag"], r["end_key"]["loop_key"], r["props"]["role"]) for r in _rels(result, "MEMBER_OF")}
    assert {("PT-1005", "P-1005", "sensor"), ("PV-1005", "P-1005", "final_element"), ("LT-1006", "L-1006", "sensor"),
            ("LV-1006", "L-1006", "final_element"), ("FT-1004", "F-1004", "sensor")} <= members
    assert all(role in O.LOOP_ROLES for _, _, role in members)
    assert not any(tag in ("PI-1001", "LG-1002") for tag, _, _ in members)          # gauges have no role in the closed list
    assert all(tag in facts["index"] for tag, _, _ in members)
    assert result["skipped"]["ControlLoop: loop of a collapsed interlock symbol"] == len(facts["interlocks"])


def test_derived_and_foreign_relationships_are_skipped_by_design(pidkg, result):
    counts = Counter(e["type"] for e in pidkg["edges"])
    for typ in ("FEEDS", "ACTUATES", "TRIPS", "PART_OF"):
        assert result["skipped"][f"{typ}: skipped by design"] == counts[typ] > 0
    assert result["skipped"]["Plant: skipped by design"] == 1
    assert not ({r["type"] for r in result["rels"]} & {"FEEDS", "ACTUATES", "TRIPS", "PART_OF", "CASCADES_TO", "HAS_STATE"})
    g = copy.deepcopy(pidkg)
    g["edges"].append({"id": "E99999", "source": "LOOP:P-1001", "target": "LOOP:L-1002", "type": "CASCADES_TO", "confidence": 1.0,
                       "derived": True, "attributes": {}})
    r, _ = _run(g)
    assert r["skipped"]["CASCADES_TO: skipped by design"] == 1 and not _rels(r, "CASCADES_TO")


def test_qa_issues_and_unreadable_items_become_exception_rows(pidkg, result):
    assert len(_by(result, "X27")) == len(pidkg["issues"]) == 1
    g = copy.deepcopy(pidkg)
    next(n for n in g["nodes"] if n["id"] == "SHEET:PID-100-003")["attributes"]["unreadable"] = [
        {"description": "smudged tag near the strainer", "bbox": [0.4, 0.3, 0.45, 0.35]}]
    g["issues"].append({"severity": "error", "code": "unresolved_reference", "message": "x", "node": "P04.V9"})
    r, _ = _run(g)
    x27 = _by(r, "X27")
    assert len(x27) == 3 and any("smudged" in e["detail"] for e in x27) and any("unresolved_reference" in e["detail"] for e in x27)
    assert {n["label"] for n in r["nodes"]} <= NEW_LABELS


def test_index_tag_not_seen_by_vision_on_its_sheet(result, facts):
    assert [e["id"] for e in _by(result, "X22")] == ["TT-1003"]          # T2; XV-1002 is seen on a sheet it is SHOWN_ON
    assert result["seen"]["XV-1002"] == ["PID-100-001"] and "TT-1003" not in result["seen"]


# ---- safety, schema and the gate -------------------------------------------------
def test_nothing_safety_relevant_is_written(result):
    assert not ({r["type"] for r in result["rels"]} & SAFETY_RELS)
    assert {r["type"] for r in result["rels"]} <= {"SEGMENT_OF", "FLOWS_TO", "SIGNAL_TO", "MEMBER_OF", "MEASURES", "INSTALLED_ON", "SHOWN_ON"}
    for r in result["rels"]:
        O.check_rel(r["type"], r["start_label"], r["end_label"])


def test_every_new_node_has_a_relationship(result):
    touched = {(r[f"{e}_label"], json.dumps(r[f"{e}_key"], sort_keys=True)) for r in result["rels"] if r["type"] != "SHOWN_ON"
               for e in ("start", "end")}
    assert all((n["label"], json.dumps(n["key"], sort_keys=True)) in touched for n in result["nodes"])
    shown = {(r["start_label"], json.dumps(r["start_key"], sort_keys=True)) for r in _rels(result, "SHOWN_ON")}
    assert shown == {(n["label"], json.dumps(n["key"], sort_keys=True)) for n in result["nodes"]}


def test_a_rejected_fact_is_not_written_and_an_accepted_one_keeps_its_decision(pidkg, result):
    seg = next(n for n in result["nodes"] if n["label"] == "Segment")
    flow = _rels(result, "FLOWS_TO")[0]
    review = {seg["props"]["fact_id"]: "accepted", flow["props"]["fact_id"]: "rejected"}
    r, _ = _run(pidkg, review=review)
    ids = {x["props"]["fact_id"]: x for x in r["nodes"] + r["rels"]}
    assert ids[seg["props"]["fact_id"]]["props"]["review"] == "accepted"
    assert flow["props"]["fact_id"] not in ids and r["skipped"]["rejected in the review register"] == 1
    # the accepted Segment and its own SHOWN_ON (which follows the node's decision) are the only non-pending facts
    assert Counter(x["props"]["review"] for x in ids.values()) == {"pending": len(ids) - 2, "accepted": 2}


# ---- apply -----------------------------------------------------------------------
def test_dry_run_changes_nothing_and_apply_twice_changes_nothing_more(pidkg):
    res, store = _run(pidkg)
    before = json.dumps(store.to_dict(), default=str)
    assert before == json.dumps(_store().to_dict(), default=str)        # reconcile is pure
    LP.apply(store, res)
    once = json.dumps(store.to_dict(), default=str)
    assert once != before
    res2 = LP.reconcile(pidkg, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE")
    LP.apply(store, res2)
    assert json.dumps(store.to_dict(), default=str) == once              # idempotent
    c = store.counts()
    assert c["by_label"]["Segment"] == len([n for n in res["nodes"] if n["label"] == "Segment"])
    assert c["nodes"] == 49 + len(res["nodes"]) and c["rels"] == 164 + len(res["rels"]) and store.conflicts == []


def test_v12_part_of_the_graph_is_untouched_by_apply(pidkg):
    res, store = _run(pidkg)
    LP.apply(store, res)
    # Phase 10 adds the informative dexpiClass pair to nodes vision saw; everything else about a v1.2 node is untouched
    plain = lambda n: {**n, "props": {k: v for k, v in n["props"].items() if k not in ("dexpiClass", "dexpiClass_source")}}
    v12 = {"nodes": [plain(n) for n in store.nodes() if n["label"] not in NEW_LABELS],
           "rels": [r for r in store.rels() if r["props"].get("extracted_by") != "pidkg_vision"], "conflicts": []}
    assert (json.dumps(v12, indent=1, default=str) + "\n").encode() == V12_DUMP.read_bytes().replace(b"\r\n", b"\n")


def test_run_all_with_the_loader_off_is_v12_and_on_adds_the_vision_layer(tmp_path, pidkg):
    from pid_graph.run_all import main
    common = ["--unit", "U-100", "--backend", "memory", "--pdf", str(DATA / "U100-PIDS-TX-0057.pdf"), "--transmittal", "TX-0057",
              "--load-run", "TX-0057-BASELINE"]
    assert main(common + ["--out", str(tmp_path / "off")]) == 0
    assert (tmp_path / "off" / "graph_U-100.json").read_bytes().replace(b"\r\n", b"\n") + b"\n" == V12_DUMP.read_bytes().replace(b"\r\n", b"\n")
    assert main(common + ["--out", str(tmp_path / "on"), "--pidkg", str(FIXTURE)]) == 0
    on = json.loads((tmp_path / "on" / "graph_U-100.json").read_text(encoding="utf-8"))
    assert {n["label"] for n in on["nodes"]} >= NEW_LABELS
    rep = json.loads((tmp_path / "on" / "load_report_U-100.json").read_text(encoding="utf-8"))
    assert rep["pidkg"]["exceptions_by_code"]["X21"] == 4 and rep["reconcile"]["exceptions_by_code"]["X21"] == 4
    from openpyxl import load_workbook
    codes = {r[0] for r in load_workbook(tmp_path / "on" / "exception_register_U-100.xlsx")["Exceptions"].iter_rows(values_only=True)}
    assert {"X21", "X22", "X24", "X25", "X27", "X29"} <= codes


def test_cli_is_dry_run_by_default(tmp_path, pidkg, capsys):
    args = ["--graph", str(FIXTURE), "--pdf", str(DATA / "U100-PIDS-TX-0057.pdf"), "--transmittal", "TX-0057", "--out", str(tmp_path)]
    assert LP.main(args) == 0
    assert "DRY RUN" in capsys.readouterr().out and list(tmp_path.iterdir()) == []
    assert LP.main(args + ["--apply"]) == 0
    assert (tmp_path / "graph_U-100.json").is_file()
