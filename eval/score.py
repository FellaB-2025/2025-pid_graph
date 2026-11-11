"""Score the graph for one drawing against a hand-built gold set.

Node and edge precision/recall are reported separately (decisions section 8).
Predicted nodes = anything SHOWN_ON the drawing by a P&ID extraction (not by the
index's claim). Predicted edges = INSTALLED_ON / FEEDS / MEASURES edges whose
source_doc is the drawing.

    python -m eval.score --gold eval/gold_PID-100-001.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXTRACTED = ("pid_audit", "manual", "llm")


def _prf(gold: set, pred: set) -> dict:
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"gold": len(gold), "predicted": len(pred), "tp": tp,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
            "missed": sorted(" ".join(x) for x in gold - pred),
            "spurious": sorted(" ".join(x) for x in pred - gold)}


def score(store, gold: dict) -> dict:
    sheet = gold["sheet"]
    gold_nodes = {(lab, ident) for lab, ident in gold["nodes"]}
    gold_edges = {(t, a, b) for t, a, b in gold["edges"]}
    pred_nodes = set()
    for r in store.rels("SHOWN_ON"):
        if r["end_key"]["doc_no"] == sheet and r["props"].get("extracted_by") in EXTRACTED:
            pred_nodes.add((r["start_label"], list(r["start_key"].values())[0]))
    pred_edges = set()
    for r in store.rels():
        if r["type"] in ("INSTALLED_ON", "FEEDS", "MEASURES") and r["props"].get("source_doc") == sheet:
            pred_edges.add((r["type"], list(r["start_key"].values())[0], list(r["end_key"].values())[0]))
    return {"sheet": sheet, "nodes": _prf(gold_nodes, pred_nodes), "edges": _prf(gold_edges, pred_edges)}


def print_scores(res: dict) -> None:
    print(f"  Gold set: {res['sheet']}")
    print(f"  {'':8} {'gold':>5} {'pred':>5} {'tp':>4} {'prec':>6} {'rec':>6} {'f1':>6}")
    for k in ("nodes", "edges"):
        s = res[k]
        print(f"  {k:8} {s['gold']:5} {s['predicted']:5} {s['tp']:4} {s['precision']:6.3f} {s['recall']:6.3f} {s['f1']:6.3f}")
    for k in ("nodes", "edges"):
        if res[k]["missed"]:
            print(f"  missed {k}:   {', '.join(res[k]['missed'])}")
        if res[k]["spurious"]:
            print(f"  spurious {k}: {', '.join(res[k]['spurious'])}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", default=str(ROOT / "eval" / "gold_PID-100-001.json"))
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--index", default=str(ROOT / "data" / "U100-INST-INDEX-Rev-B.xlsx"))
    ap.add_argument("--topology", default=str(ROOT / "data" / "pid_audit_U100_topology.csv"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    from pid_graph.pipeline import build_store, new_load_run
    store, _ = build_store(unit=a.unit, index=a.index, topology=a.topology, load_run=new_load_run("eval"))
    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    res = score(store, gold)
    print_scores(res)
    out = Path(a.out) / f"eval_{res['sheet']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
