"""DCS / SIS configuration export -> what is actually running.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Four sheets:
  Points     configured I/O and blocks -> Instrument properties `configured`, `range_cfg`, `units_cfg`,
             `system_cfg`, `controller_cfg`, `io_channel_cfg`. A configured point the index does not list
             becomes a stub Instrument (checked as C2). Controller blocks whose tag is an index loop number
             (PIC-1005) are loops, not instruments, and are skipped.
  Alarms     configured alarms -> Alarm properties `setpoint_cfg`, `priority_cfg`, `enabled_cfg`, `alarm_type_cfg`.
             The configuration owns what is configured, so an alarm nobody rationalised is created (C3).
  SIS Trips  INITIATES and ACTUATES as configured, beside the C&E's (one relationship per document, D-P1-06).
  Overrides  maintenance override switches -> the switch as a stub Instrument, and on the overridden
             instrument `override_switch`, `override_sif`, `override_degraded_voting`, `override_max_h`,
             `override_timeout_action`, `override_active`, `override_active_since`. No relationship type
             exists for "overrides" in v1.3 and none is added (D-V13-12); the link is the property.
The export time is the document's status line; it is kept on the Document as `export_time`.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, func_prefix
from .ops_common import alarm_index, document, ensure_instrument, prov, split_tags, with_units
from .tables import (CFG_ALARM_ALIASES, CFG_OVERRIDE_ALIASES, CFG_POINT_ALIASES, CFG_TRIP_ALIASES, clean, detect_document,
                     raw_rows, read_table, sheet_names)

EXPORT_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")


def _export_time(path: Path) -> str:
    rows, _ = raw_rows(path, sheet_names(path)[0])
    for r in rows[:3]:
        m = EXPORT_RE.search(" ".join(clean(c) for c in r if c))
        if m:
            return m.group(1)
    return ""


def _loops(store) -> set[str]:
    return {n["props"].get("loop") for n in store.nodes("Instrument") if n["props"].get("loop")}


def load_config(store: MemoryStore, path: str | Path, *, unit: str, load_run: str) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, "Points")
    export_time = _export_time(path)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how}, "export_time": export_time,
              "points": 0, "cfg_only_points": [], "loops_skipped": [], "alarms": 0, "new_alarms": [], "initiates": 0,
              "actuates": 0, "overrides": 0, "skipped": []}
    doc_key = document(store, doc_no, rev, "CFG", f"DCS / SIS configuration export {doc_no}", unit, path, load_run,
                       export_time=export_time)
    loops = _loops(store)

    for r in read_table(path, "Points", CFG_POINT_ALIASES):
        ref = f"{path.name}:Points:{r['_row']}"
        tag = canonical_tag(r.get("tag"))
        if not tag:
            report["skipped"].append({"ref": ref, "reason": "point tag not tag-shaped"})
            continue
        if tag in loops and r.get("block_type", "").upper() in ("PID", "IND"):
            report["loops_skipped"].append(tag)
            continue
        p = prov(doc_no, rev, "Points", load_run, ref)
        rng = f"{r.get('range_low', '')}-{r.get('range_high', '')}" if r.get("range_high") not in (None, "") else ""
        if ensure_instrument(store, tag, unit, p, configured="yes", range_cfg=rng, units_cfg=r.get("units", ""),
                             system_cfg=r.get("system", ""), controller_cfg=r.get("controller", ""),
                             io_channel_cfg=r.get("io_channel", ""), block_type_cfg=r.get("block_type", ""),
                             service_cfg=r.get("description", "")):
            report["cfg_only_points"].append(tag)
        store.merge_rel("SHOWN_ON", "Instrument", {"tag": tag}, "Document", doc_key, p)
        report["points"] += 1

    for r in read_table(path, "Alarms", CFG_ALARM_ALIASES):
        ref = f"{path.name}:Alarms:{r['_row']}"
        tag, source = canonical_tag(r.get("alarm_tag")), canonical_tag(r.get("source_tag"))
        if not tag or not source or not store.has_node("Instrument", {"tag": source}):
            report["skipped"].append({"ref": ref, "alarm": r.get("alarm_tag"), "reason": "alarm or its source not resolvable"})
            continue
        p = prov(doc_no, rev, "Alarms", load_run, ref)
        props = {"setpoint_cfg": with_units(r.get("limit"), r.get("units")), "priority_cfg": r.get("priority", ""),
                 "enabled_cfg": r.get("enabled", ""), "alarm_type_cfg": r.get("alarm_type", ""), "system_cfg": r.get("system", ""),
                 "deadband_cfg": r.get("deadband", ""), "on_delay_cfg": r.get("on_delay", ""), "cfg_ref": ref}
        alarm_id = alarm_index(store).get(tag)
        if alarm_id is None:
            alarm_id = f"{source}.{func_prefix(tag)}"
            report["new_alarms"].append(tag)
            store.merge_node("Alarm", {"alarm_id": alarm_id}, {"alarm_tag": tag, "alarm_type": func_prefix(tag), "unit": unit,
                                                               **props, **p})
        else:
            store.merge_node("Alarm", {"alarm_id": alarm_id}, {**props, **p}, stub=False)   # configured: it exists
        store.merge_rel("GENERATES", "Instrument", {"tag": source}, "Alarm", {"alarm_id": alarm_id}, p)
        store.merge_rel("SHOWN_ON", "Alarm", {"alarm_id": alarm_id}, "Document", doc_key, p)
        report["alarms"] += 1

    for r in read_table(path, "SIS Trips", CFG_TRIP_ALIASES):
        ref = f"{path.name}:SIS Trips:{r['_row']}"
        sif = canonical_id(r.get("sif_id"))
        if not store.has_node("SIF", {"sif_id": sif}):
            report["skipped"].append({"ref": ref, "reason": f"SIF {sif} not in the graph"})
            continue
        p = prov(doc_no, rev, "SIS Trips", load_run, ref)
        store.merge_node("SIF", {"sif_id": sif}, {"voting_cfg": r.get("voting", ""), "trip_enabled_cfg": r.get("enabled", ""),
                                                  "logic_solver_cfg": canonical_id(r.get("logic_solver", "")), **p},
                         stub=store.get_node("SIF", {"sif_id": sif})["props"].get("stub", False))
        store.merge_rel("SHOWN_ON", "SIF", {"sif_id": sif}, "Document", doc_key, p)
        for t in split_tags(r.get("initiators")):
            tag = canonical_tag(t)
            if not tag:
                continue
            if ensure_instrument(store, tag, unit, p):
                report["cfg_only_points"].append(tag)
            store.merge_rel("INITIATES", "Instrument", {"tag": tag}, "SIF", {"sif_id": sif},
                            {**p, "voting": r.get("voting", ""), "setpoint": with_units(r.get("setpoint"), r.get("units")),
                             "direction": r.get("direction", "")})
            report["initiates"] += 1
        actions = dict(a.split(" ", 1) for a in split_tags(r.get("action")) if " " in a)
        for t in split_tags(r.get("final_elements")):
            tag = canonical_tag(t)
            if not tag:
                continue
            if ensure_instrument(store, tag, unit, p):
                report["cfg_only_points"].append(tag)
            store.merge_rel("ACTUATES", "SIF", {"sif_id": sif}, "Instrument", {"tag": tag}, {**p, "action": actions.get(t, "").title()})
            report["actuates"] += 1

    for r in read_table(path, "Overrides", CFG_OVERRIDE_ALIASES):
        ref = f"{path.name}:Overrides:{r['_row']}"
        mos, element, sif = canonical_tag(r.get("override_tag")), canonical_tag(r.get("element")), canonical_id(r.get("sif_id"))
        if not mos or not element:
            report["skipped"].append({"ref": ref, "reason": "override or element not tag-shaped"})
            continue
        p = prov(doc_no, rev, "Overrides", load_run, ref)
        o = {"override_switch": mos, "override_sif": sif, "override_degraded_voting": r.get("degraded_voting", ""),
             "override_max_h": r.get("max_h", ""), "override_timeout_action": r.get("timeout_action", ""),
             "override_alarm_priority": r.get("alarm_priority", ""), "override_active": r.get("active", ""),
             "override_active_since": r.get("active_since", ""), "override_ref": ref}
        if ensure_instrument(store, element, unit, p, **o):
            report["cfg_only_points"].append(element)
        if ensure_instrument(store, mos, unit, p, configured="yes", block_type_cfg="MOS", overrides=element,
                             **{k: v for k, v in o.items() if k != "override_switch"}):
            report["cfg_only_points"].append(mos)
        store.merge_rel("SHOWN_ON", "Instrument", {"tag": mos}, "Document", doc_key, p)
        report["overrides"] += 1
    return report
