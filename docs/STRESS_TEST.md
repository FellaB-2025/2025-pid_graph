# STRESS_TEST.md — pid-to-kg on real public drawings (Phase 9 pilot)

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Date: 10 Nov 2026. Extraction only: these plants have no instrument index here, so nothing was
reconciled, gated or loaded into pid_graph. Scores are in `eval/stress_test_scores.json`
(numbers only). **No drawing, render, marked-up PDF, tag list, gold file or extracted graph is in
this repository**; they stay in `data/external/` and `work/`, both git-ignored. The drawings are
public records and remain under their owners' terms.

## Read this before the numbers

1. **This is a pilot: two sheets from each set, not the sets.** Pahala has 17 P&ID sheets and
   Virden 10. Extraction cost about 80,000 to 110,000 tokens a sheet, so the full 27 would be
   roughly 2.5 million. Whether that is worth running is Alan's call.
2. **The gold files are not checked by an engineer.** Each was written by a second, independent
   model reader that could not see the extraction. A score here is *agreement between two
   machine reads*, not accuracy. Two readers of the same kind can agree and both be wrong.
3. **No OCR.** This machine has Python 3.14 and the tool's OCR package needs 3.10 to 3.12, so
   there were no OCR hints and no automatic rotation. The scans had no hints at all.

## What was run

| | Pahala WWTP | Virden WWTF |
|---|---|---|
| Source | `epa.gov`, design-build drawings, 23 Jul 2021 | `gov.mb.ca`, Phase 2 P&ID drawings, 26 Apr 2019 |
| Kind | Digital vector PDF; most text drawn as outlines | Scans, about 150 dpi, no text layer |
| P&ID pages in the set | 9–25 | 5–14 |
| Pages extracted | 11 and 20 | 6 and 14 |
| Page scored against a gold file | 11 and 20 | 6 |
| Tool | pid-to-kg 0.1.0 at commit `7ee3a82`, unmodified | same |
| Extraction time, tokens | about 4 minutes, 163,000 | about 7.5 minutes, 214,000 |

Steps per set: probe, render, text-layer hints, one page file per sheet written by a model
reading the tiles, build, QA to zero errors, then
`python -m pid_graph.load_pidkg --graph work/<set>/kg/graph.json --no-master --report-only`.

## Report-only counts

| | Pahala (2 sheets) | Virden (2 sheets) | U-100 synthetic (3 sheets) |
|---|---|---|---|
| Nodes / relationships | 50 / 56 | 338 / 458 | 84 / 140 |
| Tagged equipment, instruments, valves | 3, 11, 3 | 17, 88, 51 | 1, 16, 6 |
| Untagged fittings | 4 | 20 | 10 |
| Pipe segments on a numbered line | 0 of 12 | 79 of 112 | 21 of 27 |
| Off-page connectors paired | 0 of 4 | 0 of 2 | 4 of 4 |
| Items marked unreadable | 0 | 7 | 0 |
| QA errors / warnings | 0 / 7 | 0 / 19 | 0 / 1 |
| Facts below 0.85 confidence | 19 of 89 | 107 of 659 | 1 of 164 |
| **T5 flag rate** | **26 of 67 (0.388)** | **140 of 564 (0.248)** | 32 of 146 (0.219) |

Every off-page connector is unpaired because the sheets they point to were not extracted.

## Scores against the independent gold files (pid-to-kg's own `eval_kg.py`)

| Sheet | Tags | Flow pairs | Instrument placement | Loops |
|---|---|---|---|---|
| Pahala p.11, as scored | P 0.867, R 0.929 | 0 of 4 | 0 of 5 | recall 1.0, member overlap 1.0 |
| Pahala p.11, basin's two identifiers treated as one | P 0.933, R 1.0 | 0 of 4 | 2 of 5 | same |
| Pahala p.20 | 2 of 2 | gold has none; 1 extra | gold has none | recall 1.0, member overlap 0.5 |
| Virden p.6 | P 0.988, R 1.0 (81 of 81) | P 0.385, R 0.714 | 12 of 12 | recall 1.0, member overlap 0.949 |

## What the numbers mean

**Tags were read well on both kinds of drawing.** On the scanned Virden sheet both readers
agreed on all 81 tags, and the one extra was a tag the gold reader saw and left out because one
character was fuzzy. The scans read better than "150 dpi" suggests.

**The flow score is not usable on isolated sheets.** pid-to-kg derives an equipment-level pair
only between equipment or named boundaries. On a single sheet most lines begin or end at an
off-page connector whose partner sheet is missing, so no pair is produced.
- Pahala p.11: 0 of 4, yet the extracted flow chain, checked by hand, has all four connections
  the gold describes. The zero is the metric, not the reading.
- Virden p.6: the two misses are the two lines that leave through the off-page connector. The
  eight extras are drains, a vent and a future sampler branch, which the extraction recorded
  and the gold reader deliberately left out as not being equipment-level flow.
A fair flow score needs the whole set extracted so connectors pair, and a written rule for
whether drains and vents count.

**Two readers disagree on conventions more than on what is drawn.**
- A basin printed with two identifiers was keyed by one reader as the first and by the other as
  the second. That alone moved five placements and one tag.
- Three transmitters drawn touching their sensing elements, with no line of their own: one
  reader placed them, the other would not add a connection that is not drawn.
- Whether a control panel is a tagged item, and whether it belongs in a loop.

**Real drawings need a legend.** On Pahala the difficulty was symbol meaning, not legibility: a
tie-point marker, a weir and an unusual valve symbol were all recorded at 0.6 to 0.7 confidence
with no legend sheet supplied. The set has legend sheets; they were not in the pilot.

**The drawings themselves are imperfect.** A pump tag printed with no number, a flag with no
sheet reference, no line numbers on one set, a label that contradicts the bubbles beside it.
An extraction that reports these faithfully is doing its job, and a gate that expects complete
tags will raise them as exceptions.

## Where pid-to-kg did not fit these drawings

- Six-digit tag numbers are not recognised as ISA tags; loops had to be set by hand on every instrument.
- No home for control panels, I/O cabinets or MCCs. Recorded as equipment, each raises a QA warning.
- No interlock or logic symbol (also seen on U-100).
- The same tag drawn in a PLC band and on a panel raises a duplicate warning every time.
- Line codes that are size-service-spec, repeated on many runs, cannot identify a run.
- "Typical of 2" shared I/O has no construct.
- Text-layer hints found only title-block strings where the tags are outlined, so the
  missed-tag check gave no safety net.

## What this says about the v1.3 design

- The gate matters more on real drawings: the T5 flag rate rose from 0.219 to 0.248 and 0.388,
  and low-confidence facts from under 1 % to 16–21 %.
- Flow that crosses sheets cannot be trusted until both sheets are extracted and the connector
  is paired, which is what the off-page flag in T5 is for.
- Identifier aliases need a rule before real data is loaded: one thing, two printed names.

## Not done

- The other 23 sheets.
- Engineer-checked gold. Until Alan checks one gold file against its sheet, treat every score
  above as unverified.
- A run with OCR.
- pid_graph's own scorer (`eval/topology_eval.py`) on these sheets: its gold format needs
  segment-level placements, which nobody has written for a real sheet.
