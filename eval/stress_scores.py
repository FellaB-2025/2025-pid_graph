"""Collect the Phase 9 stress-test scores into eval/stress_test_scores.json: numbers only, nothing copied from the drawings.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

    python eval/stress_scores.py      (needs work/pahala/scores and work/virden/scores, which are git-ignored)

The token and minute figures are those of the run of 10 Nov 2026 and are typed in below.
"""
import json
from pathlib import Path


def slim_eval(path):
    e = json.loads(Path(path).read_text(encoding="utf-8"))
    t, f, ip, lp = e["tags"], e["flow"], e["instrument_placement"], e["loops"]
    return {"tags": {"precision": t["precision"], "recall": t["recall"], "correct": t["tp"], "missed": len(t["missed"]), "extra": len(t["false_positives"])},
            "flow": {"precision": f["precision"], "recall": f["recall"], "correct": f["tp"], "missed": len(f["missed"]), "extra": len(f["false_positives"])},
            "instrument_placement": {"correct": ip["correct"], "total": ip["total"]},
            "loops": {"recall": lp["recall"], "mean_member_overlap": lp["mean_member_jaccard"], "gold_loops": len(lp["detail"])}}


def slim_report(path):
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"sheets": [{"page": s["page"], "tiles_reviewed": s["tiles_reviewed"], "unreadable": s["unreadable"]} for s in r["sheets"]],
            "nodes": r["nodes"], "nodes_by_type": r["nodes_by_type"], "relationships": r["relationships"],
            "relationships_by_type": r["relationships_by_type"], "tagged": r["tagged"], "segments": r["segments"],
            "off_page_connectors": r["off_page_connectors"], "unreadable": r["unreadable"], "qa_issues": r["qa_issues"],
            "confidence": r["confidence"], "t5": r["t5"]}


out = {
    "note": "Phase 9 stress test, pilot of two sheets per set, 10 Nov 2026. Numbers only: no drawing, render, tag list or extracted graph is "
            "kept in the repository. Gold files were written by an independent model reader and are NOT yet checked by an engineer, so every "
            "score here is agreement between two machine reads, not accuracy.",
    "tool": "pid-to-kg 0.1.0 @ 7ee3a82, no OCR (Python 3.14)", "scorer": "pid-to-kg eval_kg.py, unmodified", "gold_verified_by_engineer": False,
    "sets": {
        "pahala": {"kind": "digital vector PDF, text mostly outlined", "pages_in_set": "9-25", "pages_extracted": [11, 20],
                   "report_only": slim_report("work/pahala/scores/report_only.json"),
                   "scores": {"page_11": slim_eval("work/pahala/scores/eval_p11.json"),
                              "page_11_basin_alias_allowed": slim_eval("work/pahala/scores/eval_p11_alias.json"),
                              "page_20": slim_eval("work/pahala/scores/eval_p20.json")},
                   "extraction_tokens": 163123, "extraction_minutes": 3.7},
        "virden": {"kind": "scanned, about 150 dpi, no text layer", "pages_in_set": "5-14", "pages_extracted": [6, 14],
                   "report_only": slim_report("work/virden/scores/report_only.json"),
                   "scores": {"page_06": slim_eval("work/virden/scores/eval_p06.json")},
                   "extraction_tokens": 213598, "extraction_minutes": 7.5},
    },
}
Path("eval/stress_test_scores.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(out["sets"]["pahala"]["scores"], indent=0)[:900])
print(json.dumps(out["sets"]["virden"]["scores"]))
