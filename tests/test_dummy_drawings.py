"""The synthetic U-100 P&ID PDFs carry drawn sheets (needed before Phase 3 of PIDKG_UPGRADE.md).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The drawings are fabricated by scripts/make_dummy_pdf.py from the dummy index, the pid_audit
topology export and the C&E. They must agree with the topology export, keep the planted
discrepancies, and leave the title blocks (and so the v1.2 graph) exactly as they were.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
PDFS = {"TX-0042": DATA / "U100-PIDS-TX-0042.pdf", "TX-0057": DATA / "U100-PIDS-TX-0057.pdf"}
MANIFEST = DATA / "U100-PIDS-DRAWN-CONTENT.json"
SHEETS = ("PID-100-001", "PID-100-002", "PID-100-003")
# Controllers are drawn (DCS bubbles) but pid_audit's flow walk does not list them.
DRAWN_NOT_IN_TOPOLOGY = {"PID-100-001": {"LIC-1006", "FIC-1004"}, "PID-100-002": {"PIC-1005"}, "PID-100-003": set()}

from pid_graph.loaders.titleblock import DEFAULT_REGION, read_title_blocks  # noqa: E402


def _script():
    spec = importlib.util.spec_from_file_location("make_dummy_pdf", ROOT / "scripts" / "make_dummy_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def topology() -> list[dict]:
    with (DATA / "pid_audit_U100_topology.csv").open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _tagged(sheet: dict) -> set[str]:
    tags = {x["tag"] for kind in ("equipment", "instruments", "components", "boundaries") for x in sheet[kind] if x.get("tag")}
    return tags | {c["other_item"] for c in sheet["off_page_connectors"] if c.get("other_item")}


def _end(sheet: dict, ref: str) -> str:
    """A line end as a tag: equipment or boundary tag, or the far-end item of an off-page connector."""
    for c in sheet["off_page_connectors"]:
        if c["id"] == ref:
            return c["other_item"] or ref
    for b in sheet["boundaries"]:
        if b["id"] == ref:
            return b.get("tag") or ref
    return ref


def _tag_order(sheet: dict, line: dict) -> list[str]:
    """Tagged things along a line in flow order (untagged fittings dropped), ends included."""
    by_id = {x["id"]: x for kind in ("instruments", "components") for x in sheet[kind]}
    mid = [by_id[i]["tag"] for i in line["order"] if by_id[i].get("tag")]
    return [_end(sheet, line["from"])] + mid + [_end(sheet, line["to"])]


# ---- the manifest agrees with the script, and the PDFs with the manifest -------
def test_manifest_file_is_what_the_script_draws(manifest):
    assert _script().drawn_content() == manifest
    assert tuple(manifest["sheets"]) == SHEETS


@pytest.mark.parametrize("issue", sorted(PDFS))
def test_pdf_pages_are_drawn_and_carry_every_tag(issue, manifest):
    import pymupdf
    with pymupdf.open(PDFS[issue]) as doc:
        assert doc.page_count == 4
        for n, doc_no in enumerate(SHEETS, start=1):
            page = doc[n]
            words = {w[4] for w in page.get_text("words")}
            assert len(page.get_drawings()) > 20, f"{doc_no} has no drawing graphics"
            sheet = manifest["sheets"][doc_no]
            for kind in ("equipment", "instruments", "components", "boundaries", "off_page_connectors"):
                for item in sheet[kind]:
                    for token in item["text"]:
                        assert token in words, f"{issue} {doc_no}: {token!r} of {item['id']} is not on the page"
            for line in sheet["lines"]:
                if line["line_no"]:
                    assert line["line_no"] in words


@pytest.mark.parametrize("issue,rev1", [("TX-0042", "C"), ("TX-0057", "D")])
def test_title_blocks_read_exactly_as_before(issue, rev1):
    recs = read_title_blocks(PDFS[issue])
    assert [(r["doc_no"], r["rev"], r["sheet"], r["of"]) for r in recs[1:]] == [
        ("PID-100-001", rev1, 1, 1), ("PID-100-002", "B", 1, 1), ("PID-100-003", "A", 1, 1)]
    assert recs[0]["doc_no"] is None and all(r["has_text_layer"] for r in recs)
    assert [r["title"] for r in recs[1:]] == ["FEED GAS INLET - INLET KO DRUM V-1002", "FEED GAS INLET - PRESSURE CONTROL AND EXPORT",
                                              "FEED GAS INLET - UTILITY CONNECTIONS"]


@pytest.mark.parametrize("issue", sorted(PDFS))
def test_nothing_but_the_title_block_in_the_title_block_region(issue):
    import pymupdf
    with pymupdf.open(PDFS[issue]) as doc:
        for page in list(doc)[1:]:
            r = page.rect
            clip = pymupdf.Rect(r.width * DEFAULT_REGION[0], r.height * DEFAULT_REGION[1], r.width, r.height)
            lines = [ln.strip() for ln in page.get_text("text", clip=clip).splitlines() if ln.strip()]
            assert len(lines) == 6 and lines[0].startswith("DUMMY LNG PROJECT") and lines[1].startswith("TITLE:")


# ---- the drawings agree with the pid_audit topology export ---------------------
def test_every_topology_row_is_drawn_in_that_order(manifest, topology):
    for row in topology:
        sheet = manifest["sheets"][row["sheet"]]
        a, b = row["from"], row["to"]
        if row["line_no"]:
            line = next(ln for ln in sheet["lines"] if ln["line_no"] == row["line_no"])
            order = _tag_order(sheet, line)
            assert a in order and b in order, f"{row}: not both on {row['line_no']} ({order})"
            assert order.index(b) == order.index(a) + 1, f"{row}: drawn order is {order}"
        else:
            inst = next(i for i in sheet["instruments"] if i["tag"] == b)
            assert inst["measures"] == {"item": a}


def test_tagged_items_per_sheet_match_the_topology_export(manifest, topology):
    for doc_no in SHEETS:
        in_csv = {t for r in topology if r["sheet"] == doc_no for t in (r["from"], r["to"])}
        assert _tagged(manifest["sheets"][doc_no]) - in_csv == DRAWN_NOT_IN_TOPOLOGY[doc_no]
        assert in_csv <= _tagged(manifest["sheets"][doc_no])


# ---- planted discrepancies survive ---------------------------------------------
def test_planted_discrepancies_are_kept(manifest):
    import pymupdf
    s1, s2, s3 = (manifest["sheets"][d] for d in SHEETS)
    everything = _tagged(s1) | _tagged(s2) | _tagged(s3)
    assert "TT-1003" not in everything            # X1: in the index, not on the drawing
    assert "PT-1001D" not in everything           # X4: C&E only
    assert "FT-1006" in _tagged(s2)               # X2: on the drawing, not in the index
    assert "XV-1002" in _tagged(s1) and "XV-1002" not in _tagged(s2)   # X3: index says PID-100-002
    assert _tagged(s3) == set()                   # X12: nothing tagged on PID-100-003
    with pymupdf.open(PDFS["TX-0057"]) as doc:
        text = " ".join(p.get_text() for p in doc)
    assert "1003" not in text and "1001D" not in text


# ---- what Phase 3 onwards needs is actually there -------------------------------
def test_drawings_exercise_the_v13_additions(manifest):
    sheets = manifest["sheets"].values()
    untagged = [c for s in sheets for c in s["components"] if not c.get("tag")]
    assert {c["kind"] for c in untagged} >= {"check_valve", "reducer", "gate_valve", "strainer"}
    purposes = {sig["purpose"] for s in sheets for sig in s["signals"]}
    assert purposes >= {"measurement", "control", "trip"}
    s1, s2 = manifest["sheets"]["PID-100-001"], manifest["sheets"]["PID-100-002"]
    out = {(c["line_no"], c["other_drawing"]) for c in s1["off_page_connectors"] if c["direction"] == "out"}
    into = {(c["line_no"], c["other_drawing"]) for c in s2["off_page_connectors"] if c["direction"] == "in"}
    assert out == {("L-102", "PID-100-002"), ("L-105", "PID-100-002")}
    assert into == {("L-102", "PID-100-001"), ("L-105", "PID-100-001")}
    assert any(not ln["line_no"] for ln in manifest["sheets"]["PID-100-003"]["lines"])     # a line with no number
    trips = {(sig["from"], sig["to"]) for sig in s1["signals"] if sig["purpose"] == "trip"}
    # drawn trips follow the C&E for SIF-100-01 and SIF-100-02; SIF-100-03 (PT-1001D) is not drawn at all
    for init in ("PT-1001A", "PT-1001B", "PT-1001C"):
        assert {(init, "XV-1001"), (init, "BDV-1001")} <= trips
    for init in ("LT-1002A", "LT-1002B"):
        assert {(init, "XV-1001"), (init, "XV-1002")} <= trips


def test_fail_positions_follow_the_index_remarks(manifest):
    fail = {c["tag"]: c.get("fail_position") for s in manifest["sheets"].values() for c in s["components"] if c.get("tag")}
    assert fail["PV-1005"] == "FO" and fail["LV-1006"] == "FC" and fail["XV-1001"] == "FC"
    assert fail["XV-1002"] == "FC" and fail["BDV-1001"] == "FO"
