"""Make the Phase 6 test fixture: the frozen pid-to-kg graph with exactly one of each discrepancy.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

    python scripts/make_pidkg_discrepancies.py
        tests/fixtures/pidkg_U-100/graph.json  ->  tests/fixtures/pidkg_U-100/graph_discrepancies.json

The six edits are deliberate and small, one per reconciliation check of PIDKG_UPGRADE.md Phase 6
(pid_graph/vision_checks.py). They are listed in tests/fixtures/pidkg_U-100/DISCREPANCIES.md.
DUMMY DATA: nothing here describes a real drawing.
"""
from __future__ import annotations

import json
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pidkg_U-100"

EDITS = [
    ("1 tag check", "X22", "PI-1001", "PI-1001 removed from the drawing: in the index, not seen by vision"),
    ("2 flow", "X31", "L-104", "The blowdown flag on L-104 reads BL-200 instead of FLARE-HDR: vision's V-1002 -> BL-200 against pid_audit's V-1002 -> FLARE-HDR"),
    ("3 instrument line", "X32", "PT-1005", "PT-1005's tap moved from L-102 to the first segment of L-105; the index places it on L-102"),
    ("4 drawn trip", "X33", "LT-1006 -> XV-1002", "A trip signal drawn from LT-1006 to XV-1002; the C&E has no such cause and effect"),
    ("5 fail position", "X35", "LV-1006", "LV-1006 drawn FO; the index remark says fail close"),
    ("6 loop", "X36", "PV-1005", "PV-1005 grouped into loop L-1006; the index loop column says PIC-1005"),
]


def build(graph: dict) -> dict:
    g = json.loads(json.dumps(graph))
    nodes = {n["id"]: n for n in g["nodes"]}
    # 1. PI-1001 is not on the drawing
    g["nodes"] = [n for n in g["nodes"] if n["id"] != "PI-1001"]
    g["edges"] = [e for e in g["edges"] if "PI-1001" not in (e["source"], e["target"])]
    # 2. the blowdown line ends at BL-200
    flare = nodes["BOUNDARY:BLOWDOWN TO FLARE-HDR"]
    flare["name"] = flare["label"] = "BLOWDOWN TO BL-200"
    # 3. PT-1005 taps L-105
    next(e for e in g["edges"] if e["type"] == "MEASURES" and e["source"] == "PT-1005")["target"] = "P03.L2.1"
    # 4. an extra drawn trip
    g["edges"].append({"id": "E90001", "source": "LT-1006", "target": "XV-1002", "type": "SIGNAL_TO", "confidence": 0.85, "derived": False,
                       "attributes": {"signal_type": "electrical", "purpose": "trip"}, "sheet": "SHEET:PID-100-001"})
    # 5. LV-1006 drawn fail open
    nodes["LV-1006"]["attributes"]["fail_position"] = "FO"
    # 6. PV-1005 in the level loop
    next(e for e in g["edges"] if e["type"] == "MEMBER_OF" and e["source"] == "PV-1005" and e["target"] == "LOOP:P-1005")["target"] = "LOOP:L-1006"
    g["stats"] = {**g.get("stats", {}), "nodes": len(g["nodes"]), "edges": len(g["edges"])}
    return g


def main() -> int:
    out = FIX / "graph_discrepancies.json"
    out.write_text(json.dumps(build(json.loads((FIX / "graph.json").read_text(encoding="utf-8"))), indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
