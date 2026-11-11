"""Phase 4 (ontology v1.2): SRS and LOPA loaders and the consistency checks X15-X20."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.reconcile import reconcile  # noqa: E402

DATA = ROOT / "data"


def _build():
    return build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                       srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                       curated=DATA / "curated" / "compensating_measures_U-100.csv",
                       topology=DATA / "pid_audit_U100_topology.csv", load_run="t")


def test_srs_requirements_land_on_sif_nodes():
    store, rep = _build()
    assert rep["srs"]["sifs"] == 3 and rep["srs"]["srs_only_sifs"] == []
    s1 = store.get_node("SIF", {"sif_id": "SIF-100-01"})["props"]
    assert s1["sil"] == "2" and s1["sil_srs"] == "2" and s1["setpoint_srs"] == "65 barg"
    assert s1["safe_state"].startswith("XV-1001 closed") and s1["process_safety_time"] == "120 s" and s1["proof_test_interval"] == "12 months"
    # the C&E's own claims are untouched
    assert {r["props"]["setpoint"] for r in store.rels("INITIATES") if r["end_key"]["sif_id"] == "SIF-100-01"} == {"68 barg"}
    # PROTECTS now has two witnesses per SIF (C&E and SRS)
    assert len([r for r in store.rels("PROTECTS") if r["start_key"]["sif_id"] == "SIF-100-01"]) == 2


def test_lopa_scenarios_and_credits():
    store, rep = _build()
    lr = rep["lopa"]
    assert lr["scenarios"] == 3 and lr["threatens"] == 3 and lr["credits"] == 6
    assert [(x["kind"], x["id"]) for x in lr["lopa_only"]] == [("Instrument", "PSV-1001")]
    assert lr["unrepresentable"] == []
    assert any(s["reason"].startswith("PIC-1005") for s in lr["skipped"])          # listed without PFD -> not credited
    credits = {(r["start_key"]["scenario_id"], r["end_label"], list(r["end_key"].values())[0]): r["props"] for r in store.rels("CREDITS")}
    assert credits[("S-100-01", "Alarm", "PT-1001A.PAH")]["pfd"] == 0.1              # PAH-1001 resolved via alarm_tag
    assert credits[("S-100-01", "SIF", "SIF-100-01")]["required_sil"] == "2" and credits[("S-100-01", "SIF", "SIF-100-01")]["pfd"] == 0.005
    assert credits[("S-100-02", "SIF", "SIF-100-02")]["required_sil"] == "2"
    assert store.get_node("Instrument", {"tag": "PSV-1001"})["props"]["stub"] is True
    assert store.get_node("Scenario", {"scenario_id": "S-100-01"})["props"]["initiating_event"].startswith("PIC-1005")


def test_consistency_checks_catch_the_planted_discrepancies():
    store, rep = _build()
    rec = reconcile(store, unit="U-100", ce_report=rep["ce"], curated_report=rep["curated"], lopa_report=rep["lopa"])
    codes = {(e["code"], e["id"]): e["detail"] for e in rec["exceptions"]}
    assert "LOPA says SIL 2" in codes[("X15", "SIF-100-02")] and "C&E says SIL 1" in codes[("X15", "SIF-100-02")]
    assert ("X15", "SIF-100-01") not in codes and ("X15", "SIF-100-03") not in codes
    assert "65 barg" in codes[("X16", "SIF-100-01")] and "68 barg" in codes[("X16", "SIF-100-01")]
    assert "derives from PT-1001A, which initiates SIF-100-01" in codes[("X17", "PT-1001A.PAH")]
    assert "not defined in any loaded register" in codes[("X18", "PSV-1001")]
    assert not any(c == "X19" for c, _ in codes) and not any(c == "X20" for c, _ in codes)
