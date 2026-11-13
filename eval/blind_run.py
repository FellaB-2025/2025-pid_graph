"""Blind test, step 2 of 3: run the frozen checks on a unit whose answer key the runner has not seen, and seal the result.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Protocol (docs/BLIND_TEST.md):
  1. A planter who has not read the checks writes the unit's documents and its answer key.
  2. This script runs the checks exactly as they were at the freeze tag, never opens the answer key, and writes
     every finding and every scenario verdict to eval/blind/<UNIT>-BLIND-RUN-FINDINGS.json. That file is
     committed before anyone compares it with the key.
  3. A scorer who wrote neither compares the sealed findings with the key and writes the adjudication file.

    python -m eval.blind_run --unit U-200 --freeze blind-freeze-1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FROZEN = ("pid_graph/ops_checks.py", "pid_graph/reconcile.py", "pid_graph/pipeline.py", "pid_graph/loaders", "pid_graph/records.py",
          "pid_graph/ontology.py", "pid_graph/tags.py")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--unit", required=True)
    ap.add_argument("--freeze", required=True, help="git tag or commit the checks were frozen at")
    a = ap.parse_args(argv)
    changed = _git("diff", "--name-only", a.freeze, "--", *FROZEN)
    if changed:
        print("The checks have changed since the freeze; a blind run would not be blind:\n" + changed)
        return 1
    from pid_graph import demo
    data = demo.build(unit=a.unit)
    reports = demo.build_demo_store(unit=a.unit)[1]
    sealed = {
        "_note": "Sealed output of a blind run. Written without reading the unit's answer key. Do not edit.",
        "unit": a.unit, "freeze": a.freeze, "freeze_commit": _git("rev-parse", a.freeze), "run_commit": _git("rev-parse", "HEAD"),
        "frozen_paths": list(FROZEN), "export_time": data["export_time"], "counts": data["counts"],
        "documents": data["documents"],
        "load_reports": {k: {x: v for x, v in reports[k].items() if x in ("document", "rows", "skipped", "unknown_tags", "cfg_only_points",
                                                                           "new_alarms", "tags_not_in_graph", "unresolved", "unknown_types",
                                                                           "ce_only_instruments", "ce_only_alarms", "srs_only_sifs", "gaps", "proposed")}
                         for k in reports if isinstance(reports[k], dict) and "file" in reports[k]},
        "findings": [{k: f[k] for k in ("key", "code", "title", "label", "id", "detail", "sources", "refs", "tags", "level")} for f in data["findings"]],
        "scenario_verdicts": [{"id": s["id"], "level": s["verdict"]["level"], "text": s["verdict"]["text"]} for s in data["scenarios"]],
        "situation_as_found": {"out": data["situation"]["presets"]["as_found"]},
    }
    out = ROOT / "eval" / "blind" / f"{a.unit.replace('-', '')}-BLIND-RUN-FINDINGS.json"    # not in the unit's folder: that holds only what its generator writes
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sealed, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    by = {}
    for f in data["findings"]:
        by[f["code"]] = by.get(f["code"], 0) + 1
    print(out)
    print(f"{len(data['findings'])} findings, {len(data['scenarios'])} scenarios; by code: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: (kv[0][0], int(kv[0][1:])))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
