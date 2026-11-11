"""CSV / Excel table reading with header aliasing and title-block detection.

Ported from the NetworkX prototype (Documents/pid_graph, 3 Sep 2026). Real EPC
deliverables never use canonical column names, so each loader passes an alias map
(canonical -> accepted spellings, normalised) and the header row is found below
any title block automatically. Every returned row carries `_row`, its 1-based
row number in the sheet, for file:row provenance.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

INDEX_ALIASES = {
    "tag": ["tag", "tag_no", "tag_number", "instrument_tag", "tagno"],
    "description": ["description", "service_description", "service", "tag_description"],
    "type": ["type", "instrument_type", "inst_type", "function"],
    "loop": ["loop", "loop_no", "loop_number"],
    "unit": ["unit", "area", "area_unit", "process_unit", "unit_area"],
    "pid_sheet": ["pid_sheet", "p_id_no", "p_id", "pid", "pid_no", "drawing", "drawing_no", "p_id_drawing"],
    "line": ["line", "line_no", "line_number"],
    "equipment": ["equipment", "equipment_no", "equipment_tag", "equipment_number"],
    "line_equipment": ["line_equipment_no", "line_equipment", "line_equip_no", "location_line_equipment"],
    "layer": ["layer", "system", "protection_layer", "control_system", "sis_bpcs"],
    "range": ["range", "calibrated_range", "span"],
    "units": ["units", "eng_units", "engineering_units", "uom"],
    "signal": ["signal", "signal_type", "io_type", "output"],
    "remarks": ["remarks", "notes", "comment", "comments"],
    "bypassed": ["bypassed", "bypass", "in_bypass", "override"],
}
ALARM_ALIASES = {
    "alarm_tag": ["alarm_tag", "alarm", "alarm_no", "tag"],
    "sensor_tag": ["sensor_tag", "source_tag", "source", "derived_from", "input_tag", "transmitter"],
    "setpoint": ["setpoint", "set_point", "sp", "alarm_setpoint", "limit"],
    "priority": ["priority", "alarm_priority", "class"],
    "layer": ["layer", "system", "control_system"],
    "protects": ["protects", "protected_equipment", "equipment", "equipment_no"],
    "description": ["description", "alarm_description", "service_description", "consequence"],
}
CE_ALIASES = {
    "sif_id": ["sif_id", "sif", "sif_no", "sif_number", "function_id", "ipf_no"],
    "sif_description": ["sif_description", "description", "function_description"],
    "sil": ["sil", "sil_target", "target_sil", "sil_level"],
    "logic_solver": ["logic_solver", "solver", "sis", "controller", "logic_solver_tag"],
    "cause_tag": ["cause_tag", "cause", "initiator", "initiator_tag", "input_tag", "sensor"],
    "cause_description": ["cause_description", "cause_desc", "initiator_description"],
    "voting": ["voting", "vote", "voting_logic", "moon"],
    "setpoint": ["setpoint", "set_point", "trip_setpoint", "trip_point", "trip_setting"],
    "effect_tag": ["effect_tag", "effect", "final_element", "final_element_tag", "output_tag"],
    "effect_action": ["effect_action", "action", "effect_state", "state", "safe_state"],
    "protects": ["protects", "protected_equipment", "equipment", "hazard_equipment"],
}
SRS_ALIASES = {
    "sif_id": ["sif_id", "sif", "sif_no", "sif_number", "function_id", "ipf_no"],
    "functional_description": ["functional_description", "function", "description", "sif_description"],
    "hazard": ["hazard", "hazard_consequence", "consequence", "hazardous_event"],
    "sil": ["sil", "sil_target", "target_sil", "required_sil"],
    "rrf": ["rrf", "rrf_target", "risk_reduction_factor", "target_rrf"],
    "pfd": ["pfd", "pfdavg", "pfdavg_target", "pfd_target", "target_pfd"],
    "demand_mode": ["demand_mode", "mode_of_operation", "mode"],
    "safe_state": ["safe_state", "final_state", "trip_state"],
    "process_safety_time": ["process_safety_time", "pst"],
    "response_time": ["response_time", "sif_response_time", "sis_response_time"],
    "setpoint": ["setpoint", "trip_setpoint", "trip_point", "trip_setting"],
    "sensor_architecture": ["sensor_architecture", "sensor_voting", "initiator_architecture", "input_architecture", "voting"],
    "fe_architecture": ["fe_architecture", "final_element_architecture", "output_architecture", "final_element_voting"],
    "proof_test_interval": ["proof_test_interval", "pti", "test_interval"],
    "bypass_conditions": ["bypass_conditions", "bypass_requirements", "override_requirements", "bypass"],
    "manual_shutdown": ["manual_shutdown", "manual_trip", "manual_initiation"],
    "reset": ["reset", "reset_requirements", "reset_philosophy"],
    "logic_solver": ["logic_solver", "solver", "sis", "controller"],
    "protects": ["protects", "protected_equipment", "equipment", "equipment_protected"],
}
LOPA_SCENARIO_ALIASES = {
    "scenario_id": ["scenario_id", "scenario_no", "scenario", "scenario_number", "lopa_no", "case"],
    "node": ["node", "node_equipment", "equipment", "equipment_no", "node_no"],
    "initiating_event": ["initiating_event", "initiating_cause", "ie", "cause"],
    "ie_frequency": ["ie_frequency", "ie_frequency_yr", "initiating_event_frequency", "ief", "frequency"],
    "consequence": ["consequence", "consequence_description", "hazardous_event"],
    "severity": ["severity", "severity_category", "consequence_category", "category"],
    "tolerable_frequency": ["tolerable_frequency", "tolerable_frequency_yr", "target_frequency", "tmel", "tolerable_risk"],
    "conditional_modifiers": ["conditional_modifiers", "modifiers", "enabling_conditions", "conditional_modifier"],
    "required_sif": ["required_sif", "sif", "sif_no", "sif_id"],
    "required_rrf": ["required_rrf", "rrf_required", "sif_rrf", "required_risk_reduction"],
    "required_sil": ["required_sil", "sil_required", "sif_sil", "sil"],
    "notes": ["notes", "remarks", "comments"],
}
LOPA_IPL_ALIASES = {
    "scenario_id": ["scenario_id", "scenario_no", "scenario", "scenario_number", "lopa_no"],
    "ipl_type": ["ipl_type", "type", "layer_type", "ipl", "layer"],
    "tag": ["tag", "ipl_tag", "tag_no", "reference", "sif_alarm_device"],
    "description": ["description", "ipl_description", "credit_basis"],
    "pfd": ["pfd", "pfd_credited", "pfd_credit", "credit", "pfdavg"],
}
TOPOLOGY_ALIASES = {
    "from_tag": ["from_tag", "from", "source_tag", "upstream", "upstream_tag", "node_a"],
    "to_tag": ["to_tag", "to", "target_tag", "downstream", "downstream_tag", "node_b"],
    "via_line": ["via_line", "line", "line_no", "line_number", "via"],
    "pid_sheet": ["pid_sheet", "sheet", "drawing", "drawing_no", "p_id", "p_id_no", "pid"],
    "confidence": ["confidence", "score", "conf"],
    "verified": ["verified", "human_verified", "checked", "reviewed"],
}

YES = ("y", "yes", "true", "1", "x")


def norm(header) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(header or "").strip().lower()).strip("_")


def clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def raw_rows(path: str | Path, sheet: str | None = None) -> tuple[list[list], str]:
    """All rows of a sheet (or CSV) as lists of raw cell values, plus the sheet title."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)], ws.title
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.reader(f)], path.name


def sheet_names(path: str | Path) -> list[str]:
    path = Path(path)
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        return [path.name]
    from openpyxl import load_workbook
    return load_workbook(path, read_only=True).sheetnames


def _detect_header_row(rows: list, aliases: dict | None) -> int:
    accepted = {a for names in (aliases or {}).values() for a in names}
    for i, r in enumerate(rows[:30]):
        cells = [norm(c) for c in r if c not in (None, "")]
        if accepted and sum(c in accepted for c in cells) >= 2:
            return i
        if not accepted and len(cells) >= 2:
            return i
    return 0


def _apply_aliases(row: dict, aliases: dict | None) -> dict:
    if not aliases:
        return row
    out = dict(row)
    for canonical, names in aliases.items():
        if out.get(canonical):
            continue
        for n in names:
            if row.get(n):
                out[canonical] = row[n]
                break
    # A combined "Line / Equipment No." column: lines start with L-, everything else is equipment.
    if out.get("line_equipment") and not (out.get("line") or out.get("equipment")):
        v = out["line_equipment"].strip()
        if v.upper().startswith(("L-", "LINE")):
            out["line"] = v
        else:
            out["equipment"] = v
    return out


def read_table(path: str | Path, sheet: str | None = None, aliases: dict | None = None,
               header_row: int | None = None) -> list[dict]:
    """Rows as dicts with canonical keys. `header_row` (1-based) overrides detection."""
    rows, _ = raw_rows(path, sheet)
    start = (header_row - 1) if header_row else _detect_header_row(rows, aliases)
    headers = [norm(h) for h in rows[start]]
    out = []
    for i, r in enumerate(rows[start + 1:], start=start + 2):
        if r is None or all(v in (None, "") for v in r):
            continue
        d = _apply_aliases({h: clean(v) for h, v in zip(headers, r) if h}, aliases)
        d["_row"] = i
        out.append(d)
    return out


# ---- Title block / document identity ---------------------------------------

DOC_RE = re.compile(r"Document\s*No\.?\s*:?\s*(?P<doc>[A-Z0-9][A-Z0-9\-_/.]+).*?\bRev(?:ision)?\.?\s*:?\s*(?P<rev>[A-Z0-9]+)",
                    re.I)
FILENAME_RE = re.compile(r"^(?P<doc>.+?)[-_ ]Rev[-_ ]?(?P<rev>[A-Z0-9]+)$", re.I)


def detect_document(path: str | Path, sheet: str | None = None) -> tuple[str, str, str]:
    """(doc_no, rev, how). Deterministic: title rows of the sheet, then a Cover sheet, then the filename."""
    path = Path(path)
    rows, _ = raw_rows(path, sheet)
    for r in rows[:10]:
        text = "  ".join(clean(c) for c in r if c not in (None, ""))
        m = DOC_RE.search(text)
        if m:
            return m.group("doc").upper(), m.group("rev").upper(), f"title row of sheet {sheet or 1}"
    if path.suffix.lower() in (".xlsx", ".xlsm") and "Cover" in sheet_names(path):
        cover, _ = raw_rows(path, "Cover")
        kv = {norm(r[0]): clean(r[1]) for r in cover if len(r) >= 2 and r[0] not in (None, "")}
        doc = kv.get("document_no") or kv.get("document_number") or kv.get("doc_no")
        rev = kv.get("revision") or kv.get("rev")
        if doc and rev:
            return doc.upper(), rev.upper(), "Cover sheet"
    m = FILENAME_RE.match(path.stem)
    if m:
        return m.group("doc").upper(), m.group("rev").upper(), "filename"
    return path.stem.upper(), "UNKNOWN", "filename (no revision found)"
