"""Build the U-100 topology gold set from what the synthetic drawings show.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

    python -m eval.make_topology_gold
        data/U100-PIDS-DRAWN-CONTENT.json  ->  eval/gold_topology_U-100.json   (pid_graph's format, scored by eval/topology_eval.py)
                                           ->  eval/gold_pidkg_U-100.json      (pid-to-kg's format, scored by its own eval_kg.py)

The drawings are fabricated by scripts/make_dummy_pdf.py, which also writes the answer key this
is built from, so for U-100 the gold set is exact rather than hand-checked. A real drawing has
no answer key: there the gold is read off the sheet by an engineer, in the same format.

What the gold says, per PIDKG_UPGRADE.md Phase 8:
  tags        every tagged item drawn, per sheet (equipment, instrument bubbles, tagged valves).
              The interlock diamonds I-1 / I-2 are symbols, not tags.
  placements  every instrument bubble: on a line, between which two in-line things (segment
              level, without depending on any segment numbering), or on which equipment.
  flow_pairs  every equipment-level flow pair with the line(s) between; an end is the tag where
              the flag carries one (BL-100), else the flag text (FUTURE FUEL GAS).
  loops       every loop and its members: control loops from the drawn measurement and control
              signals, interlock loops from the drawn trip signals. Key = first letter + number.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "U100-PIDS-DRAWN-CONTENT.json"
OUT = ROOT / "eval" / "gold_topology_U-100.json"
OUT_PIDKG = ROOT / "eval" / "gold_pidkg_U-100.json"
OFF_PAGE = "off-page"
_KEY = re.compile(r"^([A-Z])[A-Z]*-(\d+)")


def loop_key(tag: str) -> str:
    m = _KEY.match(tag)
    return f"{m.group(1)}-{m.group(2)}" if m else tag


def _names(sheet: dict) -> dict:
    """id -> the name an item goes by in the gold: its tag, else its kind (fittings), flag tag or text, or off-page."""
    out = {}
    for kind in ("equipment", "instruments", "components"):
        for x in sheet[kind]:
            out[x["id"]] = x.get("tag") or x.get("kind")
    for b in sheet["boundaries"]:
        out[b["id"]] = b.get("tag") or b["name"]
    for c in sheet["off_page_connectors"]:
        out[c["id"]] = OFF_PAGE
    return out


def build(drawn: dict) -> tuple[dict, dict]:
    sheets = drawn["sheets"]
    tags, placements, loops = {}, [], {}
    line_ends: dict[str, list] = {}          # line key -> [(sheet, from name, to name, raw from, raw to)]
    boundary_text: dict[str, str] = {}       # gold end name -> flag text as drawn (pid-to-kg's format uses the text)
    for doc_no, s in sheets.items():
        name = _names(s)
        tags[doc_no] = sorted({x["tag"] for kind in ("equipment", "instruments", "components") for x in s[kind] if x.get("tag")})
        for b in s["boundaries"]:
            boundary_text[b.get("tag") or b["name"]] = " ".join(b["text"])      # the flag exactly as drawn
        tapped = set()
        for ln in s["lines"]:
            path = ln["path"]
            for i, item in enumerate(ln["order"]):
                inst = next((x for x in s["instruments"] if x["id"] == item), None)
                if inst is None:
                    continue
                before_me = [p for p in ln["order"][:i] if p in path]
                after_me = [p for p in ln["order"][i + 1:] if p in path]
                placements.append({"tag": inst["tag"], "sheet": doc_no, "on": "line", "line": ln["line_no"] or ln["service"],
                                   "after": name[before_me[-1]] if before_me else name.get(ln["from"], ln["from"]),
                                   "before": name[after_me[0]] if after_me else name.get(ln["to"], ln["to"]),
                                   "in_line": item in path})
                tapped.add(inst["tag"])
            line_ends.setdefault(ln["line_no"] or f"{doc_no}:{ln['service']}", []).append(
                (name.get(ln["from"], ln["from"]), name.get(ln["to"], ln["to"]), ln["line_no"]))
        for inst in s["instruments"]:
            if inst["tag"] not in tapped and (inst.get("measures") or {}).get("item"):
                placements.append({"tag": inst["tag"], "sheet": doc_no, "on": "equipment", "equipment": inst["measures"]["item"]})
        # loops: control loops are the connected groups of measurement / control signals; interlocks group by their symbol
        groups: list[set] = []
        for sig in s["signals"]:
            if sig["purpose"] == "trip":
                continue
            hit = [g for g in groups if g & {sig["from"], sig["to"]}]
            merged = set().union({sig["from"], sig["to"]}, *hit)
            groups = [g for g in groups if g not in hit] + [merged]
        for g in groups:
            loops.setdefault(loop_key(sorted(g)[0]), set()).update(g)
        by_symbol: dict[str, set] = {}
        first: dict[str, str] = {}
        for sig in s["signals"]:
            if sig["purpose"] == "trip":
                by_symbol.setdefault(sig["via_interlock"], set()).update({sig["from"], sig["to"]})
                first.setdefault(sig["via_interlock"], sig["from"])
        for sym, members in by_symbol.items():
            loops.setdefault(loop_key(first[sym]), set()).update(members)

    # equipment-level flow: join a line's sheets across its off-page connectors
    flow = []
    for key, parts in line_ends.items():
        starts = [p[0] for p in parts if p[0] != OFF_PAGE]
        ends = [p[1] for p in parts if p[1] != OFF_PAGE]
        for a in starts:
            for b in ends:
                flow.append({"from": a, "to": b, "via_lines": [parts[0][2]] if parts[0][2] else []})
    flow.sort(key=lambda f: (f["via_lines"], f["from"], f["to"]))
    placements.sort(key=lambda p: (p["sheet"], p["tag"]))
    gold = {"note": "DUMMY DATA. Topology gold set for the synthetic U-100 P&IDs (TX-0057). Built by eval/make_topology_gold.py from the "
                    "drawings' answer key data/U100-PIDS-DRAWN-CONTENT.json, so it is exact for these sheets.",
            "unit": "U-100", "sheets": list(sheets), "tags": tags, "placements": placements, "flow_pairs": flow,
            "loops": {k: sorted(v) for k, v in sorted(loops.items())}}

    def nearest_equipment(p: dict) -> str | None:
        if p["on"] == "equipment":
            return p["equipment"]
        eq = {x["tag"] for s in sheets.values() for x in s["equipment"]}
        ends = {e for f in flow if p["line"] in f["via_lines"] for e in (f["from"], f["to"])}
        return next(iter(sorted(ends & eq)), None)

    pidkg = {"sheets": list(sheets), "tags": sorted({t for ts in tags.values() for t in ts}),
             "feeds": [[boundary_text.get(f["from"], f["from"]), boundary_text.get(f["to"], f["to"])] for f in flow],
             "instrument_at": {p["tag"]: nearest_equipment(p) for p in placements if nearest_equipment(p)},
             "loops": gold["loops"]}
    return gold, pidkg


def main() -> int:
    gold, pidkg = build(json.loads(SOURCE.read_text(encoding="utf-8")))
    for path, data in ((OUT, gold), (OUT_PIDKG, pidkg)):
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
