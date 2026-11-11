"""v1.3 Phase 10 (PIDKG_UPGRADE.md): DEXPI class and the plant summary.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

dexpiClass is carried as a standalone, informative property. The summary is generated from the
governed graph under the T7 filter and says how many pending facts it left out.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import load_pidkg as LP  # noqa: E402
from pid_graph import summary as SM  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402

DATA = ROOT / "data"
FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
V12_DUMP = ROOT / "tests" / "fixtures" / "graph_U-100_v1_2.json"
DEXPI_PROPS = ("dexpiClass", "dexpiClass_source")


def _base():
    return build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                       srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                       curated=DATA / "curated" / "compensating_measures_U-100.csv", topology=DATA / "pid_audit_U100_topology.csv",
                       pdf=DATA / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="TX-0057-BASELINE")[0]


def _loaded(review=None, graph=None):
    store = _base()
    graph = graph or json.loads(FIXTURE.read_text(encoding="utf-8"))
    res = LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE", review=review)
    LP.apply(store, res)
    return store, res


@pytest.fixture(scope="module")
def loaded():
    return _loaded()


# ---- dexpiClass -----------------------------------------------------------------------
def test_dexpi_class_is_carried_onto_the_three_labels(loaded):
    store, res = loaded
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    theirs = {n.get("tag"): n.get("dexpi_class") for n in graph["nodes"] if n.get("tag")}
    for tag in ("PT-1001A", "XV-1001", "HV-1001", "PV-1005", "FT-1004"):
        p = store.get_node("Instrument", {"tag": tag})["props"]
        assert p["dexpiClass"] == theirs[tag] and p["dexpiClass_source"].startswith("pidkg_vision PID-100-00")
    assert store.get_node("Instrument", {"tag": "HV-1001"})["props"]["dexpiClass"] == "BallValve"
    assert store.get_node("Equipment", {"tag": "V-1002"})["props"]["dexpiClass"] == "Vessel"
    items = store.nodes("InlineItem")
    assert items and all(n["props"]["dexpiClass"] for n in items)
    assert {n["props"]["dexpiClass"] for n in items} >= {"CheckValve"}
    assert not any("dexpiClass" in n["props"] for n in store.nodes("Segment") + store.nodes("ControlLoop") + store.nodes("SIF") + store.nodes("Alarm"))


def test_only_nodes_vision_saw_get_a_class_and_nothing_else_about_them_changes(loaded):
    store, _ = loaded
    for tag in ("TT-1003", "PT-1001D", "FT-1006", "PSV-1001"):                # not drawn, C&E only, not in the index, LOPA only
        assert "dexpiClass" not in store.get_node("Instrument", {"tag": tag})["props"]
    bl = store.get_node("Equipment", {"tag": "BL-100"})["props"]             # a boundary mapped onto a stub: still a stub, no class
    assert bl["stub"] is True and "dexpiClass" not in bl and bl["extracted_by"] in ("pid_audit", "manual")
    strip = lambda n: {**n, "props": {k: v for k, v in n["props"].items() if k not in DEXPI_PROPS}}
    v12 = {"nodes": [strip(n) for n in store.nodes() if n["label"] not in ("Segment", "InlineItem", "ControlLoop")],
           "rels": [r for r in store.rels() if r["props"].get("extracted_by") != "pidkg_vision"], "conflicts": []}
    assert (json.dumps(v12, indent=1, default=str) + "\n").encode() == V12_DUMP.read_bytes().replace(b"\r\n", b"\n")
    pt = store.get_node("Instrument", {"tag": "PT-1001A"})["props"]
    assert pt["extracted_by"] == "table" and pt["source_doc"] == "U100-INST-INDEX"    # its own provenance is untouched


def test_class_is_informative_and_applying_twice_changes_nothing(loaded):
    store, res = loaded
    once = json.dumps(store.to_dict(), default=str)
    LP.apply(store, res)
    assert json.dumps(store.to_dict(), default=str) == once and store.conflicts == []
    from pid_graph import queries as Q, topology_queries as TQ
    src = "".join((ROOT / "pid_graph" / f).read_text(encoding="utf-8") for f in ("queries.py", "topology_queries.py", "report.py", "oos.py"))
    assert "dexpiClass" not in src and Q and TQ                              # no template or report reads it


def test_two_sheets_disagreeing_on_a_class_is_a_conflict_not_an_overwrite():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store, res = _loaded(graph=graph)
    again = copy.deepcopy(graph)
    next(n for n in again["nodes"] if n["id"] == "XV-1001")["dexpi_class"] = "GlobeValve"
    res2 = LP.reconcile(again, LP.index_tags(store), store, unit="U-100", load_run="TX-0057-BASELINE")
    LP.apply(store, res2)
    assert store.get_node("Instrument", {"tag": "XV-1001"})["props"]["dexpiClass"] != "GlobeValve"
    c = [x for x in store.conflicts if x.prop == "dexpiClass"]
    assert len(c) == 1 and c[0].key == {"tag": "XV-1001"} and c[0].incoming == "GlobeValve"
    LP.apply(store, res2)
    assert len([x for x in store.conflicts if x.prop == "dexpiClass"]) == 1   # recorded once


def test_nodes_seen_by_vision_with_no_class_are_listed():
    graph = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = _base()
    clean = LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="t")
    assert clean["no_dexpi_class"] == [] and clean["summary"]["dexpi_classes"] > 15
    for n in graph["nodes"]:
        if n["id"] in ("PT-1005", "P02.V2", "V-1002"):
            n.pop("dexpi_class", None)
    res = LP.reconcile(graph, LP.index_tags(store), store, unit="U-100", load_run="t")
    assert res["no_dexpi_class"] == ["Equipment V-1002", "InlineItem PID-100-001.V2", "Instrument PT-1005"]
    src = (ROOT / "pid_graph" / "validate.py").read_text(encoding="utf-8")
    assert "InlineItem) WHERE n.dexpiClass IS NULL" in src and "dexpiClass_source IS NOT NULL" in src


# ---- plant summary ----------------------------------------------------------------------
def test_summary_header_states_unit_revisions_and_pending_facts_left_out(loaded):
    store, res = loaded
    text = SM.build(store, "U-100")
    head = text.split("## 1.")[0]
    assert "# Plant summary — unit U-100" in head and "trusted facts only" in head
    assert f"**{len(res['nodes']) + len(res['rels'])} vision facts are pending or rejected and are left out**" in head
    for doc in ("PID-100-001 | D", "PID-100-002 | B", "PID-100-003 | A", "U100-INST-INDEX | B", "U100-CE-CHART | A", "U100-SRS-001 | B", "U100-LOPA-001 | A"):
        assert doc in head, doc
    assert "machine-generated" in head and "TX-0057-BASELINE" in head


def test_summary_sections(loaded):
    text = SM.build(loaded[0], "U-100")
    for title in ("## 1. Equipment-level flow", "## 2. Instruments and where they are", "## 3. Loops", "## 4. Safety instrumented functions", "## 5. Alarms",
                  "## 6. Open exceptions"):
        assert title in text, title
    assert "| BL-100 | L-101 | V-1002 |" in text and "| V-1002 | L-104 | FLARE-HDR |" in text
    assert "| PT-1001A | PT | Feed gas inlet pressure (SIS) - A | SIS | L-101 | PID-100-001 |" in text
    assert "| PIC-1005 | PT-1005, PV-1005 |" in text                           # loops per the index
    sif = next(ln for ln in text.splitlines() if ln.startswith("| SIF-100-01 |"))
    assert "PT-1001A, PT-1001B, PT-1001C" in sif and "2oo3" in sif and "68 barg" in sif and "XV-1001 (Close)" in sif and "BDV-1001 (Open)" in sif
    assert "PT-1005.PAH" in sif                                               # curated compensating measure
    assert "| PT-1001A.PAH | PAH-1001 | PT-1001A | 62 barg | High |" in text
    assert "TT-1003" in text and "PT-1001D" in text and "(stub)" in text       # C&E-only initiator is shown as a stub, not hidden


def test_pending_vision_facts_are_not_in_the_summary_until_accepted(loaded):
    store, res = loaded
    text = SM.build(store, "U-100")
    assert "L-101.3" not in text and "PID-100-001.V1" not in text and "P-1001" not in text
    assert "No segment-level flow has been accepted yet" in text and "No drawn loop has been accepted yet" in text
    on_l101 = {x["props"]["fact_id"]: "accepted" for x in res["nodes"] + res["rels"]
               if "L-101." in json.dumps([x.get("key"), x.get("start_key"), x.get("end_key")])}
    loop = {x["props"]["fact_id"]: "accepted" for x in res["nodes"] + res["rels"]
            if "P-1005" in json.dumps([x.get("key"), x.get("end_key")])}
    accepted, res2 = _loaded(review={**on_l101, **loop})
    text2 = SM.build(accepted, "U-100")
    left = sum(1 for x in res2["nodes"] + res2["rels"] if x["props"]["review"] != "accepted")
    assert f"**{left} vision facts are pending or rejected and are left out**" in text2 and left < len(res["nodes"]) + len(res["rels"])
    assert "| BL-100 | V-1002 | L-101 | HV-1001, XV-1001, FT-1004 |" in text2      # accepted segment-level flow
    assert "L-101, L-101.3" in text2 or "L-101.3, L-101" in text2                 # PT-1001A's location now names its segment
    assert "| P-1005 | control | pressure | PT-1005 (sensor), PV-1005 (final_element) |" in text2


def test_summary_without_the_vision_layer_is_plain_v12():
    text = SM.build(_base(), "U-100")
    assert "**0 vision facts are pending or rejected and are left out**" in text and "## 4. Safety instrumented functions" in text


def test_summary_is_deterministic_and_written_by_the_pipeline(tmp_path, loaded):
    assert SM.build(loaded[0], "U-100") == SM.build(_loaded()[0], "U-100")
    from pid_graph.run_all import main
    assert main(["--unit", "U-100", "--backend", "memory", "--pdf", str(DATA / "U100-PIDS-TX-0057.pdf"), "--transmittal", "TX-0057",
                 "--load-run", "TX-0057-BASELINE", "--pidkg", str(FIXTURE), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "summary_U-100.md").read_text(encoding="utf-8") == SM.build(loaded[0], "U-100")


def test_summary_from_neo4j_matches_memory():
    try:
        from pid_graph.db import DATABASE, get_driver
        from pid_graph.neo4j_store import Neo4jStore
        d = get_driver()
        d.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")
    try:
        neo = Neo4jStore(d, DATABASE)
        in_db = {n["props"].get("fact_id"): n["props"].get("review") for n in neo.nodes() + neo.rels() if n["props"].get("extracted_by") == "pidkg_vision"}
        if not in_db:
            pytest.skip("Neo4j holds no vision layer")
        everything = {x["props"]["fact_id"] for x in _loaded()[1]["nodes"] + _loaded()[1]["rels"]}
        review = {f: "accepted" for f, r in in_db.items() if r == "accepted"}
        review.update({f: "rejected" for f in everything - set(in_db)})
        store, res = _loaded(review=review)
        if {x["props"]["fact_id"]: x["props"]["review"] for x in res["nodes"] + res["rels"]} != in_db:
            pytest.skip("Neo4j holds a different vision extraction from the test fixture")
        runs = {n["props"].get("load_run") for n in neo.nodes("Instrument")}
        same = lambda t: "\n".join(ln for ln in t.splitlines() if not ln.startswith("Load run"))
        if not all("dexpiClass" in n["props"] for n in neo.nodes("InlineItem")):
            pytest.skip("Neo4j was loaded before Phase 10: reload it with python -m pid_graph --backend neo4j --pidkg <graph.json>")
        assert same(SM.build(neo, "U-100")) == same(SM.build(store, "U-100")) and runs
    finally:
        d.close()
