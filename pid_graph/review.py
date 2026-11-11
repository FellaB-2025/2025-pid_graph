"""Review register and drawing markup for the vision layer (PIDKG_UPGRADE.md, Phase 5).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Vision proposes, the index disposes, an engineer accepts. This module is where the engineer
accepts. Every pidkg_vision fact (trust rule T4) is written review = pending and listed in

    reports/review_register_<unit>.xlsx

beside the exception register and in the same workbook format: a Summary sheet (metric /
value) and a Review sheet, one row per vision node and relationship:

    fact_id, type, from, to, sheet, bbox, confidence, flags, review, reviewer, reviewed_on, comment, detail

The engineer fills in review (accepted / rejected), reviewer, reviewed_on and comment. The
loader reads the register back on every run and matches on fact_id (a stable hash of type +
endpoints + drawing), so a decision survives a re-extraction. Rules:

  * a decision counts only with a named reviewer and a closed value; anything else is
    reported as a problem and the fact stays pending (same spirit as D-P2-10);
  * a rejected fact is not written to the graph on the next load, and its row stays in the
    register with the reviewer and the reason (T8);
  * the register is an input as well as an output: it is read before it is written, the
    engineer's cells are carried over verbatim, and the file is not rewritten when nothing changed;
  * the SHOWN_ON of a new node is not a row of its own: it follows the node's decision.

flags are the priority-review flags of T5: low_confidence (< 0.85), inferred_direction,
off_page, inline_item (the fact is, or touches, an InlineItem). Flagged rows come first.
detail is an extra column, not in the plan: what the fact says, so a row can be judged.

markup() writes a copy of the P&ID PDF with one annotation per located fact, so review is done
on the drawing: green accepted, amber pending, red rejected or exception. The source PDF is a
controlled document and is never modified. Annotations carry the fact_id of the register row.

    python -m pid_graph --pidkg <graph.json> --pdf <pids.pdf> ...     (writes register and markup into --out)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import ontology as O

COLUMNS = ["fact_id", "type", "from", "to", "sheet", "bbox", "confidence", "flags", "review", "reviewer", "reviewed_on", "comment", "detail"]
ENGINEER_COLUMNS = ("review", "reviewer", "reviewed_on", "comment")
LOW_CONFIDENCE = 0.85
COLOURS = {"accepted": (0.0, 0.6, 0.0), "pending": (1.0, 0.6, 0.0), "rejected": (0.85, 0.0, 0.0)}
_BBOX = re.compile(r"bbox=([\d.,]+)")


def _ident(label: str, key: dict) -> str:
    return f"{label} {'|'.join(str(v) for v in key.values())}"


def _detail(fact: dict) -> str:
    p, typ = fact["props"], fact.get("type") or fact["label"]
    if typ == "Segment":
        return f"{p.get('size', '')} {p.get('service', '')}".strip()
    if typ == "InlineItem":
        return f"{p.get('kind', '')}, normal position {p.get('normal_position', '')}"
    if typ == "ControlLoop":
        return f"{p.get('loop_type', '')} loop, {p.get('variable', '')}"
    if typ == "FLOWS_TO":
        return f"flow {p.get('flow_direction', '')}" + (", off-page" if p.get("off_page") else "")
    if typ == "SIGNAL_TO":
        via = f" via {p['via']}" + (f" ({p['via_name']})" if p.get("via_name") else "") if p.get("via") else ""
        return f"{p.get('purpose', '')} signal ({p.get('signal_type', '')}){via}"
    if typ == "MEMBER_OF":
        return f"role {p.get('role', '')}"
    if typ == "MEASURES":
        return "tap on this segment"
    return ""


def flags(fact: dict, inline: set[str]) -> list[str]:
    """T5 priority-review flags for one fact. inline = identifiers of the InlineItems in this load."""
    p, out = fact["props"], []
    if float(p.get("confidence") or 0) < LOW_CONFIDENCE:
        out.append("low_confidence")
    if p.get("flow_direction") == "inferred":
        out.append("inferred_direction")
    if p.get("off_page") is True:
        out.append("off_page")
    ends = {_ident(fact["label"], fact["key"])} if "label" in fact else {_ident(fact["start_label"], fact["start_key"]),
                                                                            _ident(fact["end_label"], fact["end_key"])}
    if ends & inline:
        out.append("inline_item")
    return out


def rows(result: dict) -> list[dict]:
    """One register row per vision node and relationship of a reconcile() result, priority rows first."""
    inline = {_ident(n["label"], n["key"]) for n in result["nodes"] if n["label"] == "InlineItem"}
    out = []
    for f in result["nodes"] + result["rels"]:
        if f.get("type") == "SHOWN_ON":
            continue
        p = f["props"]
        m = _BBOX.search(p.get("source_ref", ""))
        frm, to = (_ident(f["label"], f["key"]), "") if "label" in f else (_ident(f["start_label"], f["start_key"]), _ident(f["end_label"], f["end_key"]))
        out.append({"fact_id": p["fact_id"], "type": f.get("type") or f["label"], "from": frm, "to": to, "sheet": p["source_doc"],
                    "bbox": m.group(1) if m else "", "confidence": p["confidence"], "flags": "; ".join(flags(f, inline)),
                    "review": p["review"], "reviewer": "", "reviewed_on": "", "comment": "", "detail": _detail(f)})
    return sorted(out, key=lambda r: (not r["flags"], r["sheet"], r["type"], r["from"], r["to"]))


def _problem(row: dict) -> str | None:
    review = str(row.get("review") or "").strip()
    if review not in O.REVIEW:
        return f"{row['fact_id']} ({row.get('type')} {row.get('from')}): review {review!r} is not one of {O.REVIEW}; treated as pending"
    if review != "pending" and not str(row.get("reviewer") or "").strip():
        return f"{row['fact_id']} ({row.get('type')} {row.get('from')}): {review} with no reviewer named; treated as pending"
    return None


def read_register(path: str | Path) -> tuple[dict[str, dict], list[str]]:
    """({fact_id: row}, problems). A missing file is an empty register."""
    path = Path(path)
    if not path.is_file():
        return {}, []
    from openpyxl import load_workbook
    ws = load_workbook(path)["Review"]
    it = ws.iter_rows(values_only=True)
    head = [str(c or "") for c in next(it)]
    register, problems = {}, []
    for values in it:
        row = {h: ("" if v is None else v) for h, v in zip(head, values)}
        if not row.get("fact_id"):
            continue
        for c in ENGINEER_COLUMNS:
            row[c] = str(row.get(c, "")).strip()
        register[str(row["fact_id"])] = row
        p = _problem(row)
        if p:
            problems.append(p)
    return register, problems


def decisions(register: dict[str, dict]) -> dict[str, str]:
    """{fact_id: 'accepted' | 'rejected'} for the rows that carry a valid decision. Input to load_pidkg.reconcile(review=...)."""
    return {fid: row["review"] for fid, row in register.items() if row["review"] in ("accepted", "rejected") and _problem(row) is None}


def merged_rows(result: dict, previous: dict[str, dict] | None = None) -> list[dict]:
    """Today's facts with the engineer's cells carried over, plus decided rows that are no longer extracted."""
    previous = previous or {}
    out, seen = [], set()
    for r in rows(result):
        old = previous.get(r["fact_id"])
        if old:
            r.update({c: old.get(c, "") for c in ENGINEER_COLUMNS})
            r["review"] = r["review"] or "pending"
        seen.add(r["fact_id"])
        out.append(r)
    for fid, old in previous.items():
        if fid in seen or old.get("review") not in ("accepted", "rejected") or _problem(old):
            continue
        keep = {c: old.get(c, "") for c in COLUMNS}
        if old["review"] == "accepted" and "not_in_extraction" not in str(keep["flags"]):
            keep["flags"] = "; ".join(filter(None, [str(keep["flags"]), "not_in_extraction"]))
        out.append(keep)                                   # rejected: stays in the register with reviewer and reason (T8)
    return out


def summarise(all_rows: list[dict], unit: str, problems: list[str] | None = None) -> dict:
    state = lambda r: r["review"] if _problem(r) is None else "pending"
    pending = [r for r in all_rows if state(r) == "pending"]
    by_sheet: dict[str, int] = {}
    for r in pending:
        by_sheet[r["sheet"]] = by_sheet.get(r["sheet"], 0) + 1
    return {"unit": unit, "facts": len(all_rows), "pending": len(pending),
            "accepted": sum(1 for r in all_rows if state(r) == "accepted"), "rejected": sum(1 for r in all_rows if state(r) == "rejected"),
            "pending_priority": sum(1 for r in pending if r["flags"] and "not_in_extraction" not in r["flags"]),
            "pending_by_sheet": json.dumps(dict(sorted(by_sheet.items()))),
            "problems": len(problems if problems is not None else [p for p in map(_problem, all_rows) if p])}


def write_register(result: dict, out: str | Path, *, unit: str, previous: dict[str, dict] | None = None) -> Path:
    """Write the register, carrying the engineer's decisions over. Not rewritten when its content is unchanged."""
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font
    out = Path(out)
    all_rows = merged_rows(result, previous)
    summary = summarise(all_rows, unit)
    table = [[r.get(c, "") for c in COLUMNS] for r in all_rows]
    if out.is_file():
        wb0 = load_workbook(out)
        if "Review" in wb0.sheetnames and "Summary" in wb0.sheetnames:
            same_rows = [["" if v is None else v for v in r] for r in wb0["Review"].iter_rows(min_row=2, values_only=True)] == table
            same_summary = {r[0]: r[1] for r in wb0["Summary"].iter_rows(min_row=2, values_only=True)} == summary
            if same_rows and same_summary:
                return out
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Metric", "Value"])
    for k, v in summary.items():
        ws.append([k, v])
    ws2 = wb.create_sheet("Review")
    ws2.append(COLUMNS)
    for r in table:
        ws2.append(r)
    for w in (ws, ws2):
        for cell in w[1]:
            cell.font = Font(bold=True)
        for col in w.columns:
            width = min(60, max(12, max(len(str(c.value or "")) for c in col) + 2))
            w.column_dimensions[col[0].column_letter].width = width
    ws2.freeze_panes = "A2"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


# ---- markup on the drawing -----------------------------------------------------------
def _worst(states: list[str]) -> str:
    return "rejected" if "rejected" in states else ("pending" if "pending" in states else "accepted")


def markup(pdf: str | Path, result: dict, out: str | Path, register: dict[str, dict] | None = None) -> Path:
    """Copy the P&ID PDF and annotate it with the vision facts of a reconcile() result.

    Boxes: InlineItems, instruments with a segment-level MEASURES, exceptions (red, with their code),
    and rejected rows of the register that carry a bbox. Lines: each Segment, drawn between the two
    located things it runs between and coloured by the worst of the segment and its two FLOWS_TO;
    each SIGNAL_TO, drawn between its two ends. MEMBER_OF and SEGMENT_OF have no place on the sheet
    and are reviewed in the register only."""
    import pymupdf
    register = register or {}
    loc, pages = result["locations"], result["pages"]
    doc = pymupdf.open(pdf)

    def rect(page, bbox, pad=3):
        r = page.rect
        return pymupdf.Rect(r.x0 + bbox[0] * r.width - pad, r.y0 + bbox[1] * r.height - pad,
                            r.x0 + bbox[2] * r.width + pad, r.y0 + bbox[3] * r.height + pad)

    def centre(page, bbox):
        r = rect(page, bbox, 0)
        return pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)

    def nearest(page, bbox, other) -> "pymupdf.Point":
        """The point of a box nearest to another point: lines end on the edge of a vessel, not in its middle."""
        r = rect(page, bbox, 0)
        return pymupdf.Point(min(max(other.x, r.x0), r.x1), min(max(other.y, r.y0), r.y1))

    def finish(annot, state, content, width=1.6, dashes=None):
        annot.set_colors(stroke=COLOURS[state])
        annot.set_border(width=width, dashes=dashes)
        annot.set_info(content=content, title="pid_graph review")
        annot.set_opacity(0.85)
        annot.update()

    def label(page, at, text, state):
        w = max(40, 3.4 * len(text) + 6)
        a = page.add_freetext_annot(pymupdf.Rect(at.x, at.y, at.x + w, at.y + 9), text, fontsize=6, fontname="helv",
                                    text_color=COLOURS[state])
        a.set_info(content=text, title="pid_graph review")
        a.update()

    def box(key, state, content, text):
        where = loc.get(key)
        if not where:
            return
        page = doc[where["page"] - 1]
        r = rect(page, where["bbox"])
        finish(page.add_rect_annot(r), state, content)
        label(page, pymupdf.Point(r.x0, r.y1 + 9), text, state)

    def line(a_key, b_key, state, content, text, signal=False):
        a, b = loc.get(a_key), loc.get(b_key)
        if not a or not b or a["page"] != b["page"]:
            return
        page = doc[a["page"] - 1]
        p1 = nearest(page, a["bbox"], centre(page, b["bbox"]))
        p2 = nearest(page, b["bbox"], p1)
        p1 = nearest(page, a["bbox"], p2)
        if signal:                                         # thin and dashed, so signals do not read as pipe
            finish(page.add_line_annot(p1, p2), state, content, width=0.7, dashes=[3, 2])
        else:
            finish(page.add_line_annot(p1, p2), state, content)
            label(page, pymupdf.Point((p1.x + p2.x) / 2 - 12, (p1.y + p2.y) / 2 - 11), text, state)

    name = lambda f, end="": _ident(f[f"{end}label"], f[f"{end}key"])
    flows = [r for r in result["rels"] if r["type"] == "FLOWS_TO"]
    for n in result["nodes"]:
        p = n["props"]
        if n["label"] == "InlineItem":
            box(name(n), p["review"], f"{p['fact_id']} InlineItem {n['key']['item_id']}: {_detail(n)} [{p['review']}]", f"{p.get('kind', '')} {p['review']}")
        elif n["label"] == "Segment":
            ins = [r for r in flows if name(r, "end_") == name(n)]
            outs = [r for r in flows if name(r, "start_") == name(n)]
            for i in ins:
                for o in outs:
                    state = _worst([p["review"], i["props"]["review"], o["props"]["review"]])
                    content = (f"Segment {n['key']['segment_id']} ({_detail(n)}) {p['fact_id']} [{p['review']}]; "
                               f"FLOWS_TO in {i['props']['fact_id']} [{i['props']['review']}], out {o['props']['fact_id']} [{o['props']['review']}]")
                    line(name(i, "start_"), name(o, "end_"), state, content, n["key"]["segment_id"])
    for r in result["rels"]:
        p = r["props"]
        if r["type"] == "MEASURES":
            seg = r["end_key"].get("segment_id", "")
            box(name(r, "start_"), p["review"], f"{p['fact_id']} MEASURES {name(r, 'start_')} -> Segment {seg} [{p['review']}]", f"taps {seg}")
        elif r["type"] == "SIGNAL_TO":
            line(name(r, "start_"), name(r, "end_"), p["review"],
                 f"{p['fact_id']} SIGNAL_TO {name(r, 'start_')} -> {name(r, 'end_')}: {_detail(r)} [{p['review']}]", f"{p.get('purpose', '')} {p.get('via', '')}".strip(), signal=True)
    for e in result["exceptions"]:
        m, pg = _BBOX.search(e["refs"] or ""), re.search(r":p(\d+)", e["refs"] or "")
        if m and pg:
            page = doc[int(pg.group(1)) - 1]
            r = rect(page, [float(v) for v in m.group(1).split(",")])
            finish(page.add_rect_annot(r), "rejected", f"{e['code']} {e['title']}: {e['id']} - {e['detail']}")
            label(page, pymupdf.Point(r.x0, r.y0 - 10), f"{e['code']} {e['id']}", "rejected")
    current = {x["props"]["fact_id"] for x in result["nodes"] + result["rels"]}
    for fid, row in register.items():
        if row.get("review") != "rejected" or fid in current or _problem(row):
            continue
        content = f"{fid} REJECTED {row.get('type')} {row.get('from')} {row.get('to') or ''} by {row.get('reviewer')}: {row.get('comment')}"
        if row.get("bbox") and row.get("sheet") in pages:
            page = doc[pages[row["sheet"]] - 1]
            r = rect(page, [float(v) for v in str(row["bbox"]).split(",")])
            finish(page.add_rect_annot(r), "rejected", content)
            label(page, pymupdf.Point(r.x0, r.y1 + 1), "rejected", "rejected")
        elif row.get("to"):
            line(str(row["from"]), str(row["to"]), "rejected", content, "rejected")
    for doc_no, pno in pages.items():
        page = doc[pno - 1]
        text = (f"pid_graph review markup - {doc_no}. Amber = pending, green = accepted, red = rejected or exception. "
                "Vision facts only; decide in the review register (fact ids are in the annotation notes).")
        a = page.add_freetext_annot(pymupdf.Rect(page.rect.x0 + 36, page.rect.y0 + 34, page.rect.x0 + 330, page.rect.y0 + 58), text,
                                    fontsize=6.5, fontname="helv", text_color=(0, 0, 0), fill_color=(1, 1, 0.85))
        a.set_info(content=text, title="pid_graph review")
        a.update()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    return out
