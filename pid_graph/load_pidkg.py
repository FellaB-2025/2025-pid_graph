"""pid-to-kg graph.json -> pid_graph v1.3 segment topology (PIDKG_UPGRADE.md, Phase 4).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Vision proposes, the instrument index disposes, an engineer accepts. pid-to-kg (third party,
MIT, see THIRD_PARTY_NOTICES.md) reads the drawings and writes graph.json; this module reads
that file as an input and decides what is allowed into the graph. Nothing here is inferred:
what cannot be placed becomes an exception row with a reason.

    python -m pid_graph.load_pidkg --graph tests/fixtures/pidkg_U-100/graph.json \
           --pdf data/U100-PIDS-TX-0057.pdf --transmittal TX-0057            (dry run: prints, writes nothing)
    ... --apply                                                               (merges, writes graph_<unit>.json)
    python -m pid_graph --pidkg <graph.json> ...                              (the full pipeline with this loader on)

Mapping (pid-to-kg -> pid_graph v1.3):

  Sheet                      match an existing Document by drawing number + revision; none -> X23,
                             and nothing from that sheet is loaded
  Equipment (tagged)         existing, non-stub Equipment by tag; else X21 (T1)
  Boundary                   existing Equipment (battery limit / header) whose tag appears in the
                             flag text ("FEED GAS FROM BL-100" -> BL-100); none or several -> X24
  Instrument (tagged)        existing Instrument, if the tag is in the instrument index; else X21 (T1)
  Instrument (interlock)     an un-indexed symbol whose signals are all trips in and out (the I-1
                             diamond): no node; collapsed into direct trip signals; one X29 row
  Component with a tag       existing Instrument (valve), if in the index; else X21 (T1)
  Component without a tag    new InlineItem  <doc_no>.<local>
  PipeSegment                new Segment <line_no>.<k> + SEGMENT_OF its Line; k runs 1..n over the
                             sheets the line is drawn on; line not in the graph -> X25
  OffPageConnector           no node; a paired connector -> one FLOWS_TO with off_page=true;
                             unpaired -> X26
  ControlLoop                new ControlLoop (not the loop pid-to-kg builds around an interlock symbol)
  Plant                      skipped
  FLOWS_TO                   FLOWS_TO (flow_direction, off_page, confidence)
  MEASURES -> PipeSegment    MEASURES Instrument -> Segment
  MEASURES -> Equipment      compared with the index location: same -> skipped; different -> conflict
  SIGNAL_TO                  SIGNAL_TO; through an interlock symbol: initiator -> final element,
                             purpose trip, via = the symbol, via_name = what the notes call it
  MEMBER_OF                  MEMBER_OF, role mapped onto the closed list; other roles skipped
  FEEDS (derived)            not loaded; pid_graph derives its own in Phase 6
  ACTUATES, TRIPS,           skipped by design and counted. Never mapped onto pid_graph's own
  CASCADES_TO, PART_OF,      ACTUATES, CASCADES_TO, HAS_STATE or State. pid-to-kg's derived TRIPS
  anything else              groups by tag number and over-reaches; the Phase 6 drawing-vs-C&E
                             check uses result["drawn_trips"] (drawn trip signals) instead
  issues, sheet unreadable   X27, one row each (T6)

Also: an index instrument that vision did not find on any drawing it is SHOWN_ON -> X22 (T2).
Tags are normalised with pid_graph's own normaliser (tags.canonical_tag), not pid-to-kg's.
Every fact written carries extracted_by=pidkg_vision, review=pending (or the decision passed
in from the review register; a rejected fact is not written), confidence, fact_id and full
provenance. Existing v1.2 nodes are never created or re-witnessed by this loader, and the only
thing it adds to one is the informative pair dexpiClass / dexpiClass_source (Phase 10): the
DEXPI class pid-to-kg gave what it saw, and which drawing that came from. A different class
from another sheet is a recorded conflict, never an overwrite. Nothing reads dexpiClass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import ontology as O
from .records import Conflict, MemoryStore
from .tags import canonical_id, canonical_tag

ROOT = Path(__file__).resolve().parent.parent

TITLES = {
    "X21": "On P&ID (vision), not in the instrument index / equipment",
    "X22": "In the index, not found on the P&ID (vision)",
    "X23": "Vision sheet matches no drawing revision in the graph",
    "X24": "Vision boundary matches no battery limit / header",
    "X25": "Vision line is not a line in the graph",
    "X26": "Off-page connector not paired",
    "X27": "pid-to-kg QA issue or unreadable item",
    "X28": "Vision fact cannot be represented",
    "X29": "Interlock symbol collapsed into direct trip signals",
}
SKIPPED_BY_DESIGN = ("FEEDS", "ACTUATES", "TRIPS", "CASCADES_TO", "PART_OF")
ROLE_MAP = {"transmitter": "sensor", "element": "sensor", "sensor": "sensor", "switch": "sensor",
            "controller": "controller", "relay": "relay", "final_element": "final_element"}
NOT_STATED = "not stated"


def index_tags(store) -> set[str]:
    """The master list: Instruments the instrument index itself witnesses (SHOWN_ON a Document of type IDX)."""
    idx_docs = {tuple(d["key"].values()) for d in store.nodes("Document") if d["props"].get("doc_type") == "IDX"}
    return {r["start_key"]["tag"] for r in store.rels("SHOWN_ON")
            if r["start_label"] == "Instrument" and tuple(r["end_key"].values()) in idx_docs}


def fact_id(typ: str, frm: str, to: str, doc_no: str) -> str:
    """Stable id of one vision fact: type + endpoints + drawing. Survives a re-extraction."""
    return hashlib.sha1(f"{typ}|{frm}|{to}|{doc_no}".encode("utf-8")).hexdigest()[:12]


def _k(label: str, ident: str) -> dict:
    return {O.KEYS[label][0]: ident}


def reconcile(pidkg_graph: dict, index: set[str], existing_graph, *, unit: str, load_run: str,
              review: dict[str, str] | None = None) -> dict:
    """Pure: reads the two graphs, returns what would be written. See the module docstring."""
    review = review or {}
    nodes = {n["id"]: n for n in pidkg_graph.get("nodes", [])}
    edges = pidkg_graph.get("edges", [])
    pdf = (pidkg_graph.get("plant") or {}).get("source_file") or "pidkg"
    out_nodes: dict[tuple, dict] = {}
    out_rels: dict[tuple, dict] = {}
    exceptions: list[dict] = []
    conflicts: list[dict] = []
    skipped: dict[str, int] = {}
    seen: dict[str, set] = {}

    def skip(reason: str, n: int = 1) -> None:
        skipped[reason] = skipped.get(reason, 0) + n

    def exc(code, label, ident, detail, refs=""):
        row = {"code": code, "title": TITLES[code], "label": label, "id": ident, "detail": detail,
               "sources": "pidkg_vision vs index" if code in ("X21", "X22") else "pidkg_vision", "refs": refs}
        if row not in exceptions:
            exceptions.append(row)

    # ---- what already exists -------------------------------------------------
    docs = {(d["key"]["doc_no"], d["key"]["rev"]) for d in existing_graph.nodes("Document") if d["props"].get("doc_type") == "PID"}
    equipment = {n["key"]["tag"]: n["props"] for n in existing_graph.nodes("Equipment")}
    lines = {n["key"]["line_no"] for n in existing_graph.nodes("Line")}

    # ---- sheets ---------------------------------------------------------------
    sheet: dict[str, dict] = {}
    for n in nodes.values():
        if n["type"] != "Sheet":
            continue
        a = n.get("attributes", {})
        doc_no, rev = canonical_id(a.get("drawing_number")), str(a.get("revision") or "").strip().upper()
        ref = f"{pdf}:p{a.get('page')}"
        if (doc_no, rev) in docs:
            sheet[n["id"]] = {"doc_no": doc_no, "rev": rev, "page": a.get("page")}
        else:
            exc("X23", "Document", f"{doc_no} rev {rev or '?'}", "Vision read this title block; the graph holds no such drawing at that "
                "revision (run the title-block pass with the same PDF). Nothing from this sheet is loaded.", ref)
        for u in a.get("unreadable") or []:
            text = u.get("description") or u.get("note") or json.dumps(u) if isinstance(u, dict) else str(u)
            exc("X27", "Document", f"{doc_no} unreadable", f"pid-to-kg could not read: {text}", ref)
    for i in pidkg_graph.get("issues", []):
        exc("X27", "QA", str(i.get("node") or i.get("code")), f"pid-to-kg QA {i.get('severity')}: {i.get('code')} - {i.get('message')}", pdf)

    def home(n: dict) -> dict | None:
        """The matched sheet a node sits on (first of its sheets that matched)."""
        return next((sheet[s] for s in n.get("sheets", []) if s in sheet), None)

    def ref_of(n: dict, sh: dict) -> str:
        bbox = next((p.get("bbox") for p in n.get("provenance", []) if p.get("bbox")), None)
        return f"{pdf}:p{sh['page']}" + (f":bbox={','.join(str(v) for v in bbox)}" if bbox else "")

    def props(sh: dict, typ: str, frm: str, to: str, confidence, ref: str, **extra) -> dict | None:
        fid = fact_id(typ, frm, to, sh["doc_no"])
        decision = review.get(fid, "pending")
        if decision == "rejected":
            skip("rejected in the review register")
            return None
        return {"source_doc": sh["doc_no"], "source_rev": sh["rev"], "source_sheet": "", "extracted_by": O.VISION,
                "load_run": load_run, "source_ref": ref, "source_file": pdf, "confidence": float(confidence or 0.5),
                "review": decision, "fact_id": fid, **extra}

    # ---- interlock symbols: un-indexed, trips in and trips out -------------------
    signals = [e for e in edges if e["type"] == "SIGNAL_TO"]
    interlocks: set[str] = set()
    for n in nodes.values():
        if n["type"] != "Instrument" or (canonical_tag(n.get("tag")) or "") in index:
            continue
        ins = [e for e in signals if e["target"] == n["id"]]
        outs = [e for e in signals if e["source"] == n["id"]]
        if ins and outs and all((e.get("attributes") or {}).get("purpose") == "trip" for e in ins + outs):
            interlocks.add(n["id"])
    interlock_loops = {(nodes[i].get("attributes") or {}).get("loop_key") or nodes[i].get("tag") for i in interlocks}

    # ---- segment numbering: <line_no>.<k>, k = 1..n over the sheets the line is drawn on ----
    seg_key: dict[str, str] = {}
    by_line: dict[str, list] = {}
    for n in nodes.values():
        if n["type"] != "PipeSegment":
            continue
        sh = home(n)
        if sh is None:
            continue
        a = n.get("attributes", {})
        line_no = canonical_tag(a.get("line_number"))
        if line_no in lines:
            by_line.setdefault(line_no, []).append((sh["page"] or 0, str(a.get("line_id")), a.get("segment") or 0, n["id"]))
        else:
            shown = a.get("line_number") or f"{a.get('line_id')} (no number)"
            exc("X25", "Line", f"{sh['doc_no']} line {shown}", f"Vision drew a line ({a.get('size') or '?'} {a.get('service') or ''}) "
                "that is not a Line in the graph. Its segments and the fittings on it are not loaded.", f"{pdf}:p{sh['page']}")
    for line_no, segs in by_line.items():
        for k, (_, _, _, nid) in enumerate(sorted(segs), start=1):
            seg_key[nid] = f"{line_no}.{k}"

    # ---- node mapping -----------------------------------------------------------
    target: dict[str, tuple] = {}          # pid-to-kg id -> (label, ident) in pid_graph

    def note_seen(tag: str, n: dict) -> None:
        for s in n.get("sheets", []):
            if s in sheet:
                seen.setdefault(tag, set()).add(sheet[s]["doc_no"])

    for n in nodes.values():
        typ = n["type"]
        if typ in ("Sheet", "OffPageConnector"):
            continue
        if typ == "Plant":
            skip("Plant: skipped by design")
            continue
        sh = home(n)
        if sh is None:
            skip(f"{typ}: its sheet matched no drawing in the graph")
            continue
        if typ == "Equipment":
            tag = canonical_tag(n.get("tag")) or canonical_id(n.get("tag"))
            if tag in equipment and not equipment[tag].get("stub"):
                target[n["id"]] = ("Equipment", tag)
            else:
                exc("X21", "Equipment", tag or n["id"], f"Vision shows equipment {n.get('label')} on {sh['doc_no']}; "
                    "no register defines it. No node.", ref_of(n, sh))
        elif typ == "Boundary":
            name = n.get("name") or n.get("label") or ""
            hits = sorted({t for t in re.split(r"[^A-Z0-9\-]+", name.upper()) if t in equipment})
            if len(hits) == 1:
                target[n["id"]] = ("Equipment", hits[0])
            else:
                exc("X24", "Equipment", name, f"Boundary on {sh['doc_no']} names "
                    + ("no battery limit or header in the graph" if not hits else f"several: {', '.join(hits)}")
                    + ". No node; flow to or from it is not loaded.", ref_of(n, sh))
        elif typ in ("Instrument", "Component"):
            tag = canonical_tag(n.get("tag")) if n.get("tag") else None
            if n["id"] in interlocks:
                exc("X29", "Instrument", n.get("tag") or n["id"], f"Interlock symbol on {sh['doc_no']}"
                    + (f" ({n['name']})" if n.get("name") else "") + ": not an indexed device, so no node. Its trip signals are loaded "
                    "as direct initiator -> final element signals with via = this symbol.", ref_of(n, sh))
            elif tag and tag in index:
                target[n["id"]] = ("Instrument", tag)
                note_seen(tag, n)
            elif typ == "Component" and not n.get("tag"):
                local = n["id"].split(".", 1)[-1]
                target[n["id"]] = ("InlineItem", f"{sh['doc_no']}.{local}")
            else:
                ident = tag or n.get("tag") or n.get("label") or n["id"]
                exc("X21", "Instrument", ident, f"Vision shows {n.get('kind') or typ.lower()} {ident} on {sh['doc_no']}; "
                    "it has no instrument index row. No node, and no fact touching it is loaded.", ref_of(n, sh))
        elif typ == "PipeSegment":
            if n["id"] in seg_key:
                target[n["id"]] = ("Segment", seg_key[n["id"]])
        elif typ == "ControlLoop":
            key = n.get("label") or n["id"].split(":", 1)[-1]
            if key in interlock_loops:
                skip("ControlLoop: loop of a collapsed interlock symbol")
            else:
                target[n["id"]] = ("ControlLoop", key)
        else:
            skip(f"{typ}: skipped by design")

    # ---- T2: index instruments vision did not find on a drawing they are SHOWN_ON ----
    vision_docs = {s["doc_no"] for s in sheet.values()}
    shown_on: dict[str, set] = {}
    for r in existing_graph.rels("SHOWN_ON"):
        if r["start_label"] == "Instrument" and r["end_key"].get("doc_no") in vision_docs:
            shown_on.setdefault(r["start_key"]["tag"], set()).add(r["end_key"]["doc_no"])
    for tag in sorted(index):
        on = shown_on.get(tag, set())
        if on and not (seen.get(tag, set()) & on):
            exc("X22", "Instrument", tag, f"The registers place it on {', '.join(sorted(on))}; vision did not find it there.")

    # ---- new nodes ----------------------------------------------------------------
    def add_node(nid: str) -> None:
        label, ident = target[nid]
        if label not in ("Segment", "InlineItem", "ControlLoop") or (label, ident) in out_nodes:
            return
        n, sh = nodes[nid], home(nodes[nid])
        a = n.get("attributes", {})
        if label == "Segment":
            extra = {"line_no": ident.rsplit(".", 1)[0], "size": a.get("size") or NOT_STATED, "service": a.get("service") or NOT_STATED}
        elif label == "InlineItem":
            extra = {"kind": n.get("kind") or "other", "normal_position": a.get("normal_position") or NOT_STATED, "indexed": False}
            if n.get("dexpi_class"):
                extra["dexpiClass"] = n["dexpi_class"]
        else:
            extra = {"loop_type": a.get("loop_type") or n.get("kind") or NOT_STATED, "variable": a.get("variable") or NOT_STATED}
        p = props(sh, label, ident, "", n.get("confidence"), ref_of(n, sh), unit=unit, **extra)
        if p is not None:
            out_nodes[(label, ident)] = {"label": label, "key": _k(label, ident), "props": p}

    def add_rel(typ: str, a: tuple, b: tuple, sh: dict, confidence, **extra) -> bool:
        try:
            O.check_rel(typ, a[0], b[0])
        except O.SchemaViolation as e:
            exc("X28", typ, f"{a[1]} -> {b[1]}", f"Not representable in ontology v1.3: {e}", f"{pdf}:p{sh['page']}")
            return False
        p = props(sh, typ, f"{a[0]}:{a[1]}", f"{b[0]}:{b[1]}", confidence, f"{pdf}:p{sh['page']}", **extra)
        if p is None:
            return False
        out_rels.setdefault((typ, a, b, sh["doc_no"]), {"type": typ, "start_label": a[0], "start_key": _k(*a),
                                                        "end_label": b[0], "end_key": _k(*b), "props": p})
        return True

    def edge_sheet(e: dict, *fallback: str) -> dict | None:
        if e.get("sheet") in sheet:
            return sheet[e["sheet"]]
        return next((home(nodes[i]) for i in fallback if i in nodes and home(nodes[i])), None)

    # ---- off-page connectors: pair -> one FLOWS_TO --------------------------------
    opc = {n["id"] for n in nodes.values() if n["type"] == "OffPageConnector"}
    paired: set[str] = set()
    for e in edges:
        if e["type"] == "FLOWS_TO" and e["source"] in opc and e["target"] in opc:
            paired |= {e["source"], e["target"]}
            ups = [x for x in edges if x["type"] == "FLOWS_TO" and x["target"] == e["source"] and x["source"] not in opc]
            downs = [x for x in edges if x["type"] == "FLOWS_TO" and x["source"] == e["target"] and x["target"] not in opc]
            for u in ups:
                for d in downs:
                    sh = edge_sheet(u, u["source"])
                    if u["source"] in target and d["target"] in target and sh:
                        add_rel("FLOWS_TO", target[u["source"]], target[d["target"]], sh, e.get("confidence"),
                                flow_direction=(u.get("attributes") or {}).get("flow_direction") or "inferred", off_page=True)
                    else:
                        skip("FLOWS_TO: an end is not loaded")
    for nid in sorted(opc - paired):
        n = nodes[nid]
        sh = home(n)
        if sh:
            exc("X26", "Line", f"{sh['doc_no']} {n.get('label')}", "Off-page connector with no partner on the sheets supplied. "
                "The flow across it is not loaded.", ref_of(n, sh))

    # ---- relationships --------------------------------------------------------------
    existing_location: dict[str, set] = {}
    for typ in ("MEASURES", "INSTALLED_ON"):
        for r in existing_graph.rels(typ):
            if r["props"].get("extracted_by") == "table":
                existing_location.setdefault(r["start_key"]["tag"], set()).add((r["end_label"], tuple(r["end_key"].values())[0]))

    drawn_trips: list[dict] = []
    for e in edges:
        typ, s, t = e["type"], e["source"], e["target"]
        a = e.get("attributes") or {}
        if typ in SKIPPED_BY_DESIGN or typ not in ("FLOWS_TO", "MEASURES", "SIGNAL_TO", "MEMBER_OF"):
            skip(f"{typ}: skipped by design")
            continue
        if typ == "FLOWS_TO":
            if s in opc or t in opc:
                continue                                         # handled above
            sh = edge_sheet(e, s, t)
            if s in target and t in target and sh:
                add_rel("FLOWS_TO", target[s], target[t], sh, e.get("confidence"),
                        flow_direction=a.get("flow_direction") or "inferred", off_page=False)
            else:
                skip("FLOWS_TO: an end is not loaded")
        elif typ == "MEASURES":
            sh = edge_sheet(e, s, t)
            if s not in target or t not in target or not sh or target[s][0] != "Instrument":
                skip("MEASURES: an end is not loaded")
            elif target[t][0] == "Segment":
                add_rel("MEASURES", target[s], target[t], sh, e.get("confidence"))
            elif target[t][0] == "Equipment":
                known = existing_location.get(target[s][1], set())
                if target[t] in known:
                    skip("MEASURES on Equipment: agrees with the index")
                elif known:
                    conflicts.append({"label": "Instrument", "key": {"tag": target[s][1]}, "prop": "MEASURES",
                                      "existing": ", ".join(sorted(f"{lab} {i}" for lab, i in known)), "incoming": f"Equipment {target[t][1]}",
                                      "existing_source": "instrument index", "incoming_source": f"{sh['doc_no']} (pidkg_vision)"})
                else:
                    skip("MEASURES on Equipment: the index gives no location to compare")
            else:
                skip("MEASURES: target is not a Segment or Equipment")
        elif typ == "SIGNAL_TO":
            if s in interlocks or t in interlocks:
                continue                                         # handled below
            sh = edge_sheet(e, s, t)
            if s in target and t in target and sh:
                purpose = a.get("purpose") if a.get("purpose") in O.SIGNAL_PURPOSES else "unknown"
                ok = add_rel("SIGNAL_TO", target[s], target[t], sh, e.get("confidence"), signal_type=a.get("signal_type") or NOT_STATED, purpose=purpose)
                if ok and purpose == "trip":                 # a trip drawn straight from initiator to final element
                    drawn_trips.append({"from": target[s][1], "to": target[t][1], "via": "", "via_name": "", "sheet": sh["doc_no"]})
            else:
                skip("SIGNAL_TO: an end is not loaded")
        elif typ == "MEMBER_OF":
            role = ROLE_MAP.get(a.get("role"))
            if t not in target:
                skip("MEMBER_OF: its loop is not loaded")
            elif s not in target or target[s][0] != "Instrument":
                skip("MEMBER_OF: the member is not loaded")
            elif role is None:
                skip("MEMBER_OF: role not in the closed list")
            else:
                sh = edge_sheet(e, s, t)
                if sh:
                    add_rel("MEMBER_OF", target[s], target[t], sh, e.get("confidence"), role=role)

    for i in sorted(interlocks):
        n = nodes[i]
        ins = [e for e in signals if e["target"] == i]
        outs = [e for e in signals if e["source"] == i]
        for u in ins:
            for d in outs:
                sh = edge_sheet(u, u["source"], i)
                if u["source"] in target and d["target"] in target and sh:
                    ok = add_rel("SIGNAL_TO", target[u["source"]], target[d["target"]], sh, min(u.get("confidence") or 0.5, d.get("confidence") or 0.5),
                                 signal_type=(u.get("attributes") or {}).get("signal_type") or NOT_STATED, purpose="trip",
                                 via=n.get("tag") or i, via_name=n.get("name") or "")
                    if ok:
                        drawn_trips.append({"from": target[u["source"]][1], "to": target[d["target"]][1], "via": n.get("tag") or i,
                                            "via_name": n.get("name") or "", "sheet": sh["doc_no"]})
                else:
                    skip("SIGNAL_TO: an end is not loaded")

    # ---- nodes: only those a loaded relationship touches; each SHOWN_ON its drawing ----
    touched = {end for (_, a, b, _) in out_rels for end in (a, b)}
    for nid, tgt in target.items():
        if tgt[0] == "Segment":
            add_node(nid)
            if tgt in out_nodes:
                add_rel("SEGMENT_OF", tgt, ("Line", tgt[1].rsplit(".", 1)[0]), home(nodes[nid]), nodes[nid].get("confidence"))
        elif tgt[0] in ("InlineItem", "ControlLoop"):
            if tgt in touched:
                add_node(nid)
            else:
                skip(f"{tgt[0]}: no loaded relationship touches it")
    # a relationship whose new end was rejected in review cannot stand
    for key in [k for k, r in out_rels.items() if any(end[0] in ("Segment", "InlineItem", "ControlLoop") and end not in out_nodes for end in (k[1], k[2]))]:
        del out_rels[key]
        skip("relationship dropped: an end was rejected in review")
    for (label, ident), node in list(out_nodes.items()):
        p = dict(node["props"])
        fid = fact_id("SHOWN_ON", f"{label}:{ident}", f"Document:{p['source_doc']}", p["source_doc"])
        shown = {k: p[k] for k in ("source_doc", "source_rev", "extracted_by", "load_run", "source_ref", "source_file", "confidence", "review")}
        out_rels[("SHOWN_ON", (label, ident), ("Document", p["source_doc"]), p["source_doc"])] = {
            "type": "SHOWN_ON", "start_label": label, "start_key": _k(label, ident), "end_label": "Document",
            "end_key": {"doc_no": p["source_doc"], "rev": p["source_rev"]}, "props": {**shown, "fact_id": fid}}

    by_code: dict[str, int] = {}
    for x in exceptions:
        by_code[x["code"]] = by_code.get(x["code"], 0) + 1
    by_label: dict[str, int] = {}
    for n in out_nodes.values():
        by_label[n["label"]] = by_label.get(n["label"], 0) + 1
    by_rel: dict[str, int] = {}
    for r in out_rels.values():
        by_rel[r["type"]] = by_rel.get(r["type"], 0) + 1
    summary = {"source": pidkg_graph.get("generator"), "file": pdf, "sheets_matched": sorted(s["doc_no"] for s in sheet.values()),
               "nodes": len(out_nodes), "nodes_by_label": dict(sorted(by_label.items())),
               "rels": len(out_rels), "rels_by_type": dict(sorted(by_rel.items())),
               "exceptions": len(exceptions), "exceptions_by_code": dict(sorted(by_code.items())),
               "conflicts": len(conflicts), "skipped": dict(sorted(skipped.items())), "drawn_trips": len(drawn_trips)}
    # Where vision saw each mapped thing, for the review markup: "Label ident" -> drawing, page, bbox (0..1 of the page).
    locations: dict[str, dict] = {}
    for nid, (label, ident) in target.items():
        n, sh = nodes[nid], home(nodes[nid])
        bbox = next((p.get("bbox") for p in n.get("provenance", []) if p.get("bbox") and p.get("sheet") in sheet
                     and sheet[p["sheet"]]["doc_no"] == sh["doc_no"]), None)
        if bbox:
            locations.setdefault(f"{label} {ident}", {"doc_no": sh["doc_no"], "page": sh["page"], "bbox": list(bbox)})
    # DEXPI class (informative): onto the existing Equipment / Instrument nodes vision saw, and listed where it gave none.
    node_props, no_class = [], []
    for nid, (label, ident) in target.items():
        n = nodes[nid]
        if label == "InlineItem" or (label in ("Equipment", "Instrument") and n["type"] in ("Equipment", "Instrument", "Component")):
            if not n.get("dexpi_class"):
                no_class.append(f"{label} {ident}")
            elif label != "InlineItem":
                node_props.append({"label": label, "key": _k(label, ident),
                                   "props": {"dexpiClass": n["dexpi_class"], "dexpiClass_source": f"{O.VISION} {home(n)['doc_no']}"}})
    summary["dexpi_classes"] = len(node_props)
    summary["no_dexpi_class"] = sorted(no_class)
    return {"node_props": node_props, "no_dexpi_class": sorted(no_class),
            "locations": locations, "pages": {s["doc_no"]: s["page"] for s in sheet.values()},
            "nodes": list(out_nodes.values()), "rels": list(out_rels.values()),
            "exceptions": sorted(exceptions, key=lambda x: (int(x["code"][1:]), x["id"])), "conflicts": conflicts,
            "skipped": dict(sorted(skipped.items())), "seen": {t: sorted(d) for t, d in sorted(seen.items())},
            "drawn_trips": drawn_trips, "summary": summary}


def apply(store: MemoryStore, result: dict) -> dict:
    """Merge a reconcile() result into the store. Idempotent: MERGE semantics, conflicts added once."""
    for n in result["nodes"]:
        store.merge_node(n["label"], n["key"], n["props"])
    for r in result["rels"]:
        store.merge_rel(r["type"], r["start_label"], r["start_key"], r["end_label"], r["end_key"], r["props"])
    for x in result.get("node_props", []):
        node = store.get_node(x["label"], x["key"])
        if node is None:
            continue
        p, new = node["props"], x["props"]
        if not p.get("dexpiClass"):
            p.update(new)                                    # informative only; the node's own provenance is not touched
        elif p["dexpiClass"] != new["dexpiClass"]:
            c = Conflict(x["label"], dict(x["key"]), "dexpiClass", str(p["dexpiClass"]), str(new["dexpiClass"]),
                         str(p.get("dexpiClass_source", "")), new["dexpiClass_source"])
            if c not in store.conflicts:
                store.conflicts.append(c)
    have = {json.dumps(c.__dict__, sort_keys=True, default=str) for c in store.conflicts}
    for c in result["conflicts"]:
        if json.dumps(c, sort_keys=True, default=str) not in have:
            store.conflicts.append(Conflict(**c))
    return {"nodes": len(result["nodes"]), "rels": len(result["rels"]), "conflicts": len(result["conflicts"])}


def report_only(pidkg_graph: dict) -> dict:
    """What an extraction holds, with no master list and no graph to reconcile against (Phase 9).

    For drawings of a plant pid_graph has no registers for. Nothing is mapped, gated or written:
    this only counts what pid-to-kg produced, its own QA issues, and how much of it trust rule T5
    would send to priority review if it were loaded (confidence < 0.85, inferred flow direction,
    off-page, or touching an untagged fitting)."""
    nodes = {n["id"]: n for n in pidkg_graph.get("nodes", [])}
    edges = pidkg_graph.get("edges", [])
    count = lambda items, key: dict(sorted(_tally(key(x) for x in items).items()))
    attr = lambda n: n.get("attributes") or {}
    sheets = [{"drawing_number": attr(n).get("drawing_number"), "revision": attr(n).get("revision"), "page": attr(n).get("page"),
               "unreadable": len(attr(n).get("unreadable") or []), "tiles_reviewed": len(attr(n).get("tiles_reviewed") or [])}
              for n in nodes.values() if n["type"] == "Sheet"]
    untagged = {n["id"] for n in nodes.values() if n["type"] == "Component" and not n.get("tag")}
    opc = {n["id"] for n in nodes.values() if n["type"] == "OffPageConnector"}
    paired = {x for e in edges if e["type"] == "FLOWS_TO" and e["source"] in opc and e["target"] in opc for x in (e["source"], e["target"])}
    segs = [n for n in nodes.values() if n["type"] == "PipeSegment"]
    low = lambda x: ["low_confidence"] if float(x.get("confidence") or 0) < 0.85 else []
    # the facts pid_graph would hold as vision facts, each with its T5 flags
    flags_per_fact: list[list[str]] = []
    for n in nodes.values():
        if n["type"] in ("PipeSegment", "ControlLoop") or n["id"] in untagged:
            flags_per_fact.append(low(n) + (["inline_item"] if n["id"] in untagged else []))
    for e in edges:
        a = attr(e)
        if e["type"] not in ("FLOWS_TO", "MEASURES", "SIGNAL_TO", "MEMBER_OF"):
            continue
        if e["type"] == "FLOWS_TO" and (e["source"] in opc) != (e["target"] in opc):
            continue                                           # a hop into or out of a connector is not a fact of its own
        flags_per_fact.append(low(e) + (["inferred_direction"] if a.get("flow_direction") == "inferred" else [])
                              + (["off_page"] if a.get("off_page") else [])
                              + (["inline_item"] if e["source"] in untagged or e["target"] in untagged else []))
    facts, flagged = len(flags_per_fact), sum(1 for f in flags_per_fact if f)
    issues = pidkg_graph.get("issues", [])
    scored = [x for x in list(nodes.values()) + edges if not x.get("derived") and x.get("type") not in ("Sheet", "Plant")]
    return {"generator": pidkg_graph.get("generator"), "plant": (pidkg_graph.get("plant") or {}).get("name"),
            "source_file": (pidkg_graph.get("plant") or {}).get("source_file"), "sheets": sorted(sheets, key=lambda x: x["page"] or 0),
            "nodes": len(nodes), "nodes_by_type": count(nodes.values(), lambda n: n["type"]),
            "relationships": len(edges), "relationships_by_type": count(edges, lambda e: e["type"]),
            "tagged": {"equipment": sum(1 for n in nodes.values() if n["type"] == "Equipment" and n.get("tag")),
                       "instruments": sum(1 for n in nodes.values() if n["type"] == "Instrument" and n.get("tag")),
                       "instruments_untagged": sum(1 for n in nodes.values() if n["type"] == "Instrument" and not n.get("tag")),
                       "components": sum(1 for n in nodes.values() if n["type"] == "Component" and n.get("tag")),
                       "components_untagged": len(untagged)},
            "segments": {"total": len(segs), "on_a_numbered_line": sum(1 for n in segs if attr(n).get("line_number"))},
            "off_page_connectors": {"total": len(opc), "paired": len(paired), "unpaired": len(opc - paired)},
            "unreadable": sum(x["unreadable"] for x in sheets),
            "qa_issues": {"total": len(issues), "by_severity": count(issues, lambda i: i.get("severity")), "by_code": count(issues, lambda i: i.get("code"))},
            "confidence": count(scored, lambda x: "%.2f" % float(x.get("confidence") or 0)),
            "t5": {"facts": facts, "flagged": flagged, "flag_rate": round(flagged / facts, 3) if facts else None,
                   "by_flag": dict(sorted(_tally(f for fs in flags_per_fact for f in fs).items()))},
            "applied": False}


def _tally(values) -> dict:
    out: dict = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def print_report_only(r: dict) -> None:
    print(f"  {r['generator']} on {r['source_file']} ({r['plant']}); {len(r['sheets'])} sheet(s)")
    for s in r["sheets"]:
        print(f"    page {s['page']}: {s['drawing_number']} rev {s['revision']}  tiles read {s['tiles_reviewed']}  unreadable {s['unreadable']}")
    print(f"  nodes {r['nodes']} {r['nodes_by_type']}")
    print(f"  relationships {r['relationships']} {r['relationships_by_type']}")
    print(f"  tagged {r['tagged']}")
    print(f"  segments {r['segments']}; off-page connectors {r['off_page_connectors']}; unreadable items {r['unreadable']}")
    print(f"  QA issues {r['qa_issues']['total']} {r['qa_issues']['by_severity']} {r['qa_issues']['by_code']}")
    print(f"  confidence {r['confidence']}")
    print(f"  T5: {r['t5']['flagged']} of {r['t5']['facts']} facts would be flagged for priority review ({r['t5']['flag_rate']}) {r['t5']['by_flag']}")
    print("  REPORT ONLY: no master list, nothing reconciled, nothing applied.")


def print_report(result: dict) -> None:
    s = result["summary"]
    print(f"  source {s['source']} on {s['file']}; sheets matched {s['sheets_matched']}")
    print(f"  would write {s['nodes']} nodes {s['nodes_by_label']}")
    print(f"              {s['rels']} relationships {s['rels_by_type']}")
    print(f"  exceptions {s['exceptions']} {s['exceptions_by_code']}; conflicts {s['conflicts']}; drawn trips {s['drawn_trips']}")
    for reason, n in s["skipped"].items():
        print(f"    skipped {n:>3}  {reason}")
    for e in result["exceptions"]:
        print(f"    {e['code']} {e['label']:<11} {e['id']:<30} {e['detail'][:110]}")


def main(argv=None) -> int:
    from .pipeline import build_store, new_load_run
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True, help="pid-to-kg graph.json")
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--index", default=str(ROOT / "data" / "U100-INST-INDEX-Rev-B.xlsx"))
    ap.add_argument("--topology", default=str(ROOT / "data" / "pid_audit_U100_topology.csv"))
    ap.add_argument("--ce", default=str(ROOT / "data" / "U100-CE-CHART-Rev-A.xlsx"))
    ap.add_argument("--srs", default=str(ROOT / "data" / "U100-SRS-001-Rev-B.xlsx"))
    ap.add_argument("--lopa", default=str(ROOT / "data" / "U100-LOPA-001-Rev-A.xlsx"))
    ap.add_argument("--curated", default=str(ROOT / "data" / "curated" / "compensating_measures_U-100.csv"))
    ap.add_argument("--pdf", default=None, help="the P&ID PDF the extraction was made from; its title blocks give the revisions")
    ap.add_argument("--transmittal", default=None)
    ap.add_argument("--load-run", default=None)
    ap.add_argument("--apply", action="store_true", help="merge into the staged graph and write graph_<unit>.json (default: dry run)")
    ap.add_argument("--no-master", action="store_true", help="the plant has no instrument index here; only with --report-only")
    ap.add_argument("--report-only", action="store_true", help="count what the extraction holds; reconcile and apply nothing; only with --no-master")
    ap.add_argument("--report-json", default="", help="with --report-only: also write the report to this file")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.no_master != a.report_only:
        ap.error("--no-master and --report-only go together: without a master list nothing can be reconciled or applied, only counted")
    if a.report_only:
        if a.apply:
            ap.error("--report-only never applies anything; drop --apply")
        rep = report_only(json.loads(Path(a.graph).read_text(encoding="utf-8")))
        print("load_pidkg REPORT ONLY (no master list)")
        print_report_only(rep)
        if a.report_json:
            Path(a.report_json).parent.mkdir(parents=True, exist_ok=True)
            Path(a.report_json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
            print(f"  -> {a.report_json}")
        return 0
    load_run = a.load_run or new_load_run(a.transmittal or "run")
    store, _ = build_store(unit=a.unit, index=a.index, topology=a.topology, load_run=load_run, ce=a.ce or None, pdf=a.pdf,
                           transmittal=a.transmittal, curated=a.curated or None, srs=a.srs or None, lopa=a.lopa or None)
    graph = json.loads(Path(a.graph).read_text(encoding="utf-8"))
    result = reconcile(graph, index_tags(store), store, unit=a.unit, load_run=load_run)
    print(f"load_pidkg {'APPLY' if a.apply else 'DRY RUN (nothing written; --apply to write)'}  unit {a.unit}  load_run {load_run}")
    print_report(result)
    from . import vision_checks as VC
    VC.print_report(VC.run(graph, result, store, index_tags(store)))
    if a.apply:
        apply(store, result)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"graph_{a.unit}.json"
        path.write_text(json.dumps(store.to_dict(), indent=1, default=str), encoding="utf-8")
        c = store.counts()
        print(f"  staged graph now {c['nodes']} nodes / {c['rels']} relationships -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
