"""Curated compensating measures -> COMPENSATES_FOR edges (Alarm -> SIF).

Ontology section 3: COMPENSATES_FOR is engineering judgement, manually curated,
never LLM-extracted. This loader therefore writes an edge ONLY for rows whose
`status` is `approved` and whose `curated_by` names a person. Rows marked
`proposed` are reported and left out of the graph; rows marked `gap` document
why no measure exists and feed exception X14.

Register columns: sif_id, alarm_id, rank, basis, conditions, rationale, status,
curated_by, date. `basis` is one of independent_bpcs / shares_sif_sensor /
field_only / gap.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id

APPROVED = "approved"
BASES = ("independent_bpcs", "shares_sif_sensor", "field_only", "gap")


def load_curated(store: MemoryStore, path: str | Path, *, unit: str, load_run: str) -> dict:
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    approved = [r for r in rows if (r.get("status") or "").strip().lower() == APPROVED]
    rev = max((r.get("date") or "" for r in approved), default="") or "DRAFT"
    doc_no = canonical_id(path.stem)
    doc_key = {"doc_no": doc_no, "rev": rev}
    report = {"file": path.name, "document": doc_key, "rows": len(rows), "loaded": 0,
              "proposed": [], "gaps": [], "skipped": []}
    prov_doc = {"source_doc": doc_no, "source_rev": rev, "source_sheet": "", "extracted_by": "manual",
                "load_run": load_run, "source_ref": path.name}
    store.merge_node("Document", doc_key, {"doc_type": "CUR", "title": "Curated compensating measures", "unit": unit,
                                           "file": path.name, **prov_doc})
    for i, r in enumerate(rows, start=2):
        ref = f"{path.name}:{i}"
        sif = canonical_id(r.get("sif_id"))
        status = (r.get("status") or "").strip().lower()
        basis = (r.get("basis") or "").strip().lower()
        entry = {"sif_id": sif, "alarm_id": (r.get("alarm_id") or "").strip().upper(), "rank": r.get("rank", ""),
                 "basis": basis, "rationale": r.get("rationale", ""), "ref": ref}
        if not sif or not store.has_node("SIF", {"sif_id": sif}):
            report["skipped"].append({**entry, "reason": f"SIF {sif or '?'} not in graph"})
            continue
        if basis not in BASES:
            report["skipped"].append({**entry, "reason": f"basis {basis!r} not one of {BASES}"})
            continue
        if status == "gap" or basis == "gap":
            report["gaps"].append(entry)
            continue
        if status != APPROVED:
            report["proposed"].append(entry)
            continue
        who = (r.get("curated_by") or "").strip()
        if not who:
            report["skipped"].append({**entry, "reason": "approved row has no curated_by; not loaded"})
            continue
        alarm_id = entry["alarm_id"]
        if not store.has_node("Alarm", {"alarm_id": alarm_id}):
            report["skipped"].append({**entry, "reason": f"alarm {alarm_id} not in graph"})
            continue
        prov = {**prov_doc, "source_ref": ref}
        store.merge_rel("COMPENSATES_FOR", "Alarm", {"alarm_id": alarm_id}, "SIF", {"sif_id": sif},
                        {**prov, "rank": int(r["rank"]) if (r.get("rank") or "").strip().isdigit() else None,
                         "basis": basis, "conditions": r.get("conditions", ""), "rationale": r.get("rationale", ""),
                         "curated_by": who, "curated_on": r.get("date", "")})
        store.merge_rel("SHOWN_ON", "SIF", {"sif_id": sif}, "Document", doc_key, prov)
        report["loaded"] += 1
    return report
