"""Safety Requirements Specification register -> requirements on SIF nodes (ontology v1.2, CQ12/CQ13).

One row per SIF. The C&E's own `sil` and INITIATES setpoints are left untouched; the SRS
values land in source-named properties (`sil_srs`, `setpoint_srs`, ...) so both documents'
claims sit side by side and reconcile compares them (X15 SIL, X16 setpoint, X20 architecture).
A SIF the SRS defines that the C&E does not is created as a stub and reported (X19).
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, classify
from .tables import SRS_ALIASES, detect_document, read_table

SRS_PROPS = ("functional_description", "hazard", "rrf_target", "pfd_target", "demand_mode", "safe_state", "process_safety_time",
             "response_time", "setpoint_srs", "sensor_architecture", "fe_architecture", "proof_test_interval",
             "bypass_conditions", "manual_shutdown", "reset", "logic_solver_srs", "sil_srs")


def load_srs(store: MemoryStore, path: str | Path, *, unit: str, load_run: str, sheet: str | None = None) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "rows": 0, "sifs": 0, "srs_only_sifs": [], "protects": 0, "skipped": [], "notes": []}
    doc_key = {"doc_no": doc_no, "rev": rev}
    prov_doc = {"source_doc": doc_no, "source_rev": rev, "source_sheet": sheet or "", "extracted_by": "table",
                "load_run": load_run, "source_ref": path.name}
    store.merge_node("Document", doc_key, {"doc_type": "SRS", "title": f"Safety requirements specification {doc_no}", "unit": unit,
                                           "file": path.name, **prov_doc})
    rows = read_table(path, sheet, SRS_ALIASES)
    report["rows"] = len(rows)
    for r in rows:
        ref = f"{path.name}:{sheet or 1}:{r['_row']}"
        sif = canonical_id(r.get("sif_id"))
        if not sif:
            report["skipped"].append({"ref": ref, "reason": "row has no SIF id"})
            continue
        prov = {**prov_doc, "source_ref": ref}
        key = {"sif_id": sif}
        existing = store.get_node("SIF", key)
        props = {"functional_description": r.get("functional_description", ""), "hazard": r.get("hazard", ""),
                 "sil_srs": r.get("sil", ""), "rrf_target": r.get("rrf", ""), "pfd_target": r.get("pfd", ""),
                 "demand_mode": r.get("demand_mode", ""), "safe_state": r.get("safe_state", ""),
                 "process_safety_time": r.get("process_safety_time", ""), "response_time": r.get("response_time", ""),
                 "setpoint_srs": r.get("setpoint", ""), "sensor_architecture": r.get("sensor_architecture", ""),
                 "fe_architecture": r.get("fe_architecture", ""), "proof_test_interval": r.get("proof_test_interval", ""),
                 "bypass_conditions": r.get("bypass_conditions", ""), "manual_shutdown": r.get("manual_shutdown", ""),
                 "reset": r.get("reset", ""), "logic_solver_srs": canonical_id(r.get("logic_solver", "")),
                 "srs_ref": ref}
        if existing is None:
            store.merge_node("SIF", key, {"description": r.get("functional_description", ""), "unit": unit, "stub_unit": unit,
                                          **props, **prov}, stub=True)
            report["srs_only_sifs"].append({"sif_id": sif, "ref": ref})
        else:
            store.merge_node("SIF", key, {**props, **prov}, stub=existing["props"].get("stub", False))
        store.merge_rel("SHOWN_ON", "SIF", key, "Document", doc_key, prov)
        report["sifs"] += 1
        if r.get("protects"):
            label, ident = classify(r["protects"])
            if label != "Instrument":
                pk = {"line_no": ident} if label == "Line" else {"tag": ident}
                ex = store.get_node(label, pk)
                if ex is None:
                    store.merge_node(label, pk, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
                else:
                    store.merge_node(label, pk, prov, stub=ex["props"].get("stub", False))
                store.merge_rel("PROTECTS", "SIF", key, label, pk, prov)     # second witness (SRS) beside the C&E's
                report["protects"] += 1
    if report["srs_only_sifs"]:
        report["notes"].append(f"{len(report['srs_only_sifs'])} SIF(s) defined in the SRS but absent from the C&E; stub SIF nodes created (X19)")
    return report
