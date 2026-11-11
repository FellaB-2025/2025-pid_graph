"""Intake check for a new (real) document before it goes through the pipeline.

Answers, without touching the graph: will the loaders understand this file, and
what needs calibrating first? Run it on the first real instrument index, C&E, pid_audit
export and Aconex PDF you receive.

    python -m pid_graph.intake data/U100-INST-INDEX-Rev-B.xlsx
    python -m pid_graph.intake data/U100-CE-CHART-Rev-A.xlsx
    python -m pid_graph.intake data/pid_audit_U100_topology.csv
    python -m pid_graph.intake data/U100-PIDS-TX-0042.pdf

For xlsx/csv: sheets, detected document number and revision, the header row found,
which canonical columns matched (and via which spelling), which headers matched
nothing (candidates for the alias maps in loaders/tables.py), and how many tags the
canonical regex accepts or rejects (candidates for tags.py).
For PDF: per page, text-layer presence and what the title-block regexes find in the
default region and in three alternative regions, so DEFAULT_REGION in
loaders/titleblock.py can be set for the project's layout.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .loaders import tables as T
from .tags import canonical_tag, classify, func_prefix

ALIAS_SETS = {"instrument index": T.INDEX_ALIASES, "alarm register": T.ALARM_ALIASES,
              "cause & effect": T.CE_ALIASES, "topology export": T.TOPOLOGY_ALIASES,
              "SRS register": T.SRS_ALIASES, "LOPA scenarios": T.LOPA_SCENARIO_ALIASES, "LOPA IPLs": T.LOPA_IPL_ALIASES}
TAG_COLUMNS = ("tag", "alarm_tag", "sensor_tag", "cause_tag", "effect_tag", "from_tag", "to_tag", "via_line", "line", "equipment", "protects")


def _best_alias_set(headers: list[str]) -> tuple[str, dict, int]:
    best = ("", {}, 0)
    for name, aliases in ALIAS_SETS.items():
        accepted = {a: canon for canon, names in aliases.items() for a in names}
        hits = sum(1 for h in headers if h in accepted)
        if hits > best[2]:
            best = (name, aliases, hits)
    return best


def inspect_table(path: Path, sheet: str | None) -> list[str]:
    lines = []
    rows, title = T.raw_rows(path, sheet)
    doc_no, rev, how = T.detect_document(path, sheet)
    lines.append(f"sheet {title!r}: {len(rows)} rows; document {doc_no} rev {rev} (from {how})")
    hdr_idx = T._detect_header_row(rows, None)
    # Try every alias set; report the one that matches most headers.
    candidates = []
    for name, aliases in ALIAS_SETS.items():
        i = T._detect_header_row(rows, aliases)
        headers = [T.norm(h) for h in rows[i]] if rows else []
        accepted = {a: canon for canon, names in aliases.items() for a in names}
        hits = [(h, accepted[h]) for h in headers if h in accepted]
        candidates.append((len(hits), name, i, headers, hits, aliases))
    hits_n, name, i, headers, hits, aliases = max(candidates, key=lambda c: c[0])
    if hits_n < 2:
        lines.append(f"  no alias set matches at least two headers (best: {name}); header row guess = {hdr_idx + 1}")
        lines.append(f"  headers seen: {[T.norm(h) for h in rows[hdr_idx]] if rows else []}")
        return lines
    matched = {canon: h for h, canon in hits}
    if name == "instrument index" and "loop" in matched and "tag" not in matched:
        lines.append(f"  looks like: a loop register (header row {i + 1}). Not loaded in v1.1 - Loop is not a label; "
                     "the index's loop number is kept as Instrument.loop (D-P1-09).")
        return lines
    lines.append(f"  looks like: {name}; header row {i + 1}; {hits_n} of {len([h for h in headers if h])} headers recognised")
    lines.append(f"  matched : {', '.join(f'{c} <- {h!r}' for c, h in matched.items())}")
    unmatched = [h for h in headers if h and h not in {h_ for h_, _ in hits}]
    if name == "cause & effect":
        effect_cols = [h for h in unmatched if canonical_tag(h.replace("_", "-"))]
        unmatched = [h for h in unmatched if h not in effect_cols]
        if effect_cols:
            lines.append(f"  matrix effect columns (tags across the top): {[h.upper().replace('_', '-') for h in effect_cols]}")
    if unmatched:
        lines.append(f"  UNMATCHED headers (add to loaders/tables.py aliases if they carry data you need): {unmatched}")
    if name == "instrument index" and "tag" not in matched:
        lines.append("  PROBLEM: no tag column recognised - the index loader cannot run")
    elif name == "cause & effect" and "cause_tag" not in matched:
        lines.append("  PROBLEM: no cause tag column recognised - the C&E loader cannot run")
    elif name == "topology export" and not ({"from_tag", "to_tag"} <= set(matched)):
        lines.append("  PROBLEM: from/to columns not recognised - the topology loader cannot run")
    # Tag shape check on every tag-like column
    data = T.read_table(path, sheet, aliases)
    for col in TAG_COLUMNS:
        vals = [r[col] for r in data if r.get(col)]
        if not vals:
            continue
        ok = [v for v in vals if canonical_tag(v)]
        bad = [v for v in vals if not canonical_tag(v)]
        kinds = Counter(classify(v)[0] for v in vals)
        lines.append(f"  column {col!r}: {len(vals)} values, {len(ok)} tag-shaped, {len(bad)} not; classified {dict(kinds)}")
        if bad:
            lines.append(f"    NOT tag-shaped (check tags.py TAG_RE / prefixes): {sorted(set(bad))[:12]}{' ...' if len(set(bad)) > 12 else ''}")
        if col in ("tag", "cause_tag", "effect_tag", "sensor_tag", "alarm_tag"):
            prefixes = Counter(func_prefix(canonical_tag(v)) for v in ok)
            unknown = sorted(p for p in prefixes if classify(f"{p}-100")[0] != "Instrument")
            if unknown:
                lines.append(f"    prefixes NOT recognised as instruments (add to tags.py if they are): {unknown}")
    return lines


def inspect_pdf(path: Path) -> list[str]:
    from .loaders.titleblock import DEFAULT_REGION, TB_DOC_RE, TB_REV_RE, TB_SHEET_RE, read_title_blocks
    import pymupdf
    lines = []
    regions = {"default (bottom-right)": DEFAULT_REGION, "bottom strip": (0.0, 0.85, 1.0, 1.0),
               "right strip": (0.80, 0.0, 1.0, 1.0), "bottom-right wide": (0.40, 0.70, 1.0, 1.0)}
    with pymupdf.open(path) as doc:
        lines.append(f"{path.name}: {len(doc)} pages")
        for pno, page in enumerate(doc, start=1):
            full = page.get_text("text") or ""
            if not full.strip():
                lines.append(f"  page {pno}: NO TEXT LAYER (scanned/flattened) - extraction impossible without OCR")
                continue
            found = []
            for name, (x0, y0, x1, y1) in regions.items():
                r = page.rect
                clip = pymupdf.Rect(r.x0 + r.width * x0, r.y0 + r.height * y0, r.x0 + r.width * x1, r.y0 + r.height * y1)
                flat = " ".join((page.get_text("text", clip=clip) or "").split())
                d, v, s = TB_DOC_RE.search(flat), TB_REV_RE.search(flat), TB_SHEET_RE.search(flat)
                found.append((name, d.group("doc") if d else None, v.group("rev") if v else None, s.group(0) if s else None))
            hit = next((f for f in found if f[1] and f[2]), None)
            if hit:
                lines.append(f"  page {pno}: drawing {hit[1]} rev {hit[2]} {hit[3] or ''} via region '{hit[0]}'"
                             + ("" if hit[0].startswith("default") else "  <- set DEFAULT_REGION to this"))
            else:
                lines.append(f"  page {pno}: title block NOT recognised in any region. Regex hits per region: "
                             + "; ".join(f"{n}: doc={d} rev={v}" for n, d, v, _ in found))
                sample = " | ".join(" ".join(t.split()) for t in full.splitlines() if t.strip())[:300]
                lines.append(f"    text sample: {sample}")
    recs = read_title_blocks(path)
    ok = [r for r in recs if r["doc_no"] and r["rev"]]
    lines.append(f"  with current DEFAULT_REGION: {len(ok)} of {len(recs)} pages yield drawing+rev")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--sheet", default=None, help="one sheet to inspect (default: every sheet)")
    a = ap.parse_args(argv)
    p = Path(a.path)
    if not p.exists():
        print(f"not found: {p}")
        return 1
    print(f"=== intake: {p.name} ===")
    if p.suffix.lower() == ".pdf":
        out = inspect_pdf(p)
    else:
        sheets = [a.sheet] if a.sheet else T.sheet_names(p)
        out = []
        for s in sheets:
            out += inspect_table(p, s if p.suffix.lower() in (".xlsx", ".xlsm") else None)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
