"""Cause & Effect chart -> SIF nodes and INITIATES / ACTUATES / PROTECTS / RAISES / CASCADES_TO edges.

Deterministic, no LLM. Provenance on every node and edge points at the C&E
document, sheet and cell.

  Instrument -INITIATES-> SIF          props: voting (per cause group), setpoint, cause_description
  SIF -ACTUATES-> Instrument           props: action (Close / Open / Trip ...)
  SIF -PROTECTS-> Equipment / Line
  SIF -RAISES-> Alarm                  v1.1: alarm effect columns; the Alarm is resolved by its register
                                       tag (PAHH-1001 -> PT-1001A.PAHH); if the register does not have
                                       it, a stub Alarm keyed by the bare tag is created and X9 reports it
  SIF -CASCADES_TO-> SIF               v1.1: effect columns whose tag is a SIF / ESD id
  SIF / Instrument -SHOWN_ON-> Document(CE)

The logic solver has no label; it is kept as SIF.logic_solver (D-P2-03).
C&E tags absent from the index become stub Instruments and X4 exceptions (D-P1-07).
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, classify, func_prefix, is_offpage, role
from .ce_table import ce_rows
from .tables import detect_document


def _prov(doc_no: str, rev: str, sheet: str, load_run: str, ref: str) -> dict:
    return {"source_doc": doc_no, "source_rev": rev, "source_sheet": sheet,
            "extracted_by": "table", "load_run": load_run, "source_ref": ref}


def load_ce(store: MemoryStore, path: str | Path, *, unit: str, load_run: str, sheet: str | None = None) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "rows": 0, "sifs": 0, "initiates": 0, "actuates": 0, "protects": 0, "raises": 0, "cascades": 0,
              "ce_only_instruments": [], "alarm_effects": [], "ce_only_alarms": [], "ce_only_sifs": [],
              "skipped": [], "notes": []}
    alarms_by_tag = {n["props"].get("alarm_tag"): n["key"]["alarm_id"] for n in store.nodes("Alarm") if n["props"].get("alarm_tag")}
    doc_key = {"doc_no": doc_no, "rev": rev}
    sheet_name = sheet or ""
    store.merge_node("Document", doc_key, {"doc_type": "CE", "title": f"Cause & effect chart {doc_no}", "unit": unit,
                                           "file": path.name, **_prov(doc_no, rev, sheet_name, load_run, path.name)})

    def ensure_instrument(tag: str, prov: dict) -> None:
        existing = store.get_node("Instrument", {"tag": tag})
        if existing is not None:
            store.merge_node("Instrument", {"tag": tag}, prov, stub=existing["props"].get("stub", False))
            return
        store.merge_node("Instrument", {"tag": tag}, {"type": func_prefix(tag), "role": role(tag), "unit": unit,
                                                      "stub_unit": unit, **prov}, stub=True)
        report["ce_only_instruments"].append({"tag": tag, "ref": prov["source_ref"]})

    rows = ce_rows(path, sheet)
    report["rows"] = len(rows)
    seen_sifs: set[str] = set()
    seen_alarm_effects: set[tuple] = set()
    for r in rows:
        ref = r["ref"]
        sif = canonical_id(r["sif_id"])
        if not sif:
            report["skipped"].append({"ref": ref, "reason": "row has no SIF id"})
            continue
        prov = _prov(doc_no, rev, sheet_name, load_run, ref)
        sif_key = {"sif_id": sif}
        store.merge_node("SIF", sif_key, {"description": r["sif_description"], "sil": r["sil"],
                                          "logic_solver": canonical_id(r["logic_solver"]), "voting": r["voting"],
                                          "unit": unit, **prov})
        if sif not in seen_sifs:
            seen_sifs.add(sif)
            report["sifs"] += 1
            store.merge_rel("SHOWN_ON", "SIF", sif_key, "Document", doc_key, prov)
            if r["protects"]:
                label, ident = classify(r["protects"])
                if label == "Instrument":
                    report["skipped"].append({"ref": ref, "reason": f"protected equipment {r['protects']!r} is an instrument tag"})
                else:
                    key = {"line_no": ident} if label == "Line" else {"tag": ident}
                    existing = store.get_node(label, key)
                    if existing is None:
                        store.merge_node(label, key, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
                        report["notes"].append(f"{label} {ident} named as protected equipment is not in the index or on a P&ID; created as stub")
                    else:
                        store.merge_node(label, key, prov, stub=existing["props"].get("stub", False))
                    store.merge_rel("PROTECTS", "SIF", sif_key, label, key, prov)
                    report["protects"] += 1

        cause = canonical_tag(r["cause_tag"])
        if not cause:
            report["skipped"].append({"ref": ref, "reason": f"cause tag {r['cause_tag']!r} is not tag-shaped"})
            continue
        ensure_instrument(cause, prov)
        before = len(store.rels("INITIATES"))
        store.merge_rel("INITIATES", "Instrument", {"tag": cause}, "SIF", sif_key,
                        {**prov, "voting": r["voting"], "setpoint": r["setpoint"], "cause_description": r["cause_description"]})
        report["initiates"] += len(store.rels("INITIATES")) - before
        store.merge_rel("SHOWN_ON", "Instrument", {"tag": cause}, "Document", doc_key, prov)

        if not r["effect_tag"]:
            continue
        effect_id = canonical_id(r["effect_tag"])
        if effect_id.startswith(("SIF-", "ESD-", "PSD-", "USD-")) or store.has_node("SIF", {"sif_id": effect_id}):
            # v1.1 CASCADES_TO: the effect is another safety function
            if not store.has_node("SIF", {"sif_id": effect_id}):
                store.merge_node("SIF", {"sif_id": effect_id}, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
                report["ce_only_sifs"].append({"sif_id": effect_id, "ref": ref})
            before = len(store.rels("CASCADES_TO"))
            store.merge_rel("CASCADES_TO", "SIF", sif_key, "SIF", {"sif_id": effect_id}, {**prov, "action": r["effect_action"]})
            report["cascades"] += len(store.rels("CASCADES_TO")) - before
            continue
        if role(r["effect_tag"]) == "alarm" or r["effect_action"].strip().lower() == "alarm":
            # v1.1 RAISES: resolve the register alarm by its own tag; stub if the register lacks it
            alarm_tag = canonical_tag(r["effect_tag"]) or effect_id
            key = (sif, alarm_tag)
            if key in seen_alarm_effects:
                continue
            seen_alarm_effects.add(key)
            alarm_id = alarms_by_tag.get(alarm_tag)
            if alarm_id is None:
                alarm_id = alarm_tag
                if not store.has_node("Alarm", {"alarm_id": alarm_id}):
                    store.merge_node("Alarm", {"alarm_id": alarm_id}, {"alarm_tag": alarm_tag, "alarm_type": func_prefix(alarm_tag),
                                                                     "unit": unit, "stub_unit": unit, **prov}, stub=True)
                    report["ce_only_alarms"].append({"alarm_tag": alarm_tag, "sif_id": sif, "ref": ref})
            report["alarm_effects"].append({"sif_id": sif, "alarm": alarm_tag, "alarm_id": alarm_id, "ref": ref,
                                            "in_register": alarm_tag in alarms_by_tag})
            before = len(store.rels("RAISES"))
            store.merge_rel("RAISES", "SIF", sif_key, "Alarm", {"alarm_id": alarm_id}, {**prov, "action": r["effect_action"]})
            report["raises"] += len(store.rels("RAISES")) - before
            store.merge_rel("SHOWN_ON", "Alarm", {"alarm_id": alarm_id}, "Document", doc_key, prov)
            continue
        effect = canonical_tag(r["effect_tag"])
        if not effect:
            report["skipped"].append({"ref": ref, "reason": f"effect tag {r['effect_tag']!r} is not tag-shaped"})
            continue
        ensure_instrument(effect, prov)
        before = len(store.rels("ACTUATES"))
        store.merge_rel("ACTUATES", "SIF", sif_key, "Instrument", {"tag": effect}, {**prov, "action": r["effect_action"]})
        report["actuates"] += len(store.rels("ACTUATES")) - before
        store.merge_rel("SHOWN_ON", "Instrument", {"tag": effect}, "Document", doc_key, prov)
    if report["ce_only_alarms"]:
        report["notes"].append(f"{len(report['ce_only_alarms'])} alarm effect(s) are not in the alarm register; stub Alarm nodes created (X9)")
    if report["ce_only_sifs"]:
        report["notes"].append(f"{len(report['ce_only_sifs'])} cascade target(s) are not defined in this C&E; stub SIF nodes created")
    return report
