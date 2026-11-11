"""pid_audit topology export -> INSTALLED_ON / FEEDS / SHOWN_ON edges.

Input: one row per flow adjacency walked along a line on a drawing
(sheet, from, to, line_no, confidence, verified). Instruments are not part of
the flow in the ontology (FEEDS is Line/Equipment only), so each row is decomposed:

  instrument side  -> INSTALLED_ON the row's line (or the equipment on the other side)
  equipment 'from' -> FEEDS the row's line;   line -> FEEDS equipment 'to'
  two equipment/line items with no line between them -> FEEDS directly

Tags seen on a drawing but absent from the index are created as stub Instruments
and reported (decisions section 2: never silently into the graph). Battery limits
and headers (BL-*, FLARE-HDR) are stub Equipment (decisions section 6).
"""
from __future__ import annotations

from pathlib import Path

from .. import ontology as O
from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag, classify, func_prefix, is_offpage, role
from .docs import pid_document
from .tables import TOPOLOGY_ALIASES, YES, read_table

LE = ("Line", "Equipment")


def _key(label: str, ident: str) -> dict:
    return {"line_no": ident} if label == "Line" else {"tag": ident}


def load_topology(store: MemoryStore, path: str | Path, *, unit: str, load_run: str,
                  extractor: str = "pid_audit", low_confidence: float = 0.75, rev_map: dict | None = None) -> dict:
    path = Path(path)
    rows = read_table(path, None, TOPOLOGY_ALIASES)
    report = {"file": path.name, "rows": len(rows), "skipped": [], "pid_only_instruments": [],
              "offpage_stubs": [], "unplaced": [], "low_confidence": [], "sheets": {}}

    def ensure(label: str, ident: str, prov: dict) -> None:
        key = _key(label, ident)
        existing = store.get_node(label, key)
        if existing is not None:
            store.merge_node(label, key, prov, stub=existing["props"].get("stub", False))
            return
        if label == "Instrument":
            store.merge_node(label, key, {"type": func_prefix(ident), "role": role(ident), "unit": unit,
                                          "stub_unit": unit, **prov}, stub=True)
            report["pid_only_instruments"].append({"tag": ident, "ref": prov["source_ref"], "sheet": prov["source_doc"]})
        elif label == "Equipment" and is_offpage(ident):
            store.merge_node(label, key, {"unit": unit, "stub_unit": unit, **prov}, stub=True)
            report["offpage_stubs"].append({"tag": ident, "ref": prov["source_ref"], "sheet": prov["source_doc"]})
        else:
            store.merge_node(label, key, {"unit": unit, **prov})

    for r in rows:
        ref = f"{path.name}:{r['_row']}"
        sheet = canonical_id(r.get("pid_sheet"))
        a_raw, b_raw = r.get("from_tag", ""), r.get("to_tag", "")
        if not sheet or not a_raw or not b_raw:
            report["skipped"].append({"ref": ref, "reason": "sheet, from or to is empty"})
            continue
        try:
            conf = float(r.get("confidence") or "nan")
        except ValueError:
            conf = float("nan")
        verified = r.get("verified", "").lower() in YES
        extracted_by = "manual" if verified else extractor
        rev = (rev_map or {}).get(sheet, O.UNKNOWN_REV)
        prov = {"source_doc": sheet, "source_rev": rev, "source_sheet": "", "extracted_by": extracted_by,
                "load_run": load_run, "source_ref": ref, "source_file": path.name}
        report["sheets"][sheet] = report["sheets"].get(sheet, 0) + 1
        doc_key = pid_document(store, sheet, rev_map=rev_map, unit=unit, prov=prov)

        la, a = classify(a_raw)
        lb, b = classify(b_raw)
        line = canonical_tag(r.get("via_line")) if r.get("via_line") else None
        if r.get("via_line") and (line is None or classify(line)[0] != "Line"):
            report["skipped"].append({"ref": ref, "reason": f"via_line {r['via_line']!r} is not a line number"})
            continue
        ensure(la, a, prov)
        ensure(lb, b, prov)
        if line:
            ensure("Line", line, prov)
        edge_props = {**prov, **({"confidence": conf} if conf == conf else {})}
        if conf == conf and conf < low_confidence and not verified:
            report["low_confidence"].append({"ref": ref, "sheet": sheet, "from": a, "to": b, "line": line or "", "confidence": conf})

        written = []
        if line:
            for lab, ident in ((la, a), (lb, b)):
                if lab == "Instrument":
                    store.merge_rel("INSTALLED_ON", "Instrument", {"tag": ident}, "Line", {"line_no": line}, edge_props)
                    written.append("INSTALLED_ON")
            if la in LE and a != line:
                store.merge_rel("FEEDS", la, _key(la, a), "Line", {"line_no": line}, edge_props)
                written.append("FEEDS")
            if lb in LE and b != line:
                store.merge_rel("FEEDS", "Line", {"line_no": line}, lb, _key(lb, b), edge_props)
                written.append("FEEDS")
        else:
            if la == "Instrument" and lb in LE:
                store.merge_rel("INSTALLED_ON", "Instrument", {"tag": a}, lb, _key(lb, b), edge_props)
            elif lb == "Instrument" and la in LE:
                store.merge_rel("INSTALLED_ON", "Instrument", {"tag": b}, la, _key(la, a), edge_props)
            elif la in LE and lb in LE:
                store.merge_rel("FEEDS", la, _key(la, a), lb, _key(lb, b), edge_props)
            else:
                report["unplaced"].append({"ref": ref, "from": a, "to": b,
                                           "reason": "two instruments with no line between them; no location edge possible"})
        for lab, ident in ((la, a), (lb, b), ("Line", line)):
            if ident:
                store.merge_rel("SHOWN_ON", lab, _key(lab, ident), "Document", doc_key, prov)
    return report
