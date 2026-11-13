"""Management-of-change register -> one Document node per MOC, linked to the tags it changes.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

A MOC record is a controlled document (doc_type MOC), so it is a Document node: doc_no = the MOC number,
rev = the register's revision it was read from. Each tag in "Tags Affected" that the graph has is
SHOWN_ON the MOC (basis "tags affected"); a tag the graph does not have (a proposed instrument) is kept in
`tags_not_in_graph`. The documents the MOC says must be revised, and those it says have been, are list
properties (`documents_to_revise`, `documents_revised`); `stage` is the status reduced to one of STAGES.
No new label or relationship (decision D-V13-12).
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id
from .ops_common import document, prov, resolve, split_tags
from .tables import MOC_ALIASES, detect_document, read_table

STAGES = ("proposed", "approved", "implemented", "closed", "cancelled")


def stage(status: str) -> str:
    s = (status or "").lower()
    for word, st in (("cancel", "cancelled"), ("implemented", "implemented"), ("closed", "closed"), ("approved", "approved")):
        if word in s:
            return st
    return "proposed"


def load_moc(store: MemoryStore, path: str | Path, *, unit: str, load_run: str, sheet: str | None = None) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, sheet)
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "mocs": 0, "links": 0, "tags_not_in_graph": [], "skipped": []}
    document(store, doc_no, rev, "MOC", f"Management of change register {doc_no}", unit, path, load_run)
    loops = {n["props"].get("loop") for n in store.nodes("Instrument") if n["props"].get("loop")}
    for r in read_table(path, sheet, MOC_ALIASES):
        ref = f"{path.name}:{sheet or 1}:{r['_row']}"
        moc = canonical_id(r.get("moc_no"))
        if not moc:
            report["skipped"].append({"ref": ref, "reason": "no MOC number"})
            continue
        p = prov(doc_no, rev, sheet or "", load_run, ref)
        missing, loops_named, links = [], [], []
        for t in split_tags(r.get("tags")):
            hit = resolve(store, t)
            if hit:
                links.append(hit)
            elif canonical_id(t) in loops:
                loops_named.append(canonical_id(t))        # a loop number: the register layer has no loop node
            else:
                missing.append(canonical_id(t))
        key = {"doc_no": moc, "rev": rev}
        store.merge_node("Document", key, {
            "doc_type": "MOC", "title": r.get("title", ""), "unit": unit, "change_type": r.get("change_type", ""),
            "status": r.get("status", ""), "stage": stage(r.get("status", "")), "raised": r.get("raised", ""),
            "approved": r.get("approved", ""), "implemented": r.get("implemented", ""), "closed": r.get("closed", ""),
            "documents_to_revise": split_tags(r.get("to_revise")), "documents_revised": split_tags(r.get("revised")),
            "tags_affected": split_tags(r.get("tags")), "tags_not_in_graph": missing, "loops_named": loops_named, "originator": r.get("originator", ""),
            "notes": r.get("notes", ""), "rev_basis": f"as recorded in {doc_no} Rev {rev}", **p})
        for label, k in links:
            store.merge_rel("SHOWN_ON", label, k, "Document", key, {**p, "basis": "tags affected"})
            report["links"] += 1
        report["tags_not_in_graph"] += [{"moc": moc, "tag": m} for m in missing]
        report["mocs"] += 1
    return report
