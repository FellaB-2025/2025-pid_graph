"""Score a pid-to-kg extraction against the topology gold set (PIDKG_UPGRADE.md, Phase 8).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

What vision read off the drawings (pid-to-kg's graph.json, before pid_graph's gate) against what
the drawings show (eval/gold_topology_<unit>.json):

  tags        precision / recall of tagged items, overall and per sheet
  flow        precision / recall of equipment-level flow pairs; how many also name the right line
  loops       precision / recall of loops, and of (loop, member) pairs
  placement   instrument-placement accuracy: right line and right neighbours either side
              (segment level), or right equipment; line-only accuracy beside it

and what the extraction costs to review once it has passed the gate (load_pidkg + review):

  workload    share of facts flagged for priority review (T5), and pending facts per sheet

    python -m eval.topology_eval                       (the frozen U-100 fixture against its gold)
    python -m eval.topology_eval --graph work/U-100/kg/graph.json --gold eval/gold_topology_U-100.json --pidkg-eval

--pidkg-eval also runs pid-to-kg's own eval_kg.py (in .venv-pidkg, on eval/gold_pidkg_<unit>.json)
so the two scorers can be compared. No pass threshold is set here: Alan sets it after seeing
the numbers (PIDKG_UPGRADE.md, Phase 8 step 4).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "pidkg_U-100" / "graph.json"
OFF_PAGE = "off-page"


def _prf(gold: set, pred: set) -> dict:
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    show = lambda x: " ".join(x) if isinstance(x, tuple) else str(x)
    return {"gold": len(gold), "predicted": len(pred), "tp": tp, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
            "missed": sorted(show(x) for x in gold - pred), "spurious": sorted(show(x) for x in pred - gold)}


def score(graph: dict, gold: dict) -> dict:
    """Extraction quality: pid-to-kg graph.json against the gold set."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]
    doc = {n["id"]: n["attributes"]["drawing_number"] for n in nodes.values() if n["type"] == "Sheet"}
    gold_sheets = set(gold["sheets"])
    ends = {e for f in gold["flow_pairs"] for e in (f["from"], f["to"])}

    def name(nid: str) -> str:
        """What a node is called in the gold: its tag; a fitting's kind; a flag's tag if it carries one, else its text."""
        n = nodes[nid]
        if n["type"] == "OffPageConnector":
            return OFF_PAGE
        if n["type"] == "Boundary":
            text = n.get("name") or n["label"]
            tokens = set(re.split(r"[^A-Z0-9\-]+", text.upper()))
            hit = sorted(e for e in ends if e in tokens)
            return hit[0] if len(hit) == 1 else text
        return n.get("tag") or n.get("kind") or n["label"]

    # ---- tags ---------------------------------------------------------------------------
    gold_tags = {(d, t) for d, ts in gold["tags"].items() for t in ts}
    pred_tags = {(doc[s], n["tag"]) for n in nodes.values() if n["type"] in ("Equipment", "Instrument", "Component") and n.get("tag")
                 for s in n.get("sheets", []) if doc.get(s) in gold_sheets}
    out = {"tags": _prf({t for _, t in gold_tags}, {t for _, t in pred_tags})}
    # report misses and extras with the sheet they are on
    out["tags"]["missed"] = sorted(f"{d} {t}" for d, t in gold_tags if t not in {x for _, x in pred_tags})
    out["tags"]["spurious"] = sorted(f"{d} {t}" for d, t in pred_tags if t not in {x for _, x in gold_tags})
    out["tags_by_sheet"] = {d: _prf({t for s, t in gold_tags if s == d}, {t for s, t in pred_tags if s == d}) for d in gold["sheets"]}

    # ---- equipment-level flow --------------------------------------------------------------
    gold_flow = {(f["from"], f["to"]): f["via_lines"] for f in gold["flow_pairs"]}
    pred_flow = {(name(e["source"]), name(e["target"])): (e.get("attributes") or {}).get("via_lines") or [] for e in edges if e["type"] == "FEEDS"}
    out["flow"] = _prf(set(gold_flow), set(pred_flow))
    with_lines = [k for k, v in gold_flow.items() if v]
    out["flow_lines"] = {"pairs_with_lines": len(with_lines), "lines_correct": sum(1 for k in with_lines if sorted(pred_flow.get(k, [])) == sorted(gold_flow[k]))}

    # ---- loops -------------------------------------------------------------------------------
    pred_loops = {n["id"]: n["label"] for n in nodes.values() if n["type"] == "ControlLoop"}
    gold_members = {(k, m) for k, ms in gold["loops"].items() for m in ms}
    pred_members = {(pred_loops[e["target"]], nodes[e["source"]].get("tag") or nodes[e["source"]]["label"])
                    for e in edges if e["type"] == "MEMBER_OF" and e["target"] in pred_loops}
    out["loops"] = {"loops": _prf(set(gold["loops"]), set(pred_loops.values())), "members": _prf(gold_members, pred_members)}

    # ---- instrument placement -------------------------------------------------------------------
    flows = [e for e in edges if e["type"] == "FLOWS_TO"]
    into = {}
    outof = {}
    for e in flows:
        into.setdefault(e["target"], []).append(e["source"])
        outof.setdefault(e["source"], []).append(e["target"])

    def segment_place(seg: str) -> dict:
        a = nodes[seg].get("attributes") or {}
        up, down = into.get(seg, []), outof.get(seg, [])
        return {"on": "line", "line": a.get("line_number") or a.get("service"),
                "after": name(up[0]) if up else None, "before": name(down[0]) if down else None}

    def predicted(tag: str) -> dict | None:
        n = next((x for x in nodes.values() if x["type"] == "Instrument" and x.get("tag") == tag), None)
        if n is None:
            return None
        if (n.get("attributes") or {}).get("inline"):
            up, down = into.get(n["id"], []), outof.get(n["id"], [])
            if up and down:
                before_seg, after_seg = segment_place(up[0]), segment_place(down[0])
                return {"on": "line", "line": before_seg["line"], "after": before_seg["after"], "before": after_seg["before"]}
        for e in edges:
            if e["type"] == "MEASURES" and e["source"] == n["id"]:
                t = nodes[e["target"]]
                if t["type"] == "PipeSegment":
                    return segment_place(t["id"])
                return {"on": "equipment", "equipment": name(t["id"])}
        return {"on": "nothing"}

    correct = line_ok = 0
    errors = []
    for g in gold["placements"]:
        want = {k: g[k] for k in (("on", "line", "after", "before") if g["on"] == "line" else ("on", "equipment"))}
        got = predicted(g["tag"])
        if got == want:
            correct += 1
        else:
            errors.append({"tag": g["tag"], "sheet": g["sheet"], "expected": want, "got": got or "not extracted"})
        if got and (got.get("line") == want.get("line") if g["on"] == "line" else got == want):
            line_ok += 1
    n = len(gold["placements"])
    out["placement"] = {"total": n, "correct": correct, "accuracy": round(correct / n, 3) if n else None,
                        "line_correct": line_ok, "line_accuracy": round(line_ok / n, 3) if n else None, "errors": errors}
    return out


def workload(graph: dict, unit: str = "U-100") -> dict:
    """Review cost after the gate: run the loader on the U-100 registers and count what an engineer has to look at."""
    from pid_graph import load_pidkg as LP
    from pid_graph import review as RV
    from pid_graph.pipeline import build_store
    d = ROOT / "data"
    store, _ = build_store(unit=unit, index=d / "U100-INST-INDEX-Rev-B.xlsx", ce=d / "U100-CE-CHART-Rev-A.xlsx", srs=d / "U100-SRS-001-Rev-B.xlsx",
                           lopa=d / "U100-LOPA-001-Rev-A.xlsx", curated=d / "curated" / "compensating_measures_U-100.csv",
                           topology=d / "pid_audit_U100_topology.csv", pdf=d / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="eval")
    res = LP.reconcile(graph, LP.index_tags(store), store, unit=unit, load_run="eval")
    rows = RV.rows(res)
    by_flag: dict[str, int] = {}
    by_sheet: dict[str, int] = {}
    for r in rows:
        for f in filter(None, r["flags"].split("; ")):
            by_flag[f] = by_flag.get(f, 0) + 1
        if r["review"] == "pending":
            by_sheet[r["sheet"]] = by_sheet.get(r["sheet"], 0) + 1
    flagged = sum(1 for r in rows if r["flags"])
    return {"facts": len(rows), "flagged": flagged, "flag_share": round(flagged / len(rows), 3) if rows else None,
            "by_flag": dict(sorted(by_flag.items())), "pending": sum(by_sheet.values()), "pending_by_sheet": dict(sorted(by_sheet.items())),
            "loaded": {"nodes": res["summary"]["nodes"], "rels": res["summary"]["rels"]}, "exceptions_by_code": res["summary"]["exceptions_by_code"]}


def run_pidkg_eval(graph_path: Path, gold_path: Path) -> dict:
    """pid-to-kg's own scorer, unmodified, in its own environment. Nothing is written into its folder."""
    import os
    script = ROOT / "third_party" / "pid-to-kg" / "skills" / "pid-to-kg" / "scripts" / "eval_kg.py"
    py = ROOT / ".venv-pidkg" / "Scripts" / "python.exe"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    run = subprocess.run([str(py), str(script), str(graph_path), str(gold_path), "--json"], capture_output=True, text=True, env=env, check=True)
    return json.loads(run.stdout)


def print_scores(s: dict, w: dict) -> None:
    print(f"  {'':18} {'gold':>5} {'pred':>5} {'tp':>4} {'prec':>6} {'rec':>6} {'f1':>6}")
    for label, x in (("tags", s["tags"]), ("flow pairs", s["flow"]), ("loops", s["loops"]["loops"]), ("loop members", s["loops"]["members"])):
        print(f"  {label:18} {x['gold']:5} {x['predicted']:5} {x['tp']:4} {x['precision']:6.3f} {x['recall']:6.3f} {x['f1']:6.3f}")
        if x["missed"]:
            print(f"      missed:   {', '.join(x['missed'])}")
        if x["spurious"]:
            print(f"      spurious: {', '.join(x['spurious'])}")
    p = s["placement"]
    print(f"  instrument placement: {p['correct']} / {p['total']} exact ({p['accuracy']}), {p['line_correct']} / {p['total']} on the right line")
    for e in p["errors"]:
        print(f"      {e['tag']}: expected {e['expected']}, got {e['got']}")
    print(f"  flow pairs naming the right line: {s['flow_lines']['lines_correct']} / {s['flow_lines']['pairs_with_lines']}")
    print(f"  review workload: {w['flagged']} of {w['facts']} facts flagged for priority review ({w['flag_share']}) {w['by_flag']}")
    print(f"  pending per sheet: {w['pending_by_sheet']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default=str(FIXTURE), help="pid-to-kg graph.json")
    ap.add_argument("--gold", default=str(ROOT / "eval" / "gold_topology_U-100.json"))
    ap.add_argument("--pidkg-eval", action="store_true", help="also run pid-to-kg's own eval_kg.py on eval/gold_pidkg_<unit>.json")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    graph = json.loads(Path(a.graph).read_text(encoding="utf-8"))
    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    s, w = score(graph, gold), workload(graph, gold["unit"])
    print(f"Topology eval, unit {gold['unit']}: {Path(a.graph).name} against {Path(a.gold).name}")
    print_scores(s, w)
    report = {"unit": gold["unit"], "graph": str(a.graph), "gold": str(a.gold), "scores": s, "workload": w, "thresholds": None}
    if a.pidkg_eval:
        theirs = run_pidkg_eval(Path(a.graph), ROOT / "eval" / f"gold_pidkg_{gold['unit']}.json")
        report["pidkg_eval"] = theirs
        t, f, ip, lp = theirs["tags"], theirs["flow"], theirs["instrument_placement"], theirs["loops"]
        print(f"  pid-to-kg eval_kg.py: tags P {t['precision']} R {t['recall']}; flow P {f['precision']} R {f['recall']}; "
              f"placement {ip['correct']} / {ip['total']}; loops recall {lp['recall']}, mean member overlap {lp['mean_member_jaccard']}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"topology_eval_{gold['unit']}.json"
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"  flagged for priority review share and pending counts are after the gate; scores are before it.\n  -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
