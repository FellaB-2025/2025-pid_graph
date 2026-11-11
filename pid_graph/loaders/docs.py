"""Shared helper: reference a P&ID Document from a loader.

If the title-block pass has registered the drawing, its real revision is used and
the node is not a stub. Otherwise the reference gets rev UNKNOWN and a stub node
(decision D-P1-03) that the next title-block pass replaces.
"""
from __future__ import annotations

from .. import ontology as O
from ..records import MemoryStore


def pid_document(store: MemoryStore, doc_no: str, *, rev_map: dict | None, unit: str, prov: dict) -> dict:
    rev = (rev_map or {}).get(doc_no, O.UNKNOWN_REV)
    key = {"doc_no": doc_no, "rev": rev}
    existing = store.get_node("Document", key)
    if existing is not None:
        store.merge_node("Document", key, prov, stub=existing["props"].get("stub", False))
    else:
        store.merge_node("Document", key, {"doc_type": "PID", "unit": unit, "stub_unit": unit, **prov},
                         stub=(rev == O.UNKNOWN_REV))
    return key
