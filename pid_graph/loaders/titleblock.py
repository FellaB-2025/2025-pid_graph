"""Aconex per-unit PDF: read the title block of every page (decisions section 7).

The page is not the document; the drawing is. Every page's title block is read
with PyMuPDF from a fixed region (deterministic regex, no LLM) and yields
drawing number + revision + sheet. Provenance is then "PID-100-001 rev C", never
"Unit100.pdf page 37".

Free change detection: on re-issue, run this pass on the new PDF and diff the
revisions per drawing against the graph; only revised sheets need re-extraction.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import ontology as O
from ..records import MemoryStore
from ..tags import canonical_id

# Title-block region as fractions of the page: (x0, y0, x1, y1). Bottom-right quarter
# strip is the norm for A1/A3 P&IDs; override per project.
DEFAULT_REGION = (0.55, 0.80, 1.0, 1.0)

TB_DOC_RE = re.compile(r"(?:DRAWING|DWG|DOCUMENT|DOC)\.?\s*(?:NO|NUMBER|N[O°])\.?\s*[:.]?\s*(?P<doc>[A-Z0-9][A-Z0-9\-_/.]{3,})", re.I)
TB_REV_RE = re.compile(r"\bREV(?:ISION)?\.?\s*[:.]?\s*(?P<rev>[A-Z0-9]{1,3})\b", re.I)
TB_SHEET_RE = re.compile(r"\bSHEET\s*[:.]?\s*(?P<sheet>\d+)\s*(?:OF|/)\s*(?P<of>\d+)", re.I)
TB_TITLE_RE = re.compile(r"\bTITLE\s*[:.]?\s*(?P<title>[^\n]{3,120})", re.I)


def read_title_blocks(pdf_path: str | Path, region: tuple = DEFAULT_REGION) -> list[dict]:
    """One record per page: page, doc_no, rev, sheet, of, title, has_text_layer, text."""
    import pymupdf
    pdf_path = Path(pdf_path)
    out = []
    with pymupdf.open(pdf_path) as doc:
        for pno, page in enumerate(doc, start=1):
            r = page.rect
            w, h = r.width, r.height
            clip = pymupdf.Rect(r.x0 + w * region[0], r.y0 + h * region[1], r.x0 + w * region[2], r.y0 + h * region[3])
            text = page.get_text("text", clip=clip) or ""
            full = page.get_text("text") or ""
            flat = " ".join(text.split())
            m_doc, m_rev, m_sheet, m_title = TB_DOC_RE.search(flat), TB_REV_RE.search(flat), TB_SHEET_RE.search(flat), TB_TITLE_RE.search(text)
            out.append({
                "file": pdf_path.name, "page": pno,
                "doc_no": canonical_id(m_doc.group("doc")) if m_doc else None,
                "rev": m_rev.group("rev").upper() if m_rev else None,
                "sheet": int(m_sheet.group("sheet")) if m_sheet else None,
                "of": int(m_sheet.group("of")) if m_sheet else None,
                "title": m_title.group("title").strip() if m_title else "",
                "has_text_layer": bool(full.strip()),
                "text": flat[:300],
            })
    return out


def rev_map(records: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """{doc_no: rev} from title-block records, plus problems (pages without a title
    block, or one drawing number seen with two revisions in the same issue)."""
    revs: dict[str, str] = {}
    problems = []
    for r in records:
        if not r["has_text_layer"]:
            problems.append({**r, "problem": "no text layer (scanned/flattened page) - extraction impossible"})
            continue
        if not r["doc_no"] or not r["rev"]:
            problems.append({**r, "problem": "title block not recognised (no drawing number / revision)"})
            continue
        if r["doc_no"] in revs and revs[r["doc_no"]] != r["rev"]:
            problems.append({**r, "problem": f"drawing seen with rev {revs[r['doc_no']]} and rev {r['rev']} in the same issue"})
            continue
        revs[r["doc_no"]] = r["rev"]
    return revs, problems


def diff_against_store(revs: dict[str, str], store) -> dict:
    """Which drawings are new, revised or unchanged relative to what the graph holds."""
    current: dict[str, set] = {}
    for d in store.nodes("Document"):
        if d["props"].get("doc_type") == "PID" and d["key"]["rev"] != O.UNKNOWN_REV:
            current.setdefault(d["key"]["doc_no"], set()).add(d["key"]["rev"])
    new, revised, unchanged = [], [], []
    for doc_no, rev in sorted(revs.items()):
        if doc_no not in current:
            new.append({"doc_no": doc_no, "rev": rev})
        elif rev in current[doc_no]:
            unchanged.append({"doc_no": doc_no, "rev": rev})
        else:
            revised.append({"doc_no": doc_no, "from": sorted(current[doc_no]), "to": rev})
    return {"new": new, "revised": revised, "unchanged": unchanged,
            "re_extract": [d["doc_no"] for d in new + revised]}


def register_drawings(store: MemoryStore, records: list[dict], *, unit: str, load_run: str,
                      transmittal: str | None = None) -> dict:
    """Document nodes with their real revision (not stubs) for every drawing the PDF carries."""
    revs, problems = rev_map(records)
    pages: dict[str, list] = {}
    titles: dict[str, str] = {}
    for r in records:
        if r["doc_no"] and r["rev"] and revs.get(r["doc_no"]) == r["rev"]:
            pages.setdefault(r["doc_no"], []).append(r["page"])
            titles.setdefault(r["doc_no"], r["title"])
    for doc_no, rev in revs.items():
        first = pages[doc_no][0]
        store.merge_node("Document", {"doc_no": doc_no, "rev": rev}, {
            "doc_type": "PID", "title": titles.get(doc_no, ""), "unit": unit,
            "file": records[0]["file"] if records else "", "pages": pages[doc_no],
            "sheets": len(pages[doc_no]), "transmittal": transmittal or "",
            "source_doc": doc_no, "source_rev": rev, "source_sheet": f"page {first}",
            "extracted_by": "pid_audit", "load_run": load_run,
            "source_ref": f"{records[0]['file'] if records else ''}:p{first}"})
    return {"file": records[0]["file"] if records else "", "pages": len(records), "drawings": len(revs),
            "rev_map": revs, "problems": problems,
            "no_text_layer_pages": [p["page"] for p in problems if "no text layer" in p["problem"]]}
