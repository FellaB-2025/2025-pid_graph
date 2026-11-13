"""Document register -> a Document node for every controlled document of the unit, linked to what it covers.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

This is how documents nobody parses (operating procedures, proof-test procedures, loop drawings, the alarm
philosophy, the SIS I/O allocation) still answer "where is this tag?": the register's Covers column names
the tags, SIFs and alarms each document deals with, and each one the graph has gets SHOWN_ON that document
(basis "document register: covers"). Load it last, after every register that creates nodes. Names that are
systems rather than graph nodes (a logic solver, a DCS controller, the unit itself) are skipped and listed;
any other name the graph does not have is reported (check C1).
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id
from .ops_common import prov, resolve, split_tags
from .tables import DOCREG_ALIASES, detect_document, read_table

TYPE_MAP = {"srs": "SRS", "lopa": "LOPA", "sil verification": "SILV", "c&e": "CE", "instrument index": "IDX",
            "alarm philosophy": "PHIL", "operating procedure": "PROC", "sis bypass procedure": "PROC",
            "proof test procedure": "PTP", "loop drawing": "LOOP", "sis logic": "SISIO", "madb": "MADB",
            "configuration export": "CFG", "moc register": "MOC", "p&id": "PID", "document register": "REG"}


def _systems(store, unit: str) -> set[str]:
    out = {canonical_id(unit)}
    for n in store.nodes("SIF"):
        out |= {canonical_id(n["props"].get(k, "")) for k in ("logic_solver", "logic_solver_srs", "logic_solver_cfg")}
    for n in store.nodes("Instrument"):
        out.add(canonical_id(n["props"].get("controller_cfg", "")))
    return out - {""}


def load_docreg(store: MemoryStore, path: str | Path, *, unit: str, load_run: str) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "documents": 0, "links": 0, "systems": [], "unresolved": [], "unknown_types": []}
    reg_key = {"doc_no": doc_no, "rev": rev}
    store.merge_node("Document", reg_key, {"doc_type": "REG", "title": f"Document register {doc_no}", "unit": unit,
                                           "file": path.name, **prov(doc_no, rev, "", load_run, path.name)})
    systems = _systems(store, unit)
    for r in read_table(path, None, DOCREG_ALIASES):
        ref = f"{path.name}:{r['_row']}"
        d_no, d_rev = canonical_id(r.get("doc_no")), (r.get("rev") or "").strip().upper()
        if not d_no or not d_rev:
            report["unresolved"].append({"ref": ref, "name": d_no, "reason": "row has no document number or revision"})
            continue
        dtype = TYPE_MAP.get((r.get("type") or "").strip().lower())
        if dtype is None:
            report["unknown_types"].append({"ref": ref, "type": r.get("type")})
            dtype = "REG"
        p = prov(doc_no, rev, "", load_run, ref)
        key = {"doc_no": d_no, "rev": d_rev}
        ex = store.get_node("Document", key)
        props = {"doc_type": dtype, "title": r.get("title", ""), "unit": unit, "registered": "yes", "register_ref": ref}
        if ex is None:
            store.merge_node("Document", key, {**props, **p})
        else:                                   # a loaded document: add the register's facts, keep its own provenance
            store.merge_node("Document", key, {k: v for k, v in props.items() if k not in ex["props"]} | p,
                             stub=ex["props"].get("stub", False))
        report["documents"] += 1
        for name in split_tags(r.get("covers")):
            if canonical_id(name) in systems:
                report["systems"].append({"doc_no": d_no, "name": canonical_id(name)})
                continue
            hit = resolve(store, name)
            if hit is None:
                report["unresolved"].append({"ref": ref, "doc_no": d_no, "name": canonical_id(name),
                                             "reason": "covered by the document but not in the graph"})
                continue
            store.merge_rel("SHOWN_ON", hit[0], hit[1], "Document", key, {**p, "basis": "document register: covers"})
            report["links"] += 1
    return report
