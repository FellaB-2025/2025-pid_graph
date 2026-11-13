"""Master alarm database (rationalisation record per alarm) -> Alarm nodes and properties.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The MADB is the owning source of alarms, so an alarm it rationalises that the index's alarm register
does not list is created (with GENERATES from its source instrument). Its claims land beside the
alarm register's: `setpoint_madb`, `priority_madb`, plus the rationalisation fields (alarm_class,
ipl_credit, lopa_ref, consequence, operator_action, time_to_respond, implementation_status ...).
pid_graph.ops_checks compares them with the register, the LOPA and the configuration.
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_tag, func_prefix
from .ops_common import alarm_index, document, prov, with_units
from .tables import MADB_ALIASES, detect_document, read_table

FIELDS = ("alarm_class", "cause", "consequence", "operator_action", "time_to_respond", "deadband", "on_delay", "off_delay",
          "ipl_credit", "lopa_ref", "implementation_status", "rationalised", "team")


def load_madb(store: MemoryStore, path: str | Path, *, unit: str, load_run: str, sheet: str | None = None) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "rows": 0, "alarms": 0, "new_alarms": [], "skipped": []}
    doc_key = document(store, doc_no, rev, "MADB", f"Master alarm database {doc_no}", unit, path, load_run)
    rows = read_table(path, sheet, MADB_ALIASES)
    report["rows"] = len(rows)
    for r in rows:
        ref = f"{path.name}:{sheet or 1}:{r['_row']}"
        tag, source = canonical_tag(r.get("alarm_tag")), canonical_tag(r.get("source_tag"))
        if not tag or not source:
            report["skipped"].append({"ref": ref, "reason": "alarm tag or source tag missing"})
            continue
        if not store.has_node("Instrument", {"tag": source}):
            report["skipped"].append({"ref": ref, "alarm": tag, "reason": f"source {source} is not in the graph"})
            continue
        p = prov(doc_no, rev, sheet or "", load_run, ref)
        props = {f: r.get(f, "") for f in FIELDS}
        props.update({"setpoint_madb": with_units(r.get("setpoint"), r.get("units")), "priority_madb": r.get("priority", ""),
                      "outcome_madb": r.get("outcome", ""), "madb_ref": ref})
        alarm_id = alarm_index(store).get(tag)
        if alarm_id is None:
            alarm_id = f"{source}.{func_prefix(tag)}"
            report["new_alarms"].append(tag)
            store.merge_node("Alarm", {"alarm_id": alarm_id}, {"alarm_tag": tag, "alarm_type": func_prefix(tag),
                                                               "description": r.get("description", ""), "unit": unit, **props, **p})
        else:
            ex = store.get_node("Alarm", {"alarm_id": alarm_id})
            store.merge_node("Alarm", {"alarm_id": alarm_id}, {**props, **p}, stub=ex["props"].get("stub", False))
        store.merge_rel("GENERATES", "Instrument", {"tag": source}, "Alarm", {"alarm_id": alarm_id}, p)
        store.merge_rel("SHOWN_ON", "Alarm", {"alarm_id": alarm_id}, "Document", doc_key, p)
        report["alarms"] += 1
    return report
