"""Phase 1 unit tests. Run: .venv\\Scripts\\python -m pytest -q"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import ontology as O  # noqa: E402
from pid_graph.records import MemoryStore  # noqa: E402
from pid_graph.tags import canonical_tag, classify, is_offpage, role  # noqa: E402
from pid_graph.neo4j_store import _key_pattern  # noqa: E402

PROV = {"source_doc": "DOC-1", "source_rev": "A", "source_sheet": "", "extracted_by": "table", "load_run": "t"}


# ---- tags -------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("PT-1001A", "PT-1001A"), ("pt 1001a", "PT-1001A"), ("PT1001A", "PT-1001A"), ("100-PT-1001A", "100-PT-1001A"),
    ("PT--1001", "PT-1001"), ("L-101", "L-101"), ("V-1002", "V-1002"), ("BL-100", "BL-100"),
    ("FLARE-HDR", None), ("", None), (None, None), ("SIF-100-01", None),
])
def test_canonical_tag(raw, expected):
    assert canonical_tag(raw) == expected


@pytest.mark.parametrize("raw,label", [
    ("PT-1001A", "Instrument"), ("XV-1001", "Instrument"), ("HV-1001", "Instrument"), ("LG-1002", "Instrument"),
    ("L-101", "Line"), ("V-1002", "Equipment"), ("BL-100", "Equipment"), ("FLARE-HDR", "Equipment"),
])
def test_classify(raw, label):
    assert classify(raw)[0] == label


def test_roles_and_offpage():
    assert role("PT-1001A") == "sensor"
    assert role("XV-1001") == "final_element"
    assert role("PI-1001") == "local_indicator"
    assert is_offpage("BL-100") and is_offpage("FLARE-HDR") and not is_offpage("V-1002")


# ---- closed schema ----------------------------------------------------------
def test_store_rejects_unknown_label_and_relationship():
    s = MemoryStore()
    with pytest.raises(O.SchemaViolation):
        s.merge_node("Loop", {"tag": "PIC-1005"}, PROV)
    s.merge_node("Instrument", {"tag": "PT-1"}, PROV)
    s.merge_node("SIF", {"sif_id": "SIF-1"}, PROV)
    with pytest.raises(O.SchemaViolation):
        s.merge_rel("TRIPS", "SIF", {"sif_id": "SIF-1"}, "Instrument", {"tag": "PT-1"}, PROV)
    with pytest.raises(O.SchemaViolation):        # wrong direction
        s.merge_rel("INITIATES", "SIF", {"sif_id": "SIF-1"}, "Instrument", {"tag": "PT-1"}, PROV)
    s.merge_rel("INITIATES", "Instrument", {"tag": "PT-1"}, "SIF", {"sif_id": "SIF-1"}, PROV)


def test_store_requires_provenance():
    s = MemoryStore()
    with pytest.raises(O.SchemaViolation):
        s.merge_node("Instrument", {"tag": "PT-1"}, {"source_doc": "X"})
    with pytest.raises(O.SchemaViolation):
        s.merge_node("Instrument", {"tag": "PT-1"}, {**PROV, "extracted_by": "guess"})


# ---- merge semantics --------------------------------------------------------
def test_stub_is_filled_by_real_source_and_conflicts_are_kept():
    s = MemoryStore()
    s.merge_node("Instrument", {"tag": "PT-1"}, {**PROV, "source_doc": "PID-1", "extracted_by": "pid_audit"}, stub=True)
    assert s.get_node("Instrument", {"tag": "PT-1"})["props"]["stub"] is True
    s.merge_node("Instrument", {"tag": "PT-1"}, {**PROV, "range": "0-100", "source_ref": "idx:5"})
    n = s.get_node("Instrument", {"tag": "PT-1"})["props"]
    assert n["stub"] is False and n["source_doc"] == "DOC-1" and n["extracted_by"] == "table"
    s.merge_node("Instrument", {"tag": "PT-1"}, {**PROV, "source_doc": "CE-1", "range": "0-150", "source_ref": "ce:9"})
    assert n["range"] == "0-100"                       # first fact kept ...
    assert len(s.conflicts) == 1 and s.conflicts[0].prop == "range"   # ... and the disagreement recorded
    # source_ref differences are provenance, never conflicts
    assert all(c.prop != "source_ref" for c in s.conflicts)


def test_edge_identity_includes_source_document():
    s = MemoryStore()
    s.merge_node("Instrument", {"tag": "XV-1"}, PROV)
    s.merge_node("Line", {"line_no": "L-1"}, PROV)
    s.merge_rel("INSTALLED_ON", "Instrument", {"tag": "XV-1"}, "Line", {"line_no": "L-1"}, PROV)
    s.merge_rel("INSTALLED_ON", "Instrument", {"tag": "XV-1"}, "Line", {"line_no": "L-1"}, PROV)   # same witness -> merged
    s.merge_rel("INSTALLED_ON", "Instrument", {"tag": "XV-1"}, "Line", {"line_no": "L-1"},
                {**PROV, "source_doc": "PID-1", "extracted_by": "pid_audit"})                       # second witness -> new edge
    assert len(s.rels("INSTALLED_ON")) == 2


# ---- Cypher generation ------------------------------------------------------
def test_cypher_key_patterns():
    assert _key_pattern("Instrument") == "{tag: r.key.tag}"
    assert _key_pattern("Document", "r.ek") == "{doc_no: r.ek.doc_no, rev: r.ek.rev}"


# ---- end to end on the dummy unit ----------------------------------------------
def test_dummy_unit_end_to_end(tmp_path):
    from pid_graph.pipeline import build_store
    from pid_graph.reconcile import reconcile
    from eval.score import score
    store, rep = build_store(unit="U-100", index=ROOT / "data" / "U100-INST-INDEX-Rev-B.xlsx",
                             ce=ROOT / "data" / "U100-CE-CHART-Rev-A.xlsx",
                             topology=ROOT / "data" / "pid_audit_U100_topology.csv", load_run="test")
    c = store.counts()
    assert c["by_label"] == {"Alarm": 5, "Document": 4, "Equipment": 5, "Instrument": 19, "Line": 5, "SIF": 3}
    assert c["by_rel"]["INITIATES"] == 6 and c["by_rel"]["ACTUATES"] == 5 and c["by_rel"]["PROTECTS"] == 3
    assert c["by_rel"]["RAISES"] == 1 and "CASCADES_TO" not in c["by_rel"]           # v1.1
    assert not store.conflicts
    rec = reconcile(store, unit="U-100", ce_report=rep["ce"])
    codes = {(e["code"], e["id"]) for e in rec["exceptions"]}
    # every discrepancy planted in the dummy documents is caught
    assert ("X1", "TT-1003") in codes            # index tag missing from the P&ID extraction
    assert ("X2", "FT-1006") in codes            # P&ID tag missing from the index
    assert ("X3", "XV-1002") in codes            # sheet mismatch
    assert ("X4", "PT-1001D") in codes           # C&E cause not in index
    assert ("X9", "PAHH-1001") in codes          # C&E alarm effect PAHH-1001 not in the alarm register (stub)
    assert ("X10", "SIF-100-02") in codes        # 2oo3 with two initiators
    assert ("X11", "PT-1001A.PAH") in codes      # alarm shares its sensor with SIF-100-01
    assert rec["summary"]["index_coverage_pct"] == 94.1
    gold = json.loads((ROOT / "eval" / "gold_PID-100-001.json").read_text(encoding="utf-8"))
    ev = score(store, gold)
    assert ev["nodes"]["precision"] == 1.0 and ev["edges"]["precision"] == 1.0
    assert ev["nodes"]["missed"] == ["Instrument TT-1003"]
