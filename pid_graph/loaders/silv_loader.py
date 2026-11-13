"""SIL verification -> what the calculation assumed, on the SIF nodes.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Per SIF: `sil_target_silv`, `rrf_target_silv`, `target_source_silv` (the document and revision the target was
taken from), `pfd_avg_silv`, `rrf_achieved_silv`, `sil_achieved_silv`, `sensor_tags_silv`,
`sensor_voting_silv`, `fe_tags_silv`, `fe_voting_silv`, `pti_sensors_silv`, `pti_fe_silv`, `result_silv`, and
from the degraded-operation sheet `degraded_sensor_voting_silv` / `degraded_fe_voting_silv` and a readable
`degraded_silv` list. Instruments the calculation names are linked to the document (SHOWN_ON); one the
graph does not have is reported in `unknown_tags` and not created: a calculation does not install anything.
"""
from __future__ import annotations

from pathlib import Path

from ..records import MemoryStore
from ..tags import canonical_id, canonical_tag
from .ops_common import document, prov, split_tags
from .tables import SILV_DEGRADED_ALIASES, SILV_SUMMARY_ALIASES, detect_document, read_table, sheet_names


def load_silv(store: MemoryStore, path: str | Path, *, unit: str, load_run: str) -> dict:
    path = Path(path)
    doc_no, rev, how = detect_document(path, "SIF Summary")
    report = {"file": path.name, "document": {"doc_no": doc_no, "rev": rev, "detected_from": how},
              "sifs": 0, "unknown_tags": [], "skipped": []}
    doc_key = document(store, doc_no, rev, "SILV", f"SIL verification {doc_no}", unit, path, load_run)
    degraded: dict[str, list[dict]] = {}
    if "Degraded Operation" in sheet_names(path):
        for r in read_table(path, "Degraded Operation", SILV_DEGRADED_ALIASES):
            degraded.setdefault(canonical_id(r.get("sif_id")), []).append(r)
    for r in read_table(path, "SIF Summary", SILV_SUMMARY_ALIASES):
        ref = f"{path.name}:SIF Summary:{r['_row']}"
        sif = canonical_id(r.get("sif_id"))
        node = store.get_node("SIF", {"sif_id": sif})
        if node is None:
            report["skipped"].append({"ref": ref, "reason": f"SIF {sif} not in the graph"})
            continue
        p = prov(doc_no, rev, "SIF Summary", load_run, ref)
        deg = degraded.get(sif, [])
        sensors = set(split_tags(r.get("sensor_tags")))
        props = {"sil_target_silv": r.get("sil_target", ""), "rrf_target_silv": r.get("rrf_target", ""),
                 "target_source_silv": r.get("target_source", ""), "pfd_avg_silv": r.get("pfd_avg", ""),
                 "rrf_achieved_silv": r.get("rrf_achieved", ""), "sil_achieved_silv": r.get("sil_achieved", ""),
                 "sensor_tags_silv": r.get("sensor_tags", ""), "sensor_voting_silv": r.get("sensor_voting", ""),
                 "fe_tags_silv": r.get("fe_tags", ""), "fe_voting_silv": r.get("fe_voting", ""),
                 "pti_sensors_silv": r.get("pti_sensors", ""), "pti_fe_silv": r.get("pti_fe", ""),
                 "result_silv": r.get("result", ""), "silv_ref": ref,
                 "degraded_silv": [f"{d['element']} bypassed: {d.get('degraded_voting') or 'function lost'}"
                                   + (f", PFDavg {d['pfd']}, SIL {d['sil']}" if d.get("pfd") else "") for d in deg]}
        for d in deg:
            # "One of PT-1001A/B/C" or "PT-1001D" names the sensors; "XV-1001 or BDV-1001" the final elements
            which = "sensor" if any(s in d["element"] or s[:-1] in d["element"] for s in sensors) else "fe"
            props[f"degraded_{which}_voting_silv"] = d.get("degraded_voting", "")
        store.merge_node("SIF", {"sif_id": sif}, {**props, **p}, stub=node["props"].get("stub", False))
        store.merge_rel("SHOWN_ON", "SIF", {"sif_id": sif}, "Document", doc_key, p)
        for t in split_tags(r.get("sensor_tags")) + split_tags(r.get("fe_tags")):
            tag = canonical_tag(t)
            if tag and store.has_node("Instrument", {"tag": tag}):
                store.merge_rel("SHOWN_ON", "Instrument", {"tag": tag}, "Document", doc_key, p)
            elif tag:
                report["unknown_tags"].append({"tag": tag, "sif_id": sif, "ref": ref})
        report["sifs"] += 1
    return report
