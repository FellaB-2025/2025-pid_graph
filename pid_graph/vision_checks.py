"""Reconciliation checks between the vision layer and the registers (PIDKG_UPGRADE.md, Phase 6).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The part neither tool has alone: pid-to-kg knows what is drawn, pid_graph knows what the index,
the C&E and pid_audit say. Each check compares the two and writes a row to the exception
register naming both sources. Nothing is corrected here and nothing is written to the graph.

  1. Tag check per sheet, index vs vision (T3): three regions - both, index only, vision only.
     The loader already raises X21 (vision only) and X22 (index only, on no sheet). This adds
     X30: the index places a tag on one drawing and vision found it only on another.
  2. Flow: FEEDS derived by walking FLOWS_TO from equipment to equipment, against the v1.2
     FEEDS from the pid_audit topology export. Disagreement on a line -> X31. The derived set is
     reported (derived = true, via_lines, via_items) but NOT written to the graph: an
     equipment-to-equipment FEEDS would shorten the "within two FEEDS hops" of the v1.2
     templates, and no v1.2 relationship may change meaning.
  3. An instrument's line per the index vs the line of the Segment vision put it on -> X32.
  4. Drawn trip signals vs the C&E (CQ18): a drawn trip with no INITIATES / ACTUATES pair -> X33;
     a C&E cause and effect with no drawn trip -> X34. Uses the loader's drawn_trips (drawn
     SIGNAL_TO with purpose = trip), not pid-to-kg's derived TRIPS.
  5. Valve fail position and actuator as drawn vs the index remark and instrument type -> X35.
  6. Loop membership as drawn vs the index loop column -> X36.

These checks read vision facts whatever their review state: they are how an engineer finds out
what to accept or reject, not a safety-relevant answer (trust rule T7 does not apply to them).
"""
from __future__ import annotations

import re

from .reconcile import TITLES
from .tags import canonical_tag

_FAIL = re.compile(r"\bfail\w*\s+(open|clos|last)", re.I)
_LOOP = re.compile(r"^(?:\d{2,4}-)?([A-Z])[A-Z]*-?(\d{2,6})[A-Z]{0,2}$")
_WORST = ("rejected", "pending", "accepted")


def fail_from_remark(remark) -> str | None:
    """'Fail close, partial stroke test' -> 'FC'. None when the remark says nothing about failure."""
    m = _FAIL.search(str(remark or ""))
    return {"open": "FO", "clos": "FC", "last": "FL"}[m.group(1).lower()] if m else None


def loop_key(loop) -> str | None:
    """Index loop number -> the key vision groups by: 'PIC-1005' -> 'P-1005' (first letter + number)."""
    m = _LOOP.match(str(loop or "").strip().upper().replace(" ", ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def pid_audit_feeds(store) -> dict[str, set]:
    """v1.2 FEEDS as equipment pairs per line: {line_no: {(from equipment, to equipment)}}. Vision FEEDS never count."""
    into: dict[str, set] = {}
    out_of: dict[str, set] = {}
    for r in store.rels("FEEDS"):
        if r["props"].get("extracted_by") not in ("pid_audit", "manual") or r["props"].get("derived"):
            continue
        if r["start_label"] == "Equipment" and r["end_label"] == "Line":
            into.setdefault(r["end_key"]["line_no"], set()).add(r["start_key"]["tag"])
        elif r["start_label"] == "Line" and r["end_label"] == "Equipment":
            out_of.setdefault(r["start_key"]["line_no"], set()).add(r["end_key"]["tag"])
    return {line: {(a, b) for a in into[line] for b in out_of[line]} for line in sorted(set(into) & set(out_of))}


def ce_pairs(store) -> dict[str, set]:
    """What the C&E says should trip what: {sif_id: {(initiator, final element)}}."""
    init: dict[str, set] = {}
    act: dict[str, set] = {}
    for r in store.rels("INITIATES"):
        init.setdefault(r["end_key"]["sif_id"], set()).add(r["start_key"]["tag"])
    for r in store.rels("ACTUATES"):
        act.setdefault(r["start_key"]["sif_id"], set()).add(r["end_key"]["tag"])
    return {sif: {(i, f) for i in init[sif] for f in act.get(sif, set())} for sif in sorted(init)}


def _end(r: dict, which: str) -> tuple:
    return r[f"{which}_label"], next(iter(r[f"{which}_key"].values()))


def derived_feeds(result: dict) -> list[dict]:
    """Equipment-level flow from the loaded FLOWS_TO: walk from each Equipment to the next one."""
    nxt: dict[tuple, list] = {}
    for r in result["rels"]:
        if r["type"] == "FLOWS_TO":
            nxt.setdefault(_end(r, "start"), []).append(r)
    seg_line = {n["key"]["segment_id"]: n["props"]["line_no"] for n in result["nodes"] if n["label"] == "Segment"}
    seg_review = {n["key"]["segment_id"]: n["props"]["review"] for n in result["nodes"] if n["label"] == "Segment"}
    out, seen = [], set()

    def walk(start, at, lines, items, off_page, reviews, visited):
        for r in nxt.get(at, []):
            to = _end(r, "end")
            if to in visited:
                continue
            rv = reviews + [r["props"]["review"]]
            op = off_page or r["props"].get("off_page") is True
            if to[0] == "Equipment":
                key = (start[1], to[1], tuple(lines))
                if key not in seen and lines:
                    seen.add(key)
                    out.append({"from": start[1], "to": to[1], "via_lines": list(lines), "via_items": list(items), "off_page": op,
                                "derived": True, "review": min(rv, key=_WORST.index)})
            elif to[0] == "Segment":
                line = seg_line.get(to[1], "")
                walk(start, to, lines if line in lines else lines + [line], items, op, rv + [seg_review.get(to[1], "pending")], visited | {to})
            else:
                walk(start, to, lines, items + [to[1]], op, rv, visited | {to})

    starts = sorted({_end(r, "start") for r in result["rels"] if r["type"] == "FLOWS_TO" and r["start_label"] == "Equipment"})
    for s in starts:
        walk(s, s, [], [], False, [], {s})
    return sorted(out, key=lambda f: (f["via_lines"], f["from"], f["to"]))


def run(pidkg_graph: dict, result: dict, store, index: set[str]) -> dict:
    """All six checks. result = load_pidkg.reconcile(...) for the same graph and store."""
    exceptions: list[dict] = []
    nodes = {n["id"]: n for n in pidkg_graph.get("nodes", [])}
    sheet_doc = {n["id"]: (n.get("attributes") or {}).get("drawing_number") for n in nodes.values() if n["type"] == "Sheet"}
    matched = set(result["pages"])

    def exc(code, label, ident, detail, sources):
        exceptions.append({"code": code, "title": TITLES[code], "label": label, "id": ident, "detail": detail, "sources": sources, "refs": ""})

    # ---- 1. tag check per sheet ---------------------------------------------------------
    interlocks = {e["id"] for e in result["exceptions"] if e["code"] == "X29"}
    vision: dict[str, set] = {d: set() for d in matched}
    for n in nodes.values():
        if n["type"] in ("Instrument", "Component") and n.get("tag") and n["tag"] not in interlocks:
            tag = canonical_tag(n["tag"]) or n["tag"]
            for s in n.get("sheets", []):
                if sheet_doc.get(s) in vision:
                    vision[sheet_doc[s]].add(tag)
    claimed: dict[str, set] = {d: set() for d in matched}
    for r in store.rels("SHOWN_ON"):
        doc = r["end_key"].get("doc_no")
        if r["start_label"] == "Instrument" and r["props"].get("extracted_by") == "table" and doc in claimed and r["start_key"]["tag"] in index:
            claimed[doc].add(r["start_key"]["tag"])
    tag_check = {d: {"both": sorted(claimed[d] & vision[d]), "index_only": sorted(claimed[d] - vision[d]),
                     "vision_only": sorted(vision[d] - claimed[d])} for d in sorted(matched)}
    for tag in sorted(index):
        says = sorted(d for d in matched if tag in claimed[d])
        found = sorted(d for d in matched if tag in vision[d])
        if says and found and not (set(says) & set(found)):
            exc("X30", "Instrument", tag, f"The index places it on {', '.join(says)}; vision found it on {', '.join(found)} only.", "pidkg_vision vs index")

    # ---- 2. derived FEEDS vs pid_audit FEEDS ---------------------------------------------
    feeds = derived_feeds(result)
    by_line: dict[str, set] = {}
    for f in feeds:
        by_line.setdefault(" + ".join(f["via_lines"]), set()).add((f["from"], f["to"]))
    audit = pid_audit_feeds(store)
    show = lambda pairs: ", ".join(f"{a} -> {b}" for a, b in sorted(pairs)) or "no equipment-to-equipment flow"
    for line in sorted(set(audit) | set(by_line)):
        a, v = audit.get(line, set()), by_line.get(line, set())
        if a != v:
            exc("X31", "Line", line, f"pid_audit: {show(a)}. Vision (walking FLOWS_TO): {show(v)}. Both kept; neither overwrites the other.",
                "pidkg_vision vs pid_audit")

    # ---- 3. instrument's line: index vs vision --------------------------------------------
    seg_line = {n["key"]["segment_id"]: n["props"]["line_no"] for n in result["nodes"] if n["label"] == "Segment"}
    vision_lines: dict[str, set] = {}
    for r in result["rels"]:
        if r["type"] in ("MEASURES", "INSTALLED_ON", "FLOWS_TO"):
            for me, other in (("start", "end"), ("end", "start")):
                if r[f"{me}_label"] == "Instrument" and r[f"{other}_label"] == "Segment":
                    vision_lines.setdefault(r[f"{me}_key"]["tag"], set()).add(seg_line.get(r[f"{other}_key"]["segment_id"], ""))
    index_line: dict[str, set] = {}
    for typ in ("MEASURES", "INSTALLED_ON"):
        for r in store.rels(typ):
            if r["props"].get("extracted_by") == "table" and r["end_label"] == "Line":
                index_line.setdefault(r["start_key"]["tag"], set()).add(r["end_key"]["line_no"])
    for tag in sorted(set(index_line) & set(vision_lines)):
        if not (index_line[tag] & vision_lines[tag]):
            exc("X32", "Instrument", tag, f"The index places it on {', '.join(sorted(index_line[tag]))}; vision put it on "
                f"{', '.join(sorted(vision_lines[tag]))}.", "pidkg_vision vs index")

    # ---- 4. drawn trips vs the C&E (CQ18) ---------------------------------------------------
    drawn = {(t["from"], t["to"]) for t in result["drawn_trips"]}
    pairs = ce_pairs(store)
    in_ce = {p for ps in pairs.values() for p in ps}
    via = {(t["from"], t["to"]): t for t in result["drawn_trips"]}
    for a, b in sorted(drawn - in_ce):
        t = via[(a, b)]
        how = f" through {t['via']}" + (f" ({t['via_name']})" if t["via_name"] else "") if t["via"] else ""
        exc("X33", "SIGNAL_TO", f"{a} -> {b}", f"A trip signal is drawn from {a} to {b}{how} on {t['sheet']}; the C&E has no SIF with {a} as a "
            f"cause and {b} as an effect.", "pidkg_vision vs cause_effect")
    for sif, ps in pairs.items():
        for a, b in sorted(ps - drawn):
            exc("X34", "SIF", f"{sif}: {a} -> {b}", f"The C&E has {a} initiating {sif} and {sif} actuating {b}; no trip signal is drawn "
                f"from {a} to {b} on the sheets vision read.", "pidkg_vision vs cause_effect")

    # ---- 5. fail position and actuator: drawn vs index ----------------------------------------
    inst = {n["key"]["tag"]: n["props"] for n in store.nodes("Instrument")}
    for n in nodes.values():
        tag = canonical_tag(n.get("tag")) if n["type"] == "Component" and n.get("tag") else None
        if not tag or tag not in index:
            continue
        a, p = n.get("attributes") or {}, inst.get(tag, {})
        said, drawn_fail = fail_from_remark(p.get("remarks")), str(a.get("fail_position") or "").upper() or None
        if said and drawn_fail and said != drawn_fail:
            exc("X35", "Instrument", tag, f"Drawn {drawn_fail}; the index remark says '{p.get('remarks')}' ({said}).", "pidkg_vision vs index")
        itype, actuator = str(p.get("instrument_type") or ""), str(a.get("actuator") or "")
        manual_in_index = "manual" in itype.lower()
        if itype and ((manual_in_index and actuator not in ("", "manual")) or (not manual_in_index and actuator == "manual")):
            exc("X35", "Instrument", tag, f"Drawn with actuator '{actuator}'; the index instrument type is '{itype}'.", "pidkg_vision vs index")

    # ---- 6. loop membership: drawn vs index ------------------------------------------------------
    vision_loops: dict[str, set] = {}
    for r in result["rels"]:
        if r["type"] == "MEMBER_OF":
            vision_loops.setdefault(r["start_key"]["tag"], set()).add(r["end_key"]["loop_key"])
    for tag in sorted(vision_loops):
        want = loop_key(inst.get(tag, {}).get("loop"))
        if want and want not in vision_loops[tag]:
            exc("X36", "Instrument", tag, f"Vision groups it into loop {', '.join(sorted(vision_loops[tag]))}; the index loop number is "
                f"{inst[tag]['loop']} ({want}).", "pidkg_vision vs index")

    by_code: dict[str, int] = {}
    for e in exceptions:
        by_code[e["code"]] = by_code.get(e["code"], 0) + 1
    exceptions.sort(key=lambda x: (int(x["code"][1:]), x["id"]))
    return {"exceptions": exceptions, "conflicts": [], "tag_check": tag_check, "derived_feeds": feeds,
            "summary": {"exceptions": len(exceptions), "exceptions_by_code": dict(sorted(by_code.items())),
                        "tag_check": tag_check, "derived_feeds": feeds}}


def print_report(checks: dict) -> None:
    for doc, t in checks["tag_check"].items():
        print(f"  tag check {doc}: both {len(t['both'])}, index only {t['index_only']}, vision only {t['vision_only']}")
    for f in checks["derived_feeds"]:
        print(f"  derived flow {f['from']} -> {f['to']} via {', '.join(f['via_lines'])}" + (" (off-page)" if f["off_page"] else "") + f" [{f['review']}]")
    print(f"  findings {checks['summary']['exceptions']} {checks['summary']['exceptions_by_code']}")
    for e in checks["exceptions"]:
        print(f"    {e['code']} {e['label']:<11} {e['id']:<30} {e['detail'][:110]}")
