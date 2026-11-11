"""v1.3 Phase 7 (PIDKG_UPGRADE.md): fixed templates for CQ14-CQ18, on both backends.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Each template is written once over a small set of backend primitives; the Cypher and the
in-memory form of every primitive must give the same rows. Safety-relevant templates use
trusted facts only (T7); asked to include pending facts, they say so in their header.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402
from pid_graph import queries as Q  # noqa: E402
from pid_graph import topology_queries as TQ  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402

DATA = ROOT / "data"
FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
VISION_WRITABLE = {"MEASURES", "INSTALLED_ON", "SHOWN_ON", "SEGMENT_OF", "FLOWS_TO", "SIGNAL_TO", "MEMBER_OF"}
CALLS = [("isolation", "PT-1001A"), ("isolation", "PT-1005"), ("isolation", "FT-1004"), ("isolation", "XV-1002"), ("isolation", "LT-1006"),
         ("same_pressure", "PT-1001A"), ("same_pressure", "PT-1005"), ("blast_radius", "XV-1001"), ("blast_radius", "L-103.2"),
         ("blast_radius", "PID-100-001.V1"), ("blast_radius", "HV-1001"), ("loop_membership", "PV-1005"), ("loop_membership", "XV-1001"),
         ("loop_membership", "LV-1006"), ("drawing_vs_ce", None), ("isolation", "NOT-A-TAG"), ("blast_radius", "NOPE")]


def _store(review=None):
    store = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                        srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                        curated=DATA / "curated" / "compensating_measures_U-100.csv", topology=DATA / "pid_audit_U100_topology.csv",
                        pdf=DATA / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="TX-0057-BASELINE")[0]
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    res = LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE", review=review)
    LP.apply(store, res)
    return store, res


@pytest.fixture(scope="module")
def store():
    return _store()[0]


def _call(src, name, arg, **kw):
    fn = getattr(TQ, name)
    return fn(src, **kw) if arg is None else fn(src, arg, **kw)


# ---- CQ14 isolation ------------------------------------------------------------------
def test_cq14_isolation_valves_each_way_to_the_next_equipment(store):
    r = TQ.isolation(store, "PT-1001A", include_pending=True)
    assert r["cq"] == "CQ14" and r["tag"] == "PT-1001A" and r["taps"] == ["L-101.3"] and r["in_line"] is False
    assert [(v["id"], v["kind"], v["hops"]) for v in r["upstream"]["valves"]] == [("XV-1001", "final_element", 1), ("HV-1001", "manual_valve", 3)]
    assert r["upstream"]["ends_at"] == ["BL-100"] and r["downstream"]["valves"] == [] and r["downstream"]["ends_at"] == ["V-1002"]
    assert r["upstream"]["open_ends"] == [] and r["downstream"]["open_ends"] == []

    r = TQ.isolation(store, "PT-1005", include_pending=True)
    assert r["upstream"]["valves"] == [] and r["upstream"]["ends_at"] == ["V-1002"]            # back across the off-page connector
    down = r["downstream"]["valves"]
    assert [(v["id"], v["label"], v["kind"]) for v in down] == [("PID-100-002.V1", "InlineItem", "gate_valve"),
                                                                ("PV-1005", "Instrument", "final_element"),
                                                                ("PID-100-002.V2", "InlineItem", "gate_valve")]
    assert [v["hops"] for v in down] == sorted(v["hops"] for v in down) and r["downstream"]["ends_at"] == ["BL-200"]
    assert all("reducer" not in v["kind"] for v in down)                                       # fittings are passed, not listed


def test_cq14_in_line_instrument_and_valve_start_from_themselves(store):
    r = TQ.isolation(store, "XV-1002", include_pending=True)
    assert r["taps"] == [] and r["in_line"] is True
    assert [v["id"] for v in r["upstream"]["valves"]] == ["LV-1006"] and r["upstream"]["ends_at"] == ["V-1002"]
    assert [(v["id"], v["kind"]) for v in r["downstream"]["valves"]] == [("PID-100-001.V2", "check_valve")] and r["downstream"]["ends_at"] == ["BL-103"]
    f = TQ.isolation(store, "FT-1004", include_pending=True)                                    # in-line and tapped: itself never listed
    assert f["in_line"] and f["taps"] == ["L-101.3"] and "FT-1004" not in json.dumps(f["upstream"]) + json.dumps(f["downstream"])


def test_cq14_says_when_vision_does_not_place_the_instrument(store):
    r = TQ.isolation(store, "LT-1006", include_pending=True)                                    # on the vessel: no segment, not in-line
    assert r["taps"] == [] and r["in_line"] is False and "not placed" in r["note"]
    assert TQ.isolation(store, "NOT-A-TAG", include_pending=True)["error"] == "not in graph"


# ---- CQ15 same pressure system ----------------------------------------------------------
def test_cq15_candidates_stop_at_actuated_valves_and_are_only_candidates(store):
    r = TQ.same_pressure(store, "PT-1001A", include_pending=True)
    assert r["cq"] == "CQ15" and r["heading"] == "candidates for curation — not compensating measures"
    got = {c["device"]: c for c in r["candidates"]}
    assert set(got) == {"PT-1001B", "PT-1001C", "PI-1001", "FT-1004", "PT-1005"}
    assert got["PT-1001B"]["hops"] == 0 and got["PT-1001B"]["segment"] == "L-101.3" and got["PT-1005"]["segment"] == "L-102.2"
    assert got["PT-1005"]["hops"] == 5 and got["PT-1005"]["alarms"] == ["PT-1005.PAH"] and got["PT-1005"]["system"] == "BPCS"
    assert {d for d, c in got.items() if c["same_variable"]} == {"PT-1001B", "PT-1001C", "PI-1001", "PT-1005"}
    assert r["blocked_at"] == ["BDV-1001", "LV-1006", "PV-1005", "XV-1001"]                     # reached, not crossed
    assert "PT-1001A" not in got


def test_cq15_a_closed_untagged_valve_blocks_too():
    store, _ = _store()
    lo = store.get_node("InlineItem", {"item_id": "PID-100-002.V1"})
    lo["props"]["normal_position"] = "closed"                                                  # as if drawn NC
    r = TQ.same_pressure(store, "PT-1005", include_pending=True)
    assert "PID-100-002.V1" in r["blocked_at"] and "PV-1005" not in r["blocked_at"]


def test_cq15_never_writes_anything(store):
    before = json.dumps(store.to_dict(), default=str)
    TQ.same_pressure(store, "PT-1001A", include_pending=True)
    assert json.dumps(store.to_dict(), default=str) == before and len(store.rels("COMPENSATES_FOR")) == 3
    src = (ROOT / "pid_graph" / "topology_queries.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(CREATE|MERGE|DELETE|DETACH|REMOVE)\b|\bSET\s+\w+\.", src) and "merge_rel" not in src and "merge_node" not in src


# ---- CQ16 MOC blast radius ------------------------------------------------------------------
def test_cq16_downstream_to_the_next_equipment_with_loops_and_sifs(store):
    r = TQ.blast_radius(store, "XV-1001", include_pending=True)
    assert r["cq"] == "CQ16" and r["label"] == "Instrument"
    assert [(d["id"], d["hops"]) for d in r["downstream"]] == [("L-101.3", 1), ("FT-1004", 2), ("L-101.4", 3), ("V-1002", 4)]
    assert r["ends_at"] == ["V-1002"] and r["open_ends"] == []
    assert r["instruments_affected"] == ["FT-1004", "PI-1001", "PT-1001A", "PT-1001B", "PT-1001C", "XV-1001"]
    assert [x["loop"] for x in r["loops"]] == ["F-1004", "L-1002", "P-1001"]
    assert next(x for x in r["loops"] if x["loop"] == "P-1001")["touched_by"] == ["PT-1001A", "PT-1001B", "PT-1001C", "XV-1001"]
    sifs = {s["sif"]: s for s in r["sifs"]}
    assert set(sifs) == {"SIF-100-01", "SIF-100-02", "SIF-100-03"}
    assert sifs["SIF-100-01"]["initiators"] == ["PT-1001A", "PT-1001B", "PT-1001C"] and sifs["SIF-100-01"]["final_elements"] == ["XV-1001"]
    assert sifs["SIF-100-03"]["initiators"] == [] and sifs["SIF-100-03"]["final_elements"] == ["XV-1001"]


def test_cq16_from_a_segment_and_from_an_untagged_valve(store):
    r = TQ.blast_radius(store, "L-103.2", include_pending=True)
    assert r["label"] == "Segment" and [d["id"] for d in r["downstream"]] == ["XV-1002", "L-103.3", "PID-100-001.V2", "L-103.4", "BL-103"]
    assert r["instruments_affected"] == ["XV-1002"] and [x["loop"] for x in r["loops"]] == ["L-1002"] and [s["sif"] for s in r["sifs"]] == ["SIF-100-02"]
    v = TQ.blast_radius(store, "PID-100-001.V1", include_pending=True)
    assert v["label"] == "InlineItem" and v["ends_at"] == ["FLARE-HDR"] and v["instruments_affected"] == ["BDV-1001"]
    assert [s["sif"] for s in v["sifs"]] == ["SIF-100-01"]
    assert TQ.blast_radius(store, "NOPE", include_pending=True)["error"] == "not in graph"


# ---- CQ17 loop membership ---------------------------------------------------------------------
def test_cq17_loop_sensor_and_the_segment_it_measures(store):
    r = TQ.loop_membership(store, "PV-1005", include_pending=True)
    assert r["cq"] == "CQ17" and len(r["loops"]) == 1
    lp = r["loops"][0]
    assert (lp["loop"], lp["loop_type"], lp["variable"]) == ("P-1005", "control", "pressure")
    assert lp["members"] == [{"tag": "PT-1005", "role": "sensor"}, {"tag": "PV-1005", "role": "final_element"}]
    assert lp["sensors"] == [{"tag": "PT-1005", "segments": ["L-102.2"], "index_location": ["L-102"]}]
    x = TQ.loop_membership(store, "XV-1001", include_pending=True)
    assert [l["loop"] for l in x["loops"]] == ["L-1002", "P-1001"]
    assert next(l for l in x["loops"] if l["loop"] == "L-1002")["sensors"] == [
        {"tag": "LT-1002A", "segments": [], "index_location": ["V-1002"]}, {"tag": "LT-1002B", "segments": [], "index_location": ["V-1002"]}]


# ---- CQ18 drawing vs C&E ------------------------------------------------------------------------
def test_cq18_drawn_trips_against_the_c_and_e(store):
    r = TQ.drawing_vs_ce(store)
    assert r["cq"] == "CQ18" and "EXPLORATION" in r["basis"]                                   # reads pending facts by default, and says so
    assert r["drawn_not_in_ce"] == [] and r["ce_not_drawn"] == [{"sif": "SIF-100-03", "from": "PT-1001D", "to": "XV-1001"}]
    assert r["drawn"] == 10 and r["ce_pairs"] == 11
    disc, _ = _store()
    from pid_graph.records import MemoryStore  # noqa: F401
    graph = json.loads((FIXTURE.parent / "graph_discrepancies.json").read_text(encoding="utf-8"))
    base = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                       topology=DATA / "pid_audit_U100_topology.csv", pdf=DATA / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="t")[0]
    LP.apply(base, LP.reconcile(graph, LP.index_tags(base), base, unit="U-100", load_run="t"))
    d = TQ.drawing_vs_ce(base)
    assert [(x["from"], x["to"], x["via"]) for x in d["drawn_not_in_ce"]] == [("LT-1006", "XV-1002", "")]


# ---- T7 ------------------------------------------------------------------------------------------
def test_trusted_by_default_and_nothing_is_visible_until_accepted(store):
    for name, arg in CALLS:
        if name == "drawing_vs_ce":
            continue
        r = _call(store, name, arg)
        assert "trusted facts only" in r["basis"] and r["vision_facts_left_out"] == 152, name
    assert TQ.isolation(store, "PT-1001A")["taps"] == [] and "not placed" in TQ.isolation(store, "PT-1001A")["note"]
    assert TQ.same_pressure(store, "PT-1001A")["candidates"] == [] and TQ.blast_radius(store, "XV-1001")["downstream"] == []
    assert TQ.loop_membership(store, "PV-1005")["loops"] == []
    strict = TQ.drawing_vs_ce(store, include_pending=False)
    assert "trusted facts only" in strict["basis"] and strict["drawn"] == 0 and len(strict["ce_not_drawn"]) == 11


def test_exploration_says_so_in_the_header(store):
    for name, arg in CALLS:
        r = _call(store, name, arg, include_pending=True)
        assert r["basis"].startswith("EXPLORATION ONLY") and "pending" in r["basis"], name


def test_accepting_l101_makes_the_trusted_answer_equal_the_exploratory_one():
    _, res = _store()
    on_l101 = {x["props"]["fact_id"]: "accepted" for x in res["nodes"] + res["rels"]
               if "L-101." in json.dumps([x.get("key"), x.get("start_key"), x.get("end_key")])}
    accepted, _ = _store(review=on_l101)
    full = TQ.isolation(accepted, "PT-1001A", include_pending=True)
    safe = TQ.isolation(accepted, "PT-1001A")
    assert safe["upstream"] == full["upstream"] and safe["downstream"] == full["downstream"] and safe["taps"] == ["L-101.3"]
    assert safe["vision_facts_left_out"] < 152
    assert [c["device"] for c in TQ.same_pressure(accepted, "PT-1001A")["candidates"]] == ["FT-1004", "PI-1001", "PT-1001B", "PT-1001C"]
    assert TQ.blast_radius(accepted, "XV-1001")["ends_at"] == ["V-1002"] and TQ.isolation(accepted, "PT-1005")["taps"] == []


class _Recorder:
    """Stands in for a Neo4j driver: records every Cypher text, returns no rows."""

    def __init__(self):
        self.seen = []

    def session(self, **_):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def run(self, cypher, **params):
        self.seen.append(cypher)
        return []


def _patterns(cypher: str):
    for m in re.finditer(r"\[\s*(\w*)\s*:\s*([A-Za-z_|]+)\s*(\*[^\]]*)?\]", cypher):
        yield m.group(1), set(m.group(2).split("|")), bool(m.group(3))


def test_every_cypher_text_is_gated_in_trusted_mode_and_reads_only():
    rec = _Recorder()
    for name, arg in CALLS:
        _call(rec, name, arg) if name != "drawing_vs_ce" else TQ.drawing_vs_ce(rec, include_pending=False)
    rec2 = _Recorder()
    for prim in ("taps", "is_in_line", "kind_of", "terminal"):
        pass
    TQ.exercise_all_primitives(rec2, include_pending=False)                                     # so no primitive escapes the check
    texts = set(rec.seen) | set(rec2.seen)
    assert len(texts) >= 10
    checked = 0
    for cypher in texts:
        assert not re.search(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP)\b", cypher)
        for var, types, varlen in _patterns(cypher):
            if varlen:
                assert re.search(r"all\(\s*\w+ IN relationships\(\w+\) WHERE \(\w+\.extracted_by IN", cypher), cypher
                assert re.search(r"all\(\s*\w+ IN nodes\(\w+\) WHERE \(\w+\.extracted_by IN", cypher), cypher
                checked += 1
            elif types & VISION_WRITABLE:
                assert var and Q.trusted_rel(var) in cypher, f"[{var}:{types}] not gated in: {cypher}"
                checked += 1
    assert checked >= 8
    loose = _Recorder()
    TQ.exercise_all_primitives(loose, include_pending=True)
    assert not any("extracted_by IN" in c for c in loose.seen)                                  # exploration really is ungated


# ---- both backends agree ----------------------------------------------------------------------------
def _neo4j_with_vision():
    try:
        from pid_graph.db import DATABASE, get_driver
        d = get_driver()
        d.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")
    with d.session(database=DATABASE) as s:
        rows = [r.data() for r in s.run("MATCH (n) WHERE n.extracted_by = 'pidkg_vision' RETURN n.fact_id AS f, n.review AS r "
                                        "UNION ALL MATCH ()-[e]->() WHERE e.extracted_by = 'pidkg_vision' RETURN e.fact_id AS f, e.review AS r")]
    if not rows:
        d.close()
        pytest.skip("Neo4j holds no vision layer: load it with python -m pid_graph --backend neo4j --pidkg <graph.json>")
    return d, {r["f"]: r["r"] for r in rows}


def test_neo4j_and_memory_backends_agree_on_u100():
    d, in_db = _neo4j_with_vision()
    try:
        # Mirror the database: what it holds as accepted is accepted here; a fixture fact it does not hold was
        # rejected (or dropped with a rejected end) on its last load, so it is rejected here too.
        everything = {x["props"]["fact_id"] for x in _store()[1]["nodes"] + _store()[1]["rels"]}
        review = {f: "accepted" for f, r in in_db.items() if r == "accepted"}
        review.update({f: "rejected" for f in everything - set(in_db)})
        store, res = _store(review=review)
        mine = {x["props"]["fact_id"]: x["props"]["review"] for x in res["nodes"] + res["rels"]}
        if mine != in_db:
            pytest.skip("Neo4j holds a different vision extraction from the test fixture")
        for include in (False, True):
            for name, arg in CALLS:
                neo, mem = _call(d, name, arg, include_pending=include), _call(store, name, arg, include_pending=include)
                assert neo == mem, f"{name}({arg}, include_pending={include}) differs between Neo4j and memory"
    finally:
        d.close()
