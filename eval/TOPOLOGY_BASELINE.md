# TOPOLOGY_BASELINE.md — first topology eval of the U-100 vision extraction

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Date: 10 Nov 2026. Extraction: `tests/fixtures/pidkg_U-100/graph.json` (pid-to-kg 0.1.0, see its
`RUN.md`). Gold: `eval/gold_topology_U-100.json`, built from the drawings' answer key by
`eval/make_topology_gold.py`. Reproduce with:

```
.venv\Scripts\python -m eval.topology_eval --pidkg-eval
```

**No pass threshold is set.** `PIDKG_UPGRADE.md` Phase 8 leaves that to Alan after this first run.

## What these numbers are, and are not

They are the score of one extraction of three clean, synthetic vector sheets that carry a text
layer, read without OCR. They show the scorer and the pipeline work, and they show where
pid-to-kg's own conventions differ from the drawing. They say nothing about real or scanned
drawings; that is Phase 9.

## pid_graph's scorer (`eval/topology_eval.py`): extraction against the drawings, before the gate

| | Gold | Predicted | Correct | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Tags | 21 | 23 | 21 | 0.913 | 1.000 | 0.955 |
| Equipment-level flow pairs | 7 | 7 | 7 | 1.000 | 1.000 | 1.000 |
| Loops | 5 | 7 | 5 | 0.714 | 1.000 | 0.833 |
| Loop members | 17 | 25 | 17 | 0.68 | 1.000 | 0.810 |

- **Instrument placement: 11 / 11** exact (right line and right neighbours either side, or
  right equipment); 11 / 11 on the right line.
- Flow pairs that also name the right line: 5 / 5 (the two utility lines have no number).

Nothing was missed. Everything that costs precision comes from two conventions of the tool, not
from misreading the sheets:

1. **Interlock diamonds read as tags.** `I-1` and `I-2` were extracted as instruments, so they
   count as two spurious tags and two spurious loops with six spurious members.
2. **Loops grouped by tag number.** PI-1001 was put in loop P-1001 and LG-1002 in loop L-1002;
   neither has a signal line.

pid_graph's loader already deals with both: the diamonds are collapsed into direct trip signals
(X29) and gauges have no role in the closed list, so none of the ten spurious items is loaded.

## After the gate: review workload

| | |
|---|---|
| Facts in the review register | 120 |
| Flagged for priority review (T5) | 20 of 120 (0.167): 18 touch an untagged fitting, 2 cross sheets |
| Below 0.85 confidence | 0 |
| Pending, PID-100-001 | 85 |
| Pending, PID-100-002 | 35 |
| Pending, PID-100-003 | 0 (its two lines have no number, so nothing is loaded: X25) |

## pid-to-kg's own scorer (`eval_kg.py`, unmodified, on `eval/gold_pidkg_U-100.json`)

| | pid-to-kg `eval_kg.py` | pid_graph `topology_eval.py` |
|---|---|---|
| Tags | P 0.913, R 1.0 | P 0.913, R 1.0 |
| Flow | P 1.0, R 1.0 | P 1.0, R 1.0 |
| Instrument placement | 11 / 11 (nearest equipment) | 11 / 11 (line and both neighbours) |
| Loops | recall 1.0, mean member overlap 0.927 | P 0.714, R 1.0; members P 0.68, R 1.0 |

The two agree except on loops, where they measure different things. `eval_kg.py` scores only
the gold loops (were they found, and how much do their members overlap), so the two extra
`I-1` / `I-2` loops cost nothing there; it sees PI-1001 and LG-1002 as extra members, which is
the 0.927. pid_graph's scorer also counts loops and members that should not exist. Placement
differs in strictness: theirs asks for the nearest equipment, ours for the segment.

One correction made while setting this up: the first gold file in pid-to-kg's format named the
blowdown destination "BLOWDOWN TO FLARE HEADER" where the flag reads "BLOWDOWN TO FLARE-HDR".
That was an error in the gold, not in the extraction, and gave a false 0.857 on flow until fixed.
