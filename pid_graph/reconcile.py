"""Coverage report and exception register (decisions section 2).

Completeness is measured, not hoped for. The instrument index defines the expected
population; everything else reconciles against it. Mismatches are exceptions in an
Excel register, never silent edits to the graph. Works on either store.

Exception codes:
  X1 INDEX_TAG_NOT_ON_PID   index instrument with no P&ID extraction evidence
  X2 PID_TAG_NOT_IN_INDEX   instrument extracted from a P&ID with no index row (stub)
  X3 SHEET_MISMATCH         index says drawing A, extraction found it on drawing B only
  X4 CE_TAG_UNMATCHED       C&E cause/effect tag matches no instrument and no alarm
  X5 LOW_CONFIDENCE_EDGE    extracted edge below the confidence threshold, not human-verified
  X6 PROPERTY_CONFLICT      two sources disagree on a property value (both kept)
  X7 DOCUMENT_REV_UNKNOWN   a drawing is referenced but its title block has not been read
  X8 OFFPAGE_STUB           battery-limit / header reference awaiting its own unit's load
  X9 CE_ALARM_NOT_IN_REG    C&E alarm effect that the alarm register does not define (stub Alarm)
  X10 VOTING_MISMATCH       MooN on INITIATES does not match the number of initiators listed
  X11 SHARED_SENSOR         an alarm's source instrument also initiates a SIF (independence check)
"""
from __future__ import annotations

import re
from pathlib import Path

from . import ontology as O

VOTING_RE = re.compile(r"(\d+)\s*oo\s*(\d+)", re.I)

TITLES = {
    "X1": "Index instrument not found on any P&ID extraction",
    "X2": "P&ID instrument not in the instrument index",
    "X3": "Index P&ID reference disagrees with extraction",
    "X4": "C&E tag matches neither index nor P&ID",
    "X5": "Low-confidence extracted edge (unverified)",
    "X6": "Property conflict between sources",
    "X7": "Document revision unknown (title block not read)",
    "X8": "Off-page / battery-limit stub",
    "X9": "C&E alarm effect not in the alarm register",
    "X10": "SIF voting arity does not match initiator count",
    "X11": "Alarm shares its sensor with a SIF initiator",
    "X12": "Drawing registered from the PDF but nothing extracted from it",
    "X13": "P&ID PDF page problem (no text layer / title block not read)",
    "X14": "SIF has no curated compensating measure",
    "X15": "SIL disagrees between LOPA, SRS and C&E",
    "X16": "Trip setpoint disagrees between SRS and C&E",
    "X17": "LOPA-credited layer is not independent",
    "X18": "LOPA-credited layer not in any register / not representable",
    "X19": "SIF in SRS but not in C&E, or in C&E but not in SRS",
    "X20": "Sensor architecture disagrees between SRS and C&E",
    # v1.3: raised by load_pidkg.py (the vision layer), not by reconcile(); listed here so one table names every code
    "X21": "On P&ID (vision), not in the instrument index / equipment",
    "X22": "In the index, not found on the P&ID (vision)",
    "X23": "Vision sheet matches no drawing revision in the graph",
    "X24": "Vision boundary matches no battery limit / header",
    "X25": "Vision line is not a line in the graph",
    "X26": "Off-page connector not paired",
    "X27": "pid-to-kg QA issue or unreadable item",
    "X28": "Vision fact cannot be represented",
    "X29": "Interlock symbol collapsed into direct trip signals",
    # v1.3: raised by vision_checks.py (vision against the registers)
    "X30": "Index drawing reference disagrees with vision",
    "X31": "Flow derived from vision disagrees with pid_audit",
    "X32": "Instrument's line disagrees between index and vision",
    "X33": "Drawn trip signal has no cause and effect in the C&E",
    "X34": "C&E cause and effect has no drawn trip signal",
    "X35": "Valve fail position or actuator as drawn disagrees with the index",
    "X36": "Loop membership as drawn disagrees with the index",
}
EXTRACTED = ("pid_audit", "manual", "llm")


def reconcile(store, *, unit: str, ce_report: dict | None = None, titleblock_report: dict | None = None,
              curated_report: dict | None = None, lopa_report: dict | None = None, low_confidence: float = 0.75) -> dict:
    docs = {(d["key"]["doc_no"], d["key"]["rev"]): d["props"] for d in store.nodes("Document")}
    instruments = {n["key"]["tag"]: n["props"] for n in store.nodes("Instrument")}
    alarms = {n["props"].get("alarm_tag", ""): n for n in store.nodes("Alarm")}
    shown: dict[tuple, list] = {}
    for r in store.rels("SHOWN_ON"):
        start = (r["start_label"], tuple(r["start_key"].values()))
        shown.setdefault(start, []).append(r)

    ex: list[dict] = []

    def add(code, label, ident, detail, sources="", refs=""):
        ex.append({"code": code, "title": TITLES[code], "label": label, "id": ident, "detail": detail,
                   "sources": sources, "refs": refs})

    n_index = n_index_on_pid = n_pid = n_pid_in_index = 0
    for tag, props in sorted(instruments.items()):
        edges = shown.get(("Instrument", (tag,)), [])
        idx = [e for e in edges if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "IDX"]
        claimed = {e["end_key"]["doc_no"] for e in edges
                   if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "PID" and e["props"].get("extracted_by") == "table"}
        seen = {e["end_key"]["doc_no"] for e in edges
                if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "PID" and e["props"].get("extracted_by") in EXTRACTED}
        seen_refs = "; ".join(sorted({e["props"].get("source_ref", "") for e in edges if e["props"].get("extracted_by") in EXTRACTED}))
        if idx:
            n_index += 1
            if seen:
                n_index_on_pid += 1
            else:
                add("X1", "Instrument", tag, f"Index places it on {', '.join(sorted(claimed)) or 'no drawing'}; no extraction row mentions it.",
                    "index vs pid_audit", "; ".join(sorted({e["props"].get("source_ref", "") for e in idx})))
            if claimed and seen and not (claimed & seen):
                add("X3", "Instrument", tag, f"Index says {', '.join(sorted(claimed))}; extraction found it on {', '.join(sorted(seen))}.",
                    "index vs pid_audit", seen_refs)
        if seen:
            n_pid += 1
            if idx:
                n_pid_in_index += 1
            else:
                add("X2", "Instrument", tag, f"Extracted from {', '.join(sorted(seen))} but has no index row (stub node).",
                    "pid_audit vs index", seen_refs)

    for tag, props in sorted(instruments.items()):
        edges = shown.get(("Instrument", (tag,)), [])
        ce = [e for e in edges if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "CE"]
        idx = [e for e in edges if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "IDX"]
        if ce and not idx:
            pid = [e["end_key"]["doc_no"] for e in edges
                   if docs.get(tuple(e["end_key"].values()), {}).get("doc_type") == "PID"
                   and e["props"].get("extracted_by") in EXTRACTED]
            add("X4", "Instrument", tag, "Referenced by the C&E but has no instrument index row"
                + (f"; seen on {', '.join(sorted(pid))}." if pid else "; not seen on any P&ID either (stub node)."),
                "cause_effect vs index", "; ".join(sorted({e["props"].get("source_ref", "") for e in ce})))

    for r in store.rels("RAISES"):
        a = r["end_key"]["alarm_id"]
        props = next((n["props"] for n in store.nodes("Alarm") if n["key"]["alarm_id"] == a), {})
        if props.get("stub"):
            add("X9", "Alarm", a, f"C&E says {r['start_key']['sif_id']} raises {a}; the alarm register has no such alarm, so its source "
                "instrument, setpoint and priority are unknown (stub node).", "cause_effect vs alarm register", r["props"].get("source_ref", ""))

    initiates: dict[str, list] = {}
    for r in store.rels("INITIATES"):
        initiates.setdefault(r["end_key"]["sif_id"], []).append(r)
    for sif, edges in sorted(initiates.items()):
        for vote in sorted({e["props"].get("voting", "") for e in edges if e["props"].get("voting")}):
            m = VOTING_RE.search(vote)
            if not m:
                continue
            group = sorted(e["start_key"]["tag"] for e in edges if e["props"].get("voting") == vote)
            if len(group) != int(m.group(2)):
                add("X10", "SIF", sif, f"Voting {vote} implies {m.group(2)} initiators; the C&E lists {len(group)}: {', '.join(group)}.",
                    "cause_effect internal", "; ".join(sorted({e["props"].get("source_ref", "") for e in edges})))

    covered = {r["end_key"]["sif_id"] for r in store.rels("COMPENSATES_FOR")}
    proposed: dict[str, list] = {}
    gaps: dict[str, str] = {}
    for p in (curated_report or {}).get("proposed", []):
        proposed.setdefault(p["sif_id"], []).append(f"{p['alarm_id']} (rank {p['rank']}, {p['basis']})")
    for g in (curated_report or {}).get("gaps", []):
        gaps[g["sif_id"]] = g["rationale"]
    for n in store.nodes("SIF"):
        sif = n["key"]["sif_id"]
        if sif in covered:
            continue
        if sif in gaps:
            detail = "Curation records a GAP: " + gaps[sif]
        elif sif in proposed:
            detail = "Proposed, awaiting engineering approval: " + "; ".join(proposed[sif])
        else:
            detail = "Nothing curated and no gap recorded; CQ2 cannot name a compensating measure for this SIF."
        add("X14", "SIF", sif, detail, "curated register", (curated_report or {}).get("file", ""))

    # ---- v1.2: SRS and LOPA consistency (CQ11-CQ13) ----
    sif_nodes = {n["key"]["sif_id"]: n["props"] for n in store.nodes("SIF")}
    credits = store.rels("CREDITS")
    srs_docs = {(d, r) for (d, r), p in docs.items() if p.get("doc_type") == "SRS"}
    ce_docs = {(d, r) for (d, r), p in docs.items() if p.get("doc_type") == "CE"}
    for sif, p in sorted(sif_nodes.items()):
        edges = shown.get(("SIF", (sif,)), [])
        in_srs = any(tuple(e["end_key"].values()) in srs_docs for e in edges)
        in_ce = any(tuple(e["end_key"].values()) in ce_docs for e in edges)
        if srs_docs and in_ce and not in_srs:
            add("X19", "SIF", sif, "Defined in the C&E but has no entry in the SRS.", "cause_effect vs srs", p.get("source_ref", ""))
        if in_srs and not in_ce and ce_docs:
            add("X19", "SIF", sif, "Defined in the SRS but absent from the C&E (stub node).", "srs vs cause_effect", p.get("srs_ref", ""))
        lopa_sils = sorted({str(c["props"].get("required_sil", "")) for c in credits if c["end_label"] == "SIF" and c["end_key"]["sif_id"] == sif and c["props"].get("required_sil") not in (None, "")})
        claims = {"C&E": str(p.get("sil", "") or ""), "SRS": str(p.get("sil_srs", "") or ""), "LOPA": "/".join(lopa_sils)}
        stated = {k: v for k, v in claims.items() if v}
        if len(set(stated.values())) > 1:
            add("X15", "SIF", sif, "; ".join(f"{k} says SIL {v}" for k, v in stated.items()) + ". Both facts kept; resolve in the SRS.",
                " vs ".join(stated), "; ".join(filter(None, [p.get("source_ref", ""), p.get("srs_ref", "")])))
        ce_sps = sorted({str(r["props"].get("setpoint", "")) for r in store.rels("INITIATES") if r["end_key"]["sif_id"] == sif and r["props"].get("setpoint")})
        if p.get("setpoint_srs") and ce_sps and str(p["setpoint_srs"]).replace(" ", "").lower() not in {s.replace(" ", "").lower() for s in ce_sps}:
            add("X16", "SIF", sif, f"SRS trip setpoint {p['setpoint_srs']}; C&E initiators trip at {', '.join(ce_sps)}.", "srs vs cause_effect", p.get("srs_ref", ""))
        arch = VOTING_RE.search(str(p.get("sensor_architecture", "") or ""))
        ce_votes = sorted({str(r["props"].get("voting", "")) for r in store.rels("INITIATES") if r["end_key"]["sif_id"] == sif and r["props"].get("voting")})
        if arch and ce_votes and arch.group(0).lower().replace(" ", "") not in {v.lower().replace(" ", "") for v in ce_votes}:
            add("X20", "SIF", sif, f"SRS sensor architecture {p['sensor_architecture']}; C&E voting {', '.join(ce_votes)}.", "srs vs cause_effect", p.get("srs_ref", ""))
    # X17 / X18 per scenario
    gen_src = {r["end_key"]["alarm_id"]: r["start_key"]["tag"] for r in store.rels("GENERATES")}
    inits = {}
    for r in store.rels("INITIATES"):
        inits.setdefault(r["end_key"]["sif_id"], set()).add(r["start_key"]["tag"])
    acts = {}
    for r in store.rels("ACTUATES"):
        acts.setdefault(r["start_key"]["sif_id"], set()).add(r["end_key"]["tag"])
    node_props = {(n["label"], tuple(n["key"].values())): n["props"] for n in store.nodes()}
    by_sc: dict[str, list] = {}
    for c in credits:
        by_sc.setdefault(c["start_key"]["scenario_id"], []).append(c)
    for sc, cs in sorted(by_sc.items()):
        layers = [(c["end_label"], tuple(c["end_key"].values())[0], c["props"]) for c in cs]
        for lab, ident, cp in layers:
            if node_props.get((lab, (ident,)), {}).get("stub"):
                add("X18", lab, ident, f"Credited in {sc} as '{cp.get('ipl_type', '')}' (PFD {cp.get('pfd', '?')}) but not defined in any loaded register (stub).",
                    "lopa vs registers", cp.get("source_ref", ""))
        sifs_here = [ident for lab, ident, _ in layers if lab == "SIF"]
        for lab, ident, cp in layers:
            if lab == "Alarm":
                src = gen_src.get(ident)
                for s in sifs_here:
                    if src and src in inits.get(s, set()):
                        add("X17", "Alarm", ident, f"Credited in {sc} as an independent layer, but it derives from {src}, which initiates {s}, also credited in {sc}. Not independent.",
                            "lopa vs alarm register vs cause_effect", cp.get("source_ref", ""))
        for i, s1 in enumerate(sifs_here):
            for s2 in sifs_here[i + 1:]:
                shared = (inits.get(s1, set()) & inits.get(s2, set())) | (acts.get(s1, set()) & acts.get(s2, set()))
                if shared:
                    add("X17", "SIF", f"{s1} / {s2}", f"Both credited in {sc} but share {', '.join(sorted(shared))}.", "lopa vs cause_effect", "")
    if lopa_report:
        for u in lopa_report.get("unrepresentable", []):
            add("X18", "IPL", u["id"], f"Credited as '{u['ipl_type']}' but cannot be represented: {u['reason']}.", "lopa", u["ref"])

    sif_by_sensor: dict[str, set] = {}
    for r in store.rels("INITIATES"):
        sif_by_sensor.setdefault(r["start_key"]["tag"], set()).add(r["end_key"]["sif_id"])
    for r in store.rels("GENERATES"):
        sensor = r["start_key"]["tag"]
        if sensor in sif_by_sensor:
            add("X11", "Alarm", r["end_key"]["alarm_id"], f"Derives from {sensor}, which also initiates {', '.join(sorted(sif_by_sensor[sensor]))}. Confirm independence between the alarm layer and the SIS.",
                "alarm register vs cause_effect", r["props"].get("source_ref", ""))

    for r in store.rels():
        if r["type"] in ("INSTALLED_ON", "FEEDS", "MEASURES"):
            c = r["props"].get("confidence")
            if c is not None and float(c) < low_confidence and r["props"].get("extracted_by") != "manual":
                add("X5", r["type"], f"{list(r['start_key'].values())[0]} -> {list(r['end_key'].values())[0]}",
                    f"confidence {c} < {low_confidence}; verify on {r['props'].get('source_doc', '')} before relying on it.",
                    r["props"].get("extracted_by", ""), r["props"].get("source_ref", ""))

    for c in store.conflicts:
        add("X6", c.label, "|".join(c.key.values()), f"{c.prop}: {c.existing!r} ({c.existing_source}) vs {c.incoming!r} ({c.incoming_source}); both provenances kept.",
            f"{c.existing_source} vs {c.incoming_source}")

    witnessed = {tuple(r["end_key"].values()) for r in store.rels("SHOWN_ON")}
    for (doc_no, rev), props in sorted(docs.items()):
        if rev == O.UNKNOWN_REV:
            add("X7", "Document", doc_no, "Referenced by index and/or extraction; revision will be set by the title-block pass.",
                props.get("extracted_by", ""), props.get("source_ref", ""))
        elif props.get("doc_type") == "PID" and (doc_no, rev) not in witnessed:
            add("X12", "Document", f"{doc_no} rev {rev}", "Title block read from the PDF; no index row or extraction row mentions this drawing. Extraction pending or the drawing is out of scope.",
                props.get("extracted_by", ""), props.get("source_ref", ""))
    if titleblock_report:
        for p in titleblock_report.get("problems", []):
            add("X13", "Document", f"{p['file']} page {p['page']}", p["problem"], "pid_audit", f"{p['file']}:p{p['page']}")

    stubs = 0
    for n in store.nodes():
        if n["props"].get("stub") and n["label"] in ("Equipment", "Line"):
            stubs += 1
            add("X8", n["label"], "|".join(n["key"].values()), f"Referenced on {n['props'].get('source_doc', '')}; fills when its owning unit loads.",
                n["props"].get("extracted_by", ""), n["props"].get("source_ref", ""))
    stub_instruments = sum(1 for n in store.nodes("Instrument") if n["props"].get("stub"))

    by_code: dict[str, int] = {}
    for e in ex:
        by_code[e["code"]] = by_code.get(e["code"], 0) + 1
    summary = {
        "unit": unit,
        "index_instruments": n_index,
        "index_instruments_seen_on_pid": n_index_on_pid,
        "index_coverage_pct": round(100 * n_index_on_pid / n_index, 1) if n_index else None,
        "pid_instruments": n_pid,
        "pid_instruments_in_index": n_pid_in_index,
        "pid_match_pct": round(100 * n_pid_in_index / n_pid, 1) if n_pid else None,
        "stub_instruments": stub_instruments,
        "stub_equipment_lines": stubs,
        "exceptions": len(ex),
        "exceptions_by_code": dict(sorted(by_code.items())),
    }
    return {"summary": summary, "exceptions": sorted(ex, key=lambda e: (e["code"], e["id"]))}


def write_register(result: dict, out: str | Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Metric", "Value"])
    for k, v in result["summary"].items():
        ws.append([k, str(v) if isinstance(v, (dict, list, tuple)) else v])
    ws2 = wb.create_sheet("Exceptions")
    cols = ["code", "title", "label", "id", "detail", "sources", "refs"]
    ws2.append(cols)
    for e in result["exceptions"]:
        ws2.append([e.get(c, "") for c in cols])
    for w in (ws, ws2):
        for cell in w[1]:
            cell.font = Font(bold=True)
        for col in w.columns:
            width = min(80, max(12, max(len(str(c.value or "")) for c in col) + 2))
            w.column_dimensions[col[0].column_letter].width = width
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
