# RUN.md — pid-to-kg extraction of the synthetic U-100 P&IDs

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

This folder is the **frozen input** for every later test of the v1.3 loader
(`PIDKG_UPGRADE.md`, Phase 3). Vision extraction is not deterministic: do not regenerate these
files casually. A re-run is a new fixture and needs its own review.

## The run

| | |
|---|---|
| Date | 10 Nov 2026 local (2026-11-11 UTC) |
| Input | `data/U100-PIDS-TX-0057.pdf`, pages 2–4 (PID-100-001 rev D, PID-100-002 rev B, PID-100-003 rev A) |
| Tool | pid-to-kg 0.1.0 at commit `7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1`, unmodified (`THIRD_PARTY_NOTICES.md`) |
| Environment | `.venv-pidkg`, Python 3.14.3 |
| Model | Claude Fable 5.2 (`claude-fable-5-2`), run as a subagent of a Claude Code session and inheriting that session's model |
| Work directory | `work/U-100` (git-ignored) |
| Run time | Scripts (probe, render, hints): under 1 minute. Vision extraction of three sheets plus build and QA: about 3 minutes |
| Build / QA iterations | 1 (first build: 0 errors) |

Steps, as in the tool's `SKILL.md`: probe (`--pages 2-4`) → render → orientation check → hints →
one `extract/page_NN.json` per sheet → build → QA.

- **Probe:** all three pages `vector_text` (vector drawing with a text layer).
- **Render:** 5000 × 3535 px per page, 12 tiles each, none blank. Rotation 0, confirmed by eye.
- **Hints:** from the PDF text layer only. **OCR was not installed** (the OCR package supports
  Python 3.10–3.12; this machine has 3.14), so OCR hints and automatic orientation were skipped.
- **Extraction:** all 12 tiles of each sheet read; one zoom crop (the strainer on PID-100-003).
  Nothing was put in `unreadable`.

## Independence of the read

The drawings were fabricated by `scripts/make_dummy_pdf.py` in the same Claude Code session.
To keep the read honest, the extraction was done by a fresh subagent that was told not to open
that script, `data/` (including the answer key `data/U100-PIDS-DRAWN-CONTENT.json`), the index or
any other U-100 document, and to work only from the rendered images and the tool's procedure.
It reported that it opened none of them; that is its own statement and was not otherwise audited.

These are clean vector sheets with a text layer. The result says the pipeline works end to end;
it says nothing about accuracy on real or scanned drawings (Phase 9).

## Result

| Node type | Count | | Relationship type | Count |
|---|---|---|---|---|
| Sheet | 3 | | FLOWS_TO | 56 |
| Equipment | 1 | | MEMBER_OF | 25 |
| Component | 16 (6 tagged, 10 untagged) | | SIGNAL_TO | 14 |
| Instrument | 16 | | TRIPS (derived) | 14 |
| PipeSegment | 27 | | MEASURES | 11 |
| OffPageConnector | 4 | | ACTUATES (derived) | 10 |
| Boundary | 9 | | FEEDS (derived) | 7 |
| ControlLoop | 7 (3 control, 4 interlock) | | PART_OF | 3 |
| Plant | 1 | | | |
| **Total** | **84** | | **Total** | **140** |

QA report: **0 errors, 1 warning, 0 info.**

- `loop_no_final_element` on `LOOP:F-1004` — checked on the drawing and left: FIC-1004 has one
  signal, from FT-1004, and no flow valve is drawn. The loop register calls it flow indication.

## Checked against the answer key

After the run, the page files were compared with `data/U100-PIDS-DRAWN-CONTENT.json`:

- every drawn tag was extracted, on the right sheet; nothing was invented except as noted below;
- all nine lines have the right number, size, service, ends, direction and in-line order;
- all ten untagged fittings were found with the right kind;
- fail positions (FC / FO) match on all six actuated valves;
- both off-page connector pairs (L-102, L-105) were paired across the two sheets;
- TT-1003 and PT-1001D do not appear, as intended.

## What the tool did that the loader must expect (for Phase 4 and Phase 6)

1. **Interlock diamonds became instruments.** pid-to-kg has no logic symbol, so `I-1` and `I-2`
   were recorded as Instruments (location `sis`, names `SIF-100-01` / `SIF-100-02`). Drawn trip
   signals therefore run in two hops: initiator → `I-1` → final element. `I-1` and `I-2` are not
   in the index, so under T1 they become exceptions, and the two-hop signals need handling.
2. **Derived `TRIPS` over-reaches.** The tool groups loops by letter and number, so PI-1001 was
   pulled into loop P-1001 and LG-1002 into loop L-1002, and `TRIPS` relationships were derived
   from both (for example PI-1001 → XV-1001). Neither has a signal line on the drawing. The
   Phase 6 drawing-vs-C&E check should use the drawn `SIGNAL_TO` with `purpose = trip`, not `TRIPS`.
3. **Each SIF appears as two interlock loops:** `LOOP:I-1` and `LOOP:P-1001`; `LOOP:I-2` and
   `LOOP:L-1002`.
4. **Boundaries carry the flag text, not the tag:** `FEED GAS FROM BL-100`, `BLOWDOWN TO FLARE-HDR`,
   `LIQUID TO BL-103`, `FEED GAS TO BL-200`. Matching them to `BL-100`, `FLARE-HDR`, `BL-103` and
   `BL-200` needs more than a name-equals test.
5. **Drawn controllers are in no register:** LIC-1006, FIC-1004, PIC-1005 (T1 exceptions).
6. **Taps on one stretch share a segment.** PT-1001A/B/C and PI-1001 are all "after XV-1001"; their
   order along L-101 is not recorded.
7. **Line ids are local** (`L1`, `L2`, …); the printed number is in `line_number` (`L-101`).
8. **Things with no field in the tool's schema** went into names and notes: voting (2oo3), the SIF
   number, "locked open".

## Files

| File | What it is |
|---|---|
| `graph.json` | pid-to-kg's canonical graph, copied unchanged from `work/U-100/kg/` |
| `qa_report.md` | its QA report, copied unchanged |
| `extract/page_02.json`, `page_03.json`, `page_04.json` | the per-sheet extractions the graph was built from (not asked for by the plan; kept so the graph can be rebuilt without re-reading the drawings) |

Not kept: `graph.duckdb`, `summary.md`, the renders and tiles (all reproducible from the above).
