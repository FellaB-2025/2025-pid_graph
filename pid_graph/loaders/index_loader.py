"""Instrument index (xlsx) -> Instrument nodes. The master node list (decisions section 2).

Deterministic, no LLM. Canonical tag normalisation, MERGE on tag, provenance on
every node and edge. Also loads the Alarm Register sheet of the same workbook when
present (Alarm nodes + GENERATES), because it is the same controlled document.

Edges written (ontology section 3):
  Instrument -MEASURES->     Line/Equipment   for sensors and local indicators
  Instrument -INSTALLED_ON-> Line/Equipment   for valves / final elements   (decision D-P1-05)
  Instrument -SHOWN_ON->     Document(index)  and Document(P&ID claimed by the index column)
  Instrument -GENERATES->    Alarm
  Alarm      -SHOWN_ON->     Document(index)
"""
from __future__ import annotations

from pathlib import Path

from .. import ontology as O
from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, classify, func_prefix, role
from .docs import pid_document
from .tables import ALARM_ALIASES, INDEX_ALIASES, detect_document, read_table, sheet_names


def _prov(doc_no: str, rev: str, sheet: str, load_run: str, ref: str) -> dict:
    return {"source_doc": doc_no, "source_rev": rev, "source_sheet": sheet,
            "extracted_by": "table", "load_run": load_run, "source_ref": ref}


def load_index(store: MemoryStore, path: str | Path, *, unit: str, load_run: str,
               sheet: str = "Instrument Index", alarm_sheet: str | None = "Alarm Register",
               rev_map: dict | None = None) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "rows": 0, "instruments": 0, "alarms": 0, "skipped": [], "notes": []}
    doc_key = {"doc_no": doc_no, "rev": rev}
    store.merge_node("Document", doc_key, {"doc_type": "IDX", "title": f"Instrument index {doc_no}",
                                           "unit": unit, "file": path.name,
                                           **_prov(doc_no, rev, sheet, load_run, f"{path.name}:{sheet}")})

    rows = read_table(path, sheet, INDEX_ALIASES)
    report["rows"] = len(rows)
    for r in rows:
        ref = f"{path.name}:{sheet}:{r['_row']}"
        tag = canonical_tag(r.get("tag"))
        if not tag:
            report["skipped"].append({"ref": ref, "value": r.get("tag", ""), "reason": "tag is empty or not tag-shaped"})
            continue
        row_unit = canonical_id(r.get("unit")) or unit
        prov = _prov(doc_no, rev, sheet, load_run, ref)
        store.merge_node("Instrument", {"tag": tag}, {
            "type": func_prefix(tag), "role": role(tag), "service": r.get("description", ""),
            "instrument_type": r.get("type", ""), "range": r.get("range", ""), "units": r.get("units", ""),
            "io_type": r.get("signal", ""), "system": r.get("layer", ""), "loop": r.get("loop", ""),
            "remarks": r.get("remarks", ""), "unit": row_unit, **prov})
        report["instruments"] += 1
        store.merge_rel("SHOWN_ON", "Instrument", {"tag": tag}, "Document", doc_key, prov)

        if r.get("pid_sheet"):
            # The index claims the tag is on this drawing. Real rev if the title-block pass has
            # registered it, else a rev-UNKNOWN stub.
            pid_key = pid_document(store, canonical_id(r["pid_sheet"]), rev_map=rev_map, unit=row_unit, prov=prov)
            store.merge_rel("SHOWN_ON", "Instrument", {"tag": tag}, "Document", pid_key, prov)

        loc = r.get("line") or r.get("equipment")
        if loc:
            label, ident = classify(loc)
            if label == "Instrument":
                report["skipped"].append({"ref": ref, "value": loc, "reason": "location column holds an instrument tag; no MEASURES/INSTALLED_ON written"})
            else:
                key = {"line_no": ident} if label == "Line" else {"tag": ident}
                store.merge_node(label, key, {"unit": row_unit, **prov})
                rel = "MEASURES" if role(tag) in ("sensor", "local_indicator") else "INSTALLED_ON"
                store.merge_rel(rel, "Instrument", {"tag": tag}, label, key, prov)

    if alarm_sheet and alarm_sheet in sheet_names(path):
        _load_alarm_register(store, path, alarm_sheet, doc_key, unit, load_run, report)
    elif alarm_sheet:
        report["notes"].append(f"no sheet named {alarm_sheet!r}; alarms not loaded")
    return report


def _load_alarm_register(store, path: Path, sheet: str, doc_key: dict, unit: str, load_run: str, report: dict) -> None:
    doc_no, rev = doc_key["doc_no"], doc_key["rev"]
    rows = read_table(path, sheet, ALARM_ALIASES)
    dropped_protects = 0
    for r in rows:
        ref = f"{path.name}:{sheet}:{r['_row']}"
        alarm_tag = canonical_tag(r.get("alarm_tag"))
        source = canonical_tag(r.get("sensor_tag"))
        if not alarm_tag:
            report["skipped"].append({"ref": ref, "value": r.get("alarm_tag", ""), "reason": "alarm tag empty or not tag-shaped"})
            continue
        if not source:
            report["skipped"].append({"ref": ref, "value": alarm_tag, "reason": "alarm has no source instrument tag"})
            continue
        if not store.has_node("Instrument", {"tag": source}):
            report["skipped"].append({"ref": ref, "value": alarm_tag, "reason": f"source tag {source} is not in the instrument index"})
            continue
        alarm_type = func_prefix(alarm_tag)
        alarm_id = f"{source}.{alarm_type}"
        prov = _prov(doc_no, rev, sheet, load_run, ref)
        store.merge_node("Alarm", {"alarm_id": alarm_id}, {
            "alarm_tag": alarm_tag, "alarm_type": alarm_type, "setpoint": r.get("setpoint", ""),
            "priority": r.get("priority", ""), "description": r.get("description", ""),
            "system": r.get("layer", ""), "unit": unit, **prov})
        store.merge_rel("GENERATES", "Instrument", {"tag": source}, "Alarm", {"alarm_id": alarm_id}, prov)
        store.merge_rel("SHOWN_ON", "Alarm", {"alarm_id": alarm_id}, "Document", doc_key, prov)
        report["alarms"] += 1
        if r.get("protects"):
            dropped_protects += 1
    if dropped_protects:
        report["notes"].append(f"{dropped_protects} alarm rows have a Protected Equipment value; "
                               "v1 has no Alarm->Equipment relationship, so it is not loaded")
