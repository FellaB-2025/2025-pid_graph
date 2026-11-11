"""Phase 2 tests: C&E table + loader, title-block pass, change detection, query templates."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import ontology as O  # noqa: E402
from pid_graph.loaders.ce_table import ce_rows  # noqa: E402
from pid_graph.loaders.docs import pid_document  # noqa: E402
from pid_graph.loaders.titleblock import diff_against_store, read_title_blocks, rev_map  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.records import MemoryStore  # noqa: E402
from pid_graph.reconcile import reconcile  # noqa: E402

DATA = ROOT / "data"
CE = DATA / "U100-CE-CHART-Rev-A.xlsx"
PDF1, PDF2 = DATA / "U100-PIDS-TX-0042.pdf", DATA / "U100-PIDS-TX-0057.pdf"
PROV = {"source_doc": "DOC-1", "source_rev": "A", "source_sheet": "", "extracted_by": "table", "load_run": "t", "source_ref": "x"}


# ---- C&E ----------------------------------------------------------------------
def test_ce_matrix_to_rows():
    rows = ce_rows(CE, "CE-100")
    assert len(rows) == 14
    triples = {(r["sif_id"], r["cause_tag"], r["effect_tag"], r["effect_action"]) for r in rows}
    assert ("SIF-100-01", "PT-1001A", "XV-1001", "Close") in triples
    assert ("SIF-100-01", "PT-1001A", "BDV-1001", "Open") in triples
    assert ("SIF-100-01", "PT-1001A", "PAHH-1001", "Alarm") in triples
    assert ("SIF-100-03", "PT-1001D", "XV-1001", "Close") in triples
    # SIF-level cells carried down merged-cell style
    sif2 = [r for r in rows if r["cause_tag"] == "LT-1002B"][0]
    assert sif2["sif_id"] == "SIF-100-02" and sif2["sil"] == "1" and sif2["protects"] == "V-1002" and sif2["voting"] == "2oo3"
    assert all(r["ref"].startswith("U100-CE-CHART-Rev-A.xlsx:CE-100:R") for r in rows)


def test_ce_loader_edges_and_reports():
    store, rep = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=CE, topology=None, load_run="t")
    cr = rep["ce"]
    assert cr["document"] == {"doc_no": "U100-CE-CHART", "rev": "A", "detected_from": "title row of sheet 1"}
    assert cr["sifs"] == 3 and cr["initiates"] == 6 and cr["actuates"] == 5 and cr["protects"] == 3
    assert [x["tag"] for x in cr["ce_only_instruments"]] == ["PT-1001D"]
    assert [(x["sif_id"], x["alarm"], x["in_register"]) for x in cr["alarm_effects"]] == [("SIF-100-01", "PAHH-1001", False)]
    assert cr["raises"] == 1 and cr["cascades"] == 0
    raised = store.rels("RAISES")[0]
    assert raised["start_key"] == {"sif_id": "SIF-100-01"} and raised["end_key"] == {"alarm_id": "PAHH-1001"}
    assert store.get_node("Alarm", {"alarm_id": "PAHH-1001"})["props"]["stub"] is True
    ini = {(r["start_key"]["tag"], r["end_key"]["sif_id"], r["props"]["voting"]) for r in store.rels("INITIATES")}
    assert ("PT-1001A", "SIF-100-01", "2oo3") in ini and ("PT-1001D", "SIF-100-03", "1oo1") in ini
    act = {(r["start_key"]["sif_id"], r["end_key"]["tag"], r["props"]["action"]) for r in store.rels("ACTUATES")}
    assert ("SIF-100-01", "BDV-1001", "Open") in act and ("SIF-100-02", "XV-1002", "Close") in act
    assert store.get_node("Instrument", {"tag": "PT-1001D"})["props"]["stub"] is True
    assert store.get_node("SIF", {"sif_id": "SIF-100-01"})["props"]["logic_solver"] == "SIS-LS-100"


# ---- title blocks ---------------------------------------------------------------
@pytest.mark.skipif(not PDF1.exists(), reason="run scripts/make_dummy_pdf.py first")
def test_title_block_reader_and_rev_map():
    recs = read_title_blocks(PDF1)
    assert [r["page"] for r in recs] == [1, 2, 3, 4]
    assert recs[0]["doc_no"] is None and recs[0]["has_text_layer"]            # transmittal cover page
    assert (recs[1]["doc_no"], recs[1]["rev"], recs[1]["sheet"], recs[1]["of"]) == ("PID-100-001", "C", 1, 1)
    assert recs[1]["title"].startswith("FEED GAS INLET")
    revs, problems = rev_map(recs)
    assert revs == {"PID-100-001": "C", "PID-100-002": "B", "PID-100-003": "A"}
    assert len(problems) == 1 and problems[0]["page"] == 1


@pytest.mark.skipif(not (PDF1.exists() and PDF2.exists()), reason="run scripts/make_dummy_pdf.py (and --reissue) first")
def test_reissue_diff_detects_revised_drawing_only():
    store, _ = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", topology=DATA / "pid_audit_U100_topology.csv",
                           load_run="t", pdf=PDF1, transmittal="TX-0042")
    revs2, _ = rev_map(read_title_blocks(PDF2))
    d = diff_against_store(revs2, store)
    assert d["revised"] == [{"doc_no": "PID-100-001", "from": ["C"], "to": "D"}]
    assert [x["doc_no"] for x in d["unchanged"]] == ["PID-100-002", "PID-100-003"]
    assert d["new"] == [] and d["re_extract"] == ["PID-100-001"]


@pytest.mark.skipif(not PDF1.exists(), reason="run scripts/make_dummy_pdf.py first")
def test_pdf_removes_unknown_revisions_and_flags_unextracted_drawing():
    store, rep = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=CE,
                             topology=DATA / "pid_audit_U100_topology.csv", load_run="t", pdf=PDF1, transmittal="TX-0042")
    docs = {(d["key"]["doc_no"], d["key"]["rev"]): d["props"] for d in store.nodes("Document")}
    assert ("PID-100-001", "C") in docs and not docs[("PID-100-001", "C")]["stub"]
    assert not any(rev == O.UNKNOWN_REV for _, rev in docs)
    rec = reconcile(store, unit="U-100", ce_report=rep["ce"], titleblock_report=rep["titleblock"])
    codes = {(e["code"], e["id"]) for e in rec["exceptions"]}
    assert not any(c == "X7" for c, _ in codes)
    assert ("X12", "PID-100-003 rev A") in codes
    assert ("X13", "U100-PIDS-TX-0042.pdf page 1") in codes


def test_pid_document_uses_rev_map_or_stub():
    s = MemoryStore()
    k = pid_document(s, "PID-9", rev_map={"PID-9": "B"}, unit="U-1", prov=PROV)
    assert k == {"doc_no": "PID-9", "rev": "B"} and s.get_node("Document", k)["props"]["stub"] is False
    k2 = pid_document(s, "PID-8", rev_map={"PID-9": "B"}, unit="U-1", prov=PROV)
    assert k2["rev"] == O.UNKNOWN_REV and s.get_node("Document", k2)["props"]["stub"] is True


# ---- query templates (need a live Neo4j with U-100 loaded) --------------------------
def _driver_or_skip():
    try:
        from pid_graph.db import get_driver
        d = get_driver()
        d.verify_connectivity()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")


def test_query_templates_against_neo4j():
    from pid_graph import queries as Q
    d = _driver_or_skip()
    try:
        r = Q.out_of_service(d, "PT-1001A")
        assert r["as_initiator"][0]["sif"] == "SIF-100-01" and r["as_initiator"][0]["status"] == "DEGRADED"
        assert set(r["as_initiator"][0]["remaining_initiators"]) == {"PT-1001B", "PT-1001C"}
        assert [a["alarm"] for a in r["own_alarms_lost"]] == ["PT-1001A.PAH"]
        devices = {c["device"]: c for c in r["candidate_compensation"]}
        assert "PT-1005" in devices and devices["PT-1005"]["alarms"]      # BPCS alarm two hops away
        assert "PT-1001B" not in devices                                  # SIS sibling excluded
        r2 = Q.out_of_service(d, "XV-1001")
        assert {x["sif"]: x["status"] for x in r2["as_final_element"]}["SIF-100-03"].startswith("DEFEATED")
        t = Q.trip(d, "SIF-100-02")
        assert t["voting_check"] == [{"voting": "2oo3", "listed": 2, "expected": 3}]
        s = Q.shelve_impact(d, "PT-1001A.PAH")
        assert s["sifs_on_same_sensor"] == ["SIF-100-01"]
        m = Q.moc_impact(d, "L-101", hops=1)
        assert m["affected"] >= 8
    finally:
        d.close()


# ---- curated compensating measures ------------------------------------------------
def test_curated_loader_loads_only_approved_rows(tmp_path):
    import csv
    from pid_graph.loaders.curated_loader import load_curated
    store, rep = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=CE, topology=None, load_run="t")
    reg = tmp_path / "compensating_measures_U-100.csv"
    cols = ["sif_id", "alarm_id", "rank", "basis", "conditions", "rationale", "status", "curated_by", "date"]
    with reg.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow({"sif_id": "SIF-100-01", "alarm_id": "PT-1005.PAH", "rank": "1", "basis": "independent_bpcs",
                    "conditions": "c", "rationale": "r", "status": "approved", "curated_by": "AB", "date": "2026-09-09"})
        w.writerow({"sif_id": "SIF-100-01", "alarm_id": "PT-1001A.PAH", "rank": "2", "basis": "shares_sif_sensor",
                    "conditions": "", "rationale": "r", "status": "proposed", "curated_by": "", "date": ""})
        w.writerow({"sif_id": "SIF-100-02", "alarm_id": "LT-1006.LAH", "rank": "1", "basis": "independent_bpcs",
                    "conditions": "", "rationale": "r", "status": "approved", "curated_by": "", "date": ""})   # no name -> skipped
        w.writerow({"sif_id": "SIF-100-03", "alarm_id": "", "rank": "", "basis": "gap",
                    "conditions": "", "rationale": "no low alarm", "status": "gap", "curated_by": "", "date": ""})
    ur = load_curated(store, reg, unit="U-100", load_run="t")
    assert ur["loaded"] == 1 and len(ur["proposed"]) == 1 and len(ur["gaps"]) == 1 and len(ur["skipped"]) == 1
    edges = store.rels("COMPENSATES_FOR")
    assert len(edges) == 1
    e = edges[0]
    assert e["start_key"] == {"alarm_id": "PT-1005.PAH"} and e["end_key"] == {"sif_id": "SIF-100-01"}
    assert e["props"]["extracted_by"] == "manual" and e["props"]["curated_by"] == "AB" and e["props"]["rank"] == 1
    rec = reconcile(store, unit="U-100", ce_report=rep["ce"], curated_report=ur)
    x14 = {e["id"]: e["detail"] for e in rec["exceptions"] if e["code"] == "X14"}
    assert set(x14) == {"SIF-100-02", "SIF-100-03"}
    assert x14["SIF-100-03"].startswith("Curation records a GAP")


def test_u100_register_approved_by_engineer():
    """Approved by AB on 2026-09-09: three edges, one recorded gap, every edge names the curator."""
    from pid_graph.loaders.curated_loader import load_curated
    store, _ = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=CE, topology=None, load_run="t")
    ur = load_curated(store, DATA / "curated" / "compensating_measures_U-100.csv", unit="U-100", load_run="t")
    assert ur["loaded"] == 3 and ur["proposed"] == [] and ur["skipped"] == []
    edges = {(r["start_key"]["alarm_id"], r["end_key"]["sif_id"]): r["props"] for r in store.rels("COMPENSATES_FOR")}
    assert set(edges) == {("PT-1005.PAH", "SIF-100-01"), ("PT-1001A.PAH", "SIF-100-01"), ("LT-1006.LAH", "SIF-100-02")}
    assert all(p["curated_by"] == "AB" and p["extracted_by"] == "manual" for p in edges.values())
    assert edges[("PT-1001A.PAH", "SIF-100-01")]["basis"] == "shares_sif_sensor"
    assert [g["sif_id"] for g in ur["gaps"]] == ["SIF-100-03"]


def test_curated_alarm_from_bypassed_sensor_is_flagged_invalid():
    from pid_graph import queries as Q
    d = _driver_or_skip()
    try:
        r = Q.out_of_service(d, "PT-1001A")
        cur = {c["alarm"]: c for c in r["as_initiator"][0]["curated_compensating_alarms"]}
        assert cur["PT-1005.PAH"]["validity"] == "valid" and cur["PT-1005.PAH"]["rank"] == 1
        assert cur["PT-1001A.PAH"]["validity"].startswith("INVALID NOW")
        r2 = Q.out_of_service(d, "PT-1001B")
        cur2 = {c["alarm"]: c["validity"] for c in r2["as_initiator"][0]["curated_compensating_alarms"]}
        assert cur2["PT-1001A.PAH"] == "valid"
    finally:
        d.close()


# ---- v1.1: RAISES resolves to the register alarm when it exists; CASCADES_TO from SIF effects ------
def test_v11_raises_resolves_register_alarm_and_cascade(tmp_path):
    import csv
    from pid_graph.loaders.ce_loader import load_ce
    store, _ = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=None, topology=None, load_run="t")
    ce = tmp_path / "U200-CE-CHART-Rev-A.csv"
    cols = ["sif_id", "sif_description", "sil", "logic_solver", "cause_tag", "voting", "setpoint", "effect_tag", "effect_action", "protects"]
    with ce.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow({"sif_id": "SIF-100-09", "sif_description": "test", "sil": "1", "logic_solver": "SIS-LS-100", "cause_tag": "PT-1005",
                    "voting": "1oo1", "setpoint": "70 barg", "effect_tag": "PAH-1005", "effect_action": "Alarm", "protects": "V-1002"})
        w.writerow({"sif_id": "SIF-100-09", "sif_description": "", "sil": "", "logic_solver": "", "cause_tag": "PT-1005",
                    "voting": "1oo1", "setpoint": "70 barg", "effect_tag": "ESD-1", "effect_action": "Trip", "protects": ""})
    rep = load_ce(store, ce, unit="U-100", load_run="t")
    assert rep["raises"] == 1 and rep["cascades"] == 1
    r = store.rels("RAISES")[0]
    assert r["end_key"] == {"alarm_id": "PT-1005.PAH"}                     # resolved via the register's alarm_tag PAH-1005
    assert rep["alarm_effects"][0]["in_register"] is True and rep["ce_only_alarms"] == []
    c = store.rels("CASCADES_TO")[0]
    assert c["start_key"] == {"sif_id": "SIF-100-09"} and c["end_key"] == {"sif_id": "ESD-1"}
    assert store.get_node("SIF", {"sif_id": "ESD-1"})["props"]["stub"] is True
    assert rep["ce_only_sifs"] == [{"sif_id": "ESD-1", "ref": rep["ce_only_sifs"][0]["ref"]}]
