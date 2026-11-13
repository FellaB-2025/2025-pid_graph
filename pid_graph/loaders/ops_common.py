"""Shared helpers for the operations-document loaders (MADB, configuration export, SIL verification,
MOC register, document register).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

These documents add no label and no relationship (decision D-V13-12). What they say about a node
lands in source-named properties beside the design documents' own (`setpoint_madb`, `range_cfg`,
`pti_fe_silv` ...), the same pattern the SRS loader uses, so pid_graph.ops_checks can compare the
claims. A tag a document names that the graph does not have is reported, never invented, unless
the document is the owning source of that kind of thing (the MADB owns alarms; the configuration
owns configured points and alarms).
"""
from __future__ import annotations

import re
from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, classify, func_prefix

SPLIT_RE = re.compile(r"\s*[;,]\s*")


def prov(doc_no: str, rev: str, sheet: str, load_run: str, ref: str) -> dict:
    return {"source_doc": doc_no, "source_rev": rev, "source_sheet": sheet, "extracted_by": "table",
            "load_run": load_run, "source_ref": ref}


def document(store: MemoryStore, doc_no: str, rev: str, doc_type: str, title: str, unit: str, path: Path,
             load_run: str, **extra) -> dict:
    key = {"doc_no": doc_no, "rev": rev}
    existing = store.get_node("Document", key)
    props = {"doc_type": doc_type, "title": title, "unit": unit, "file": path.name, **extra,
             **prov(doc_no, rev, "", load_run, path.name)}
    store.merge_node("Document", key, props, stub=False if existing is None else existing["props"].get("stub", False))
    return key


def split_tags(value: str) -> list[str]:
    return [v for v in SPLIT_RE.split(str(value or "").strip()) if v]


def alarm_index(store) -> dict[str, str]:
    """alarm tag (PAH-1001) -> alarm_id (PT-1001A.PAH), for every Alarm that states its tag."""
    return {n["props"]["alarm_tag"]: n["key"]["alarm_id"] for n in store.nodes("Alarm") if n["props"].get("alarm_tag")}


def resolve(store, name: str) -> tuple[str, dict] | None:
    """A name a document uses -> (label, key) of the node it means, or None. Tries SIF, Alarm (by its own
    tag or id), Instrument, Equipment and Line, in that order. Never creates anything."""
    ident = canonical_id(name)
    if not ident:
        return None
    if store.has_node("SIF", {"sif_id": ident}):
        return "SIF", {"sif_id": ident}
    alarms = alarm_index(store)
    tag = canonical_tag(name) or ident
    if tag in alarms:
        return "Alarm", {"alarm_id": alarms[tag]}
    if store.has_node("Alarm", {"alarm_id": ident}):
        return "Alarm", {"alarm_id": ident}
    if store.has_node("Instrument", {"tag": tag}):
        return "Instrument", {"tag": tag}
    label, ident2 = classify(name)
    if label in ("Equipment", "Line"):
        key = {"line_no": ident2} if label == "Line" else {"tag": ident2}
        if store.has_node(label, key):
            return label, key
    return None


def ensure_instrument(store, tag: str, unit: str, p: dict, **props) -> bool:
    """Add a document's view of an instrument. Returns True if the tag was new (a stub: not in the index)."""
    existing = store.get_node("Instrument", {"tag": tag})
    if existing is not None:
        store.merge_node("Instrument", {"tag": tag}, {**props, **p}, stub=existing["props"].get("stub", False))
        return False
    store.merge_node("Instrument", {"tag": tag}, {"type": func_prefix(tag), "unit": unit, "stub_unit": unit, **props, **p},
                     stub=True)
    return True


def with_units(value, units) -> str:
    v, u = str(value or "").strip(), str(units or "").strip()
    return f"{v} {u}".strip() if v else ""
