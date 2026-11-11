"""LOPA report register -> Scenario nodes, THREATENS and CREDITS edges (ontology v1.2, CQ11/CQ12).

Two sheets: Scenarios (one row per hazard scenario, incl. the SIF it requires and the
RRF / SIL demanded of it) and IPLs (one row per credited layer per scenario).

Credited layers resolve to existing nodes:
  * SIF ids            -> SIF (stub if the C&E / SRS do not define it)
  * alarm-shaped tags  -> Alarm, by the register's alarm_tag (stub Alarm keyed by the bare tag if absent)
  * other tags         -> Instrument (stub if not in the index) - relief valves, check valves, ...
  * BPCS loop tags     -> not representable (no Loop label); reported, and X18 lists them
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, classify, func_prefix, role
from .tables import LOPA_IPL_ALIASES, LOPA_SCENARIO_ALIASES, detect_document, read_table, sheet_names


def _num(v: str):
    try:
        return float(str(v).replace(",", "")) if str(v).strip() not in ("", "-") else None
    except ValueError:
        return None


def load_lopa(store: MemoryStore, path: str | Path, *, unit: str, load_run: str,
              scenario_sheet: str | None = None, ipl_sheet: str | None = None) -> dict:
    path = Path(path)
    names = sheet_names(path)
    scenario_sheet = scenario_sheet or next((n for n in names if "scenario" in n.lower()), names[0])
    ipl_sheet = ipl_sheet or next((n for n in names if "ipl" in n.lower() or "layer" in n.lower()), None)
    doc_no, rev, how = detect_document(path, scenario_sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "scenarios": 0, "credits": 0, "threatens": 0, "lopa_only": [], "unrepresentable": [], "skipped": [], "notes": []}
    doc_key = {"doc_no": doc_no, "rev": rev}
    prov_doc = {"source_doc": doc_no, "source_rev": rev, "source_sheet": scenario_sheet, "extracted_by": "table",
                "load_run": load_run, "source_ref": path.name}
    store.merge_node("Document", doc_key, {"doc_type": "LOPA", "title": f"Layer of protection analysis {doc_no}", "unit": unit,
                                           "file": path.name, **prov_doc})
    alarms_by_tag = {n["props"].get("alarm_tag"): n["key"]["alarm_id"] for n in store.nodes("Alarm") if n["props"].get("alarm_tag")}

    def credit(sc_key: dict, raw_tag: str, ipl_type: str, props: dict, prov: dict) -> bool:
        ident = canonical_id(raw_tag)
        if not ident:
            return False
        if ident.startswith(("SIF-", "ESD-", "PSD-", "USD-")) or store.has_node("SIF", {"sif_id": ident}):
            key = {"sif_id": ident}
            if not store.has_node("SIF", key):
                store.merge_node("SIF", key, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
                report["lopa_only"].append({"kind": "SIF", "id": ident, "ref": prov["source_ref"]})
            store.merge_rel("CREDITS", "Scenario", sc_key, "SIF", key, {**props, **prov})
            return True
        tag = canonical_tag(raw_tag)
        if tag and role(tag) == "alarm":
            alarm_id = alarms_by_tag.get(tag, tag)
            if not store.has_node("Alarm", {"alarm_id": alarm_id}):
                store.merge_node("Alarm", {"alarm_id": alarm_id}, {"alarm_tag": tag, "alarm_type": func_prefix(tag), "unit": unit, "stub_unit": unit, **prov}, stub=True)
                report["lopa_only"].append({"kind": "Alarm", "id": tag, "ref": prov["source_ref"]})
            store.merge_rel("CREDITS", "Scenario", sc_key, "Alarm", {"alarm_id": alarm_id}, {**props, **prov})
            return True
        if tag and role(tag) == "loop":
            report["unrepresentable"].append({"id": tag, "ipl_type": ipl_type, "ref": prov["source_ref"],
                                              "reason": "BPCS control loop: no Loop label in the ontology"})
            return False
        label, ident2 = classify(raw_tag)
        if label == "Instrument" or (tag and label != "Line"):
            key = {"tag": tag or ident2}
            if not store.has_node("Instrument", key):
                store.merge_node("Instrument", key, {"type": func_prefix(key["tag"]), "role": role(key["tag"]), "unit": unit, "stub_unit": unit, **prov}, stub=True)
                report["lopa_only"].append({"kind": "Instrument", "id": key["tag"], "ref": prov["source_ref"]})
            store.merge_rel("CREDITS", "Scenario", sc_key, "Instrument", key, {**props, **prov})
            return True
        report["unrepresentable"].append({"id": ident, "ipl_type": ipl_type, "ref": prov["source_ref"], "reason": "not a SIF, alarm or instrument tag"})
        return False

    for r in read_table(path, scenario_sheet, LOPA_SCENARIO_ALIASES):
        ref = f"{path.name}:{scenario_sheet}:{r['_row']}"
        sc = canonical_id(r.get("scenario_id"))
        if not sc:
            report["skipped"].append({"ref": ref, "reason": "row has no scenario id"})
            continue
        prov = {**prov_doc, "source_ref": ref}
        sc_key = {"scenario_id": sc}
        store.merge_node("Scenario", sc_key, {
            "initiating_event": r.get("initiating_event", ""), "ie_frequency": r.get("ie_frequency", ""),
            "consequence": r.get("consequence", ""), "severity": r.get("severity", ""),
            "tolerable_frequency": r.get("tolerable_frequency", ""), "conditional_modifiers": r.get("conditional_modifiers", ""),
            "required_rrf": r.get("required_rrf", ""), "required_sil": r.get("required_sil", ""), "notes": r.get("notes", ""),
            "unit": unit, **prov})
        store.merge_rel("SHOWN_ON", "Scenario", sc_key, "Document", doc_key, prov)
        report["scenarios"] += 1
        if r.get("node"):
            label, ident = classify(r["node"])
            if label != "Instrument":
                pk = {"line_no": ident} if label == "Line" else {"tag": ident}
                ex = store.get_node(label, pk)
                if ex is None:
                    store.merge_node(label, pk, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
                else:
                    store.merge_node(label, pk, prov, stub=ex["props"].get("stub", False))
                store.merge_rel("THREATENS", "Scenario", sc_key, label, pk, prov)
                report["threatens"] += 1
        if r.get("required_sif"):
            before = len(store.rels("CREDITS"))
            credit(sc_key, r["required_sif"], "SIF", {"ipl_type": "SIF", "required_rrf": _num(r.get("required_rrf", "")),
                                                       "required_sil": r.get("required_sil", "")}, prov)
            report["credits"] += len(store.rels("CREDITS")) - before
    if ipl_sheet:
        for r in read_table(path, ipl_sheet, LOPA_IPL_ALIASES):
            ref = f"{path.name}:{ipl_sheet}:{r['_row']}"
            sc = canonical_id(r.get("scenario_id"))
            if not sc or not store.has_node("Scenario", {"scenario_id": sc}):
                report["skipped"].append({"ref": ref, "reason": f"scenario {sc or '?'} not in the Scenarios sheet"})
                continue
            if not r.get("tag"):
                report["skipped"].append({"ref": ref, "reason": "IPL row has no tag"})
                continue
            pfd = _num(r.get("pfd", ""))
            if pfd is None:
                report["skipped"].append({"ref": ref, "reason": f"{r['tag']}: no PFD credited (listed, not credited)"})
                continue
            prov = {**prov_doc, "source_sheet": ipl_sheet, "source_ref": ref}
            before = len(store.rels("CREDITS"))
            credit({"scenario_id": sc}, r["tag"], r.get("ipl_type", ""), {"ipl_type": r.get("ipl_type", ""), "pfd": pfd,
                                                                            "credit_description": r.get("description", "")}, prov)
            report["credits"] += len(store.rels("CREDITS")) - before
    if report["lopa_only"]:
        report["notes"].append(f"{len(report['lopa_only'])} credited layer(s) are not in any register; stub nodes created (X18)")
    if report["unrepresentable"]:
        report["notes"].append(f"{len(report['unrepresentable'])} credited layer(s) cannot be represented in v1.2 (X18)")
    return report
