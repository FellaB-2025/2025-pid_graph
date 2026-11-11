"""Generate a SYNTHETIC per-unit P&ID PDF to exercise the title-block pass.

No real Aconex file is available on this machine. This PDF imitates the shape of
one - a transmittal cover page followed by one page per drawing, each with a
title block in the bottom-right corner - so the reader, the revision map, the
re-issue diff and the pipeline wiring can be tested. Replace with the real file
and re-run; the reader's region and regexes may need adjusting to the project's
title-block layout (that is expected and is a one-time calibration).

    python scripts/make_dummy_pdf.py            -> data/U100-PIDS-TX-0042.pdf  (first issue)
    python scripts/make_dummy_pdf.py --reissue  -> data/U100-PIDS-TX-0057.pdf  (PID-100-001 revised C -> D)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
FIRST = [("PID-100-001", "C", "FEED GAS INLET - INLET KO DRUM V-1002"),
         ("PID-100-002", "B", "FEED GAS INLET - PRESSURE CONTROL AND EXPORT"),
         ("PID-100-003", "A", "FEED GAS INLET - UTILITY CONNECTIONS")]
REISSUE = [("PID-100-001", "D", "FEED GAS INLET - INLET KO DRUM V-1002"),
           ("PID-100-002", "B", "FEED GAS INLET - PRESSURE CONTROL AND EXPORT"),
           ("PID-100-003", "A", "FEED GAS INLET - UTILITY CONNECTIONS")]


def build(out: Path, drawings: list[tuple], transmittal: str) -> Path:
    doc = pymupdf.open()
    # A3 landscape in points
    W, H = 1191, 842
    cover = doc.new_page(width=W, height=H)
    cover.insert_text((60, 80), "DOCUMENT TRANSMITTAL (DUMMY DATA - not a real facility)", fontsize=18)
    cover.insert_text((60, 120), f"Transmittal No. {transmittal}    Unit 100 - Feed Gas Inlet    P&ID set", fontsize=12)
    y = 170
    for d, r, t in drawings:
        cover.insert_text((60, y), f"{d}   Rev {r}   {t}", fontsize=11)
        y += 20
    for d, r, t in drawings:
        page = doc.new_page(width=W, height=H)
        page.draw_rect(pymupdf.Rect(30, 30, W - 30, H - 30), width=1.5)
        page.insert_text((60, 70), f"{d}  {t}  (dummy drawing body - no graphics)", fontsize=10)
        # Title block, bottom right
        x0, y0 = W - 30 - 420, H - 30 - 120
        page.draw_rect(pymupdf.Rect(x0, y0, W - 30, H - 30), width=1.5)
        page.insert_text((x0 + 10, y0 + 22), "DUMMY LNG PROJECT - UNIT 100 FEED GAS INLET", fontsize=9)
        page.insert_text((x0 + 10, y0 + 42), f"TITLE: {t}", fontsize=9)
        page.insert_text((x0 + 10, y0 + 66), f"DRAWING NO. {d}", fontsize=11)
        page.insert_text((x0 + 250, y0 + 66), f"REV. {r}", fontsize=11)
        page.insert_text((x0 + 10, y0 + 90), "SHEET 1 OF 1", fontsize=9)
        page.insert_text((x0 + 250, y0 + 90), "SCALE: NTS", fontsize=9)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reissue", action="store_true")
    a = ap.parse_args()
    if a.reissue:
        out = build(ROOT / "data" / "U100-PIDS-TX-0057.pdf", REISSUE, "TX-0057")
    else:
        out = build(ROOT / "data" / "U100-PIDS-TX-0042.pdf", FIRST, "TX-0042")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
