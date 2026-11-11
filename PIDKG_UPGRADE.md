# PIDKG_UPGRADE.md — pid_graph v1.2 → v1.3 (segment topology + vision extraction)

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.
Third-party tool referenced: `pid-to-kg`, MIT licence, Copyright (c) 2026 The pid-to-kg contributors
(https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph, pinned at commit `7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1`, 8 Nov 2026).

**For Claude Code, run from the `pid_graph` folder on Alan's laptop.** Read this file and `CLAUDE.md` in full before touching anything.

---

## 0. Read this first

### What this upgrade is
pid_graph stays the governed plant model. `pid-to-kg` becomes one more *loader source* for the P&ID layer:
it reads the drawings with vision and hands back pipe-segment topology, in-line items, signal lines and
control loops. pid_graph decides what is allowed into the graph.

One sentence to hold on to: **vision proposes, the instrument index disposes, an engineer accepts.**

### What this plan was written from (and what it was not)
Written from: the v1.2 dump `graph_U-100.json` (as committed in kg_suppression `tests/fixtures/pid_graph_U-100.json`),
kg_suppression's `load_pid.py`, and the pid-to-kg repository at the pinned commit.
**Not** written from the pid_graph source itself. So file names inside pid_graph are unknown to this plan.
Phase 0 exists to close that gap. Where this plan and the repo disagree, the repo wins: stop and report.

### Assumed v1.2 baseline (verify in Phase 0)
- Labels seen in the U-100 dump (7): `Document, Instrument, Line, Equipment, Alarm, SIF, Scenario`
- Relationship types seen (12): `SHOWN_ON, INSTALLED_ON, MEASURES, FEEDS, PROTECTS, INITIATES, CREDITS, ACTUATES,
  GENERATES, THREATENS, COMPENSATES_FOR, RAISES`
- Dump shape: `{"nodes": [{label, key, props}], "rels": [{type, start_label, start_key, end_label, end_key, props}], "conflicts": []}`
- Provenance on every node and rel: `source_doc, source_rev, source_sheet, extracted_by, load_run, source_ref`
  (`extracted_by` is one of `table`, `manual`, `pid_audit` today); nodes also carry `stub`
- Topology today is line-level: `FEEDS` Equipment→Line→Equipment from `pid_audit_U100_topology.csv`, with a `confidence`
- Valves are `Instrument` with a `role` (`final_element`, `manual_valve`, …)
- Ontology document: `PID_GRAPH_ONTOLOGY_V1_2.md`

### Rules for this build
1. One phase = one commit. Tests first. `python -m pytest -q` green before every commit.
2. Additive only. No v1.2 label, relationship, property or key changes meaning. No existing test is edited to make it pass.
3. The v1.2 dump for U-100 must be reproducible byte-for-byte with the new loader switched off.
4. Closed vocabulary still applies. The only new labels and relationships are the ones in section 2.
5. Nothing is inferred by pid_graph. Anything that cannot be placed goes to the exception register with a reason.
6. Dry run by default, `--apply` to write. Same pattern as every other loader.
7. British spelling. Copyright header on every new file.
8. Do not copy pid-to-kg source into pid_graph modules. Use it as an unmodified tool (Phase 2). Its `LICENSE` file stays with it.
9. No real project drawings, tags or documents. Synthetic U-100 only, plus the public test sets in Phase 9 (never committed).

---

## 1. What comes from where

| Keep from pid_graph (unchanged) | Adopt from pid-to-kg |
|---|---|
| Plant-not-documents: one tag = one node | Pipes split into segments between in-line items |
| Instrument index as the master node list | In-line items (untagged valves, check valves, reducers) as nodes |
| Reconciliation + exception register + `conflicts` | Instrument tap located on an exact segment |
| C&E, SRS, LOPA layers; `COMPENSATES_FOR` curation | Flow direction marked `shown` or `inferred` |
| Provenance properties on every fact | `unreadable` list instead of guessing |
| CFIHOS / QUDT reference-data anchoring | Off-page connector pairing across sheets |
| Fixed Cypher templates for safety-relevant queries | Drawn signal lines and ISA-loop grouping |
| Gold-set eval, tagged baselines | Page classification, tiling, scan enhancement, OCR hints |
| pid_audit text-layer tags + PDF markup | Confidence scale (0.95 / 0.85 / 0.7 / 0.5), DEXPI class, LLM plant summary |

Deliberately **not** adopted:
- Their derived `TRIPS` and `ACTUATES` edges. In pid_graph, SIF logic comes from the C&E and SRS only. A drawn trip signal is
  used as a *cross-check* against the C&E (Phase 6), never as a source of `INITIATES` / `ACTUATES`.
- Tag-as-id merging without a master list. The index still decides which tagged nodes exist.
- DuckDB as the store. pid_graph keeps its own backends; pid-to-kg's `graph.json` is read as an input file only.

---

## 2. Ontology v1.3 (additive)

Write `PID_GRAPH_ONTOLOGY_V1_3.md` as v1.2 plus the items below. Nothing in v1.2 is removed or renamed.

### 2.1 New labels (3)

| Label | Key | What it is | Required props |
|---|---|---|---|
| `Segment` | `segment_id` = `<line_no>.<k>` (or `<doc_no>.<local>.<k>` when the line has no number) | A stretch of one Line between two in-line items | `line_no`, `size`, `service`, `review` |
| `InlineItem` | `item_id` = `<doc_no>.<local>` | An **untagged** in-line valve or fitting (check valve, reducer, untagged manual valve, strainer, blind) | `kind`, `normal_position`, `indexed=false`, `review` |
| `ControlLoop` | `loop_key` (e.g. `P-1005`) | A loop grouped from ISA tag numbers and drawn signal lines | `loop_type`, `variable`, `review` |

Rules:
- A **tagged** valve stays an `Instrument` (index is master). It is *not* duplicated as an `InlineItem`.
- `InlineItem` is the one place a node may exist without an index row, because it has no tag to index. It can never be
  the start or end of `INITIATES, ACTUATES, PROTECTS, CREDITS, COMPENSATES_FOR, GENERATES`. Add a validator and a test.
- Off-page connectors are **not** nodes. A paired connector becomes one `FLOWS_TO` with `off_page=true`. An unpaired one is an exception.
- Battery limits and headers stay `Equipment` as in v1.2 (`BL-100`, `FLARE-HDR`). pid-to-kg `Boundary` nodes map onto them by name, else exception.

### 2.2 New relationship types (4)

| Type | From → To | Props |
|---|---|---|
| `SEGMENT_OF` | Segment → Line | — |
| `FLOWS_TO` | Segment / Equipment / Instrument (in-line or valve) / InlineItem → same set | `flow_direction` (`shown`/`inferred`), `off_page`, `confidence`, `review` |
| `SIGNAL_TO` | Instrument → Instrument / Equipment | `signal_type`, `purpose` (`control`, `measurement`, `trip`, `alarm`, `status`, `unknown`), `confidence`, `review` |
| `MEMBER_OF` | Instrument → ControlLoop | `role` (`sensor`, `controller`, `relay`, `final_element`) |

### 2.3 Existing types with a wider range
- `MEASURES`: Instrument → **Segment** now allowed, alongside the v1.2 Instrument → Line / Equipment. The index-sourced Line edge stays;
  the Segment edge is added beside it with its own provenance.
- `INSTALLED_ON`: Instrument (valve) → **Segment** allowed, same rule.
- `FEEDS`: unchanged. A second, **derived** `FEEDS` set is computed by walking `FLOWS_TO` (props `derived=true`, `via_lines`), and is
  compared against the v1.2 `FEEDS` from `pid_audit_*_topology.csv` in Phase 6. Disagreement is a `conflict`, never a silent overwrite.

### 2.4 New provenance values and the review property
- `extracted_by="pidkg_vision"` on everything this loader writes. `source_ref` = `<pdf>:p<page>:bbox=<x0,y0,x1,y1>`.
- `confidence` carried through unchanged from pid-to-kg.
- `review` ∈ `pending | accepted | rejected`. Default `pending` for every `pidkg_vision` fact.
- `dexpiClass` on Equipment / Instrument / InlineItem, beside the existing CFIHOS `refClass`. Informative only.

### 2.5 New competency questions (add to the existing eight)
- CQ9 **Isolation**: which valves (tagged or not) sit between instrument X's tap and the next equipment, each way?
- CQ10 **Same-pressure-system candidates**: which other instruments sense a segment reachable from sensor X without crossing a
  closed-in-normal-operation or actuated valve? (Feeds the compensating-measure *candidate* list. Curation stays manual.)
- CQ11 **MOC blast radius**: everything downstream of valve or segment X up to the next equipment, and every loop and SIF that touches it.
- CQ12 **Loop membership**: for final element X — its loop, its sensor, and the segment the sensor measures.
- CQ13 **Drawing vs C&E**: every drawn `purpose=trip` signal with no matching `INITIATES`/`ACTUATES`, and every C&E cause/effect
  with no drawn trip signal.

---

## 3. Trust rules (the gate)

| # | Rule |
|---|---|
| T1 | Index is master. A tagged pid-to-kg node whose normalised tag is not in the index → exception `on P&ID (vision), not in index`. No node. |
| T2 | Index tag never seen by vision on any sheet it is `SHOWN_ON` → exception `in index, not found on P&ID (vision)`. |
| T3 | Three-way tag check per sheet: index ∩ pid_audit text layer ∩ vision. Report each of the seven regions; only the centre is clean. |
| T4 | Every `pidkg_vision` fact is written with `review=pending`. |
| T5 | Auto-flag for priority review: `confidence < 0.85`, `flow_direction=inferred`, `off_page=true`, any edge touching an `InlineItem`. |
| T6 | Items in pid-to-kg's `unreadable` list and every pid-to-kg QA `error` / `warning` → one exception row each. Never a node. |
| T7 | **Safety-relevant Cypher templates traverse only facts where `extracted_by IN ['table','manual','pid_audit'] OR review='accepted'`.** Exploratory templates may use `pending` facts, and must say so in their output header. |
| T8 | A `rejected` fact stays in the review register (with reviewer and reason) and is removed from the graph on the next load. |

Review register: `registers/topology_review_<unit>.csv`, one row per `pidkg_vision` edge and node —
`fact_id, type, from, to, sheet, bbox, confidence, flags, review, reviewer, reviewed_on, comment`.
The loader reads it back on every run, so a decision survives a re-extraction (match on `fact_id` = stable hash of type + endpoints + sheet).
Also emit the pid_audit-style colour-coded PDF markup for pending facts, so review is done on the drawing, not in a spreadsheet alone.

---

## 4. Phases

### Phase 0 — Inventory and baseline (no code changes)
1. Read `CLAUDE.md`, `PID_GRAPH_ONTOLOGY_V1_2.md`, the decisions doc and the loaders.
2. Run the tests and the U-100 build. Confirm the dump matches the "assumed baseline" above (labels, types, provenance keys).
3. `git tag v1.2-baseline`.
4. Write `docs/V1_3_INVENTORY.md`: actual file names for the loaders, the exception register, the Cypher templates, the eval and the gold set; any difference from this plan's assumptions.
5. **Stop and report if a label or relationship in section 2 already exists with a different meaning.**

Done when: tag exists, inventory committed, tests green.

### Phase 1 — Ontology v1.3 on paper and in the validators
1. `PID_GRAPH_ONTOLOGY_V1_3.md` (section 2). Update the closed lists in `CLAUDE.md`.
2. Extend the schema/validators: 3 labels, 4 types, widened ranges, `review`, the `InlineItem` safety-edge ban.
3. Tests: a made-up five-node graph per new label/type; a test that an `InlineItem` on an `INITIATES` edge is refused.

Done when: v1.2 dump unchanged byte-for-byte; new validators tested.

### Phase 2 — Bring in pid-to-kg as an unmodified tool
1. `git clone https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph third_party/pid-to-kg` then `git -C third_party/pid-to-kg checkout 7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1`.
   Add `third_party/` to `.gitignore`; record the URL and commit in `THIRD_PARTY_NOTICES.md` with the MIT copyright line.
2. Separate virtual environment `.venv-pidkg` from `third_party/pid-to-kg/skills/pid-to-kg/scripts/requirements.txt`
   (its OCR package installs on Python 3.10–3.12 only; without it the hints step is skipped — note that in the run log).
3. Smoke test: run its own `pytest` in that venv. Do not edit its files.

Done when: its tests pass locally; nothing of theirs is committed to pid_graph.

### Phase 3 — Extract the synthetic U-100 P&IDs
1. Follow `third_party/pid-to-kg/skills/pid-to-kg/SKILL.md` on `U100-PIDS-TX-0057.pdf` (pages 2–4), work directory `work/U-100`:
   probe → render → orientation check → hints → one `extract/page_NN.json` per sheet → build → QA loop until no errors.
2. Copy `work/U-100/kg/graph.json` and `qa_report.md` to `tests/fixtures/pidkg_U-100/` (synthetic, so safe to commit).
3. Record model, date and run time in `tests/fixtures/pidkg_U-100/RUN.md`. Extraction is not deterministic: the fixture is the frozen input for every later test.

Done when: fixture committed; QA report has zero errors.

### Phase 4 — `load_pidkg.py` (the adapter)
A pure `reconcile(pidkg_graph, index, existing_graph) -> {nodes, rels, exceptions, skipped}` plus a thin CLI. Mapping table in the docstring:

| pid-to-kg (`graph.json`) | pid_graph v1.3 |
|---|---|
| `Sheet` | match to existing `Document` by drawing number + revision; no match → exception |
| `Equipment` (tagged) | existing `Equipment` by tag; not in index/equipment list → exception (T1) |
| `Boundary` | existing `Equipment` (battery limit / header) by name; else exception |
| `Instrument` (tagged) | existing `Instrument`; not in index → exception (T1) |
| `Component` with a tag | existing `Instrument` (valve); not in index → exception (T1) |
| `Component` without a tag | new `InlineItem` |
| `PipeSegment` | new `Segment` + `SEGMENT_OF` its `Line` (`line_number` → `line_no`; unknown line → exception) |
| `OffPageConnector` | no node; paired → `FLOWS_TO off_page=true`; unpaired → exception |
| `ControlLoop` | new `ControlLoop` |
| `Plant` | skipped |
| `FLOWS_TO` | `FLOWS_TO` (carry `flow_direction`, `off_page`, `confidence`) |
| `MEASURES` → PipeSegment | `MEASURES` Instrument → Segment |
| `MEASURES` → Equipment | compare with existing index `MEASURES`; same → skip; different → conflict |
| `SIGNAL_TO` | `SIGNAL_TO` |
| `MEMBER_OF` | `MEMBER_OF` |
| `FEEDS` (derived) | not loaded; pid_graph derives its own in Phase 6 |
| `ACTUATES`, `TRIPS`, `CASCADES_TO`, `PART_OF` | skipped by design; counted. `TRIPS` is kept in memory for the Phase 6 cross-check |
| `issues`, per-sheet `unreadable` | exception rows (T6) |

Also: normalise tags with pid_graph's own normaliser, not theirs; idempotent `--apply`; every written fact gets
`extracted_by=pidkg_vision`, `review=pending` (or the decision already in the review register), full provenance.

Tests: on the Phase 3 fixture — every row of the table above has a case; counts are computed from the fixture, not hard-coded;
running `--apply` twice changes nothing; with the loader off the v1.2 dump is byte-identical.

### Phase 5 — Review register, gate and markup
1. Write/read `registers/topology_review_<unit>.csv` (section 3). Priority flags per T5.
2. PDF markup of pending facts (re-use pid_audit's markup code): green accepted, amber pending, red rejected / exception.
3. Add the T7 filter to every safety-relevant template. Test: a `pending` segment is invisible to a safety template and visible to an exploratory one.

### Phase 6 — Reconciliation checks (the part neither tool has alone)
Each check writes rows to the exception register or `conflicts`, with both sources named:
1. Three-way tag check (T3).
2. Derived `FEEDS` (walk `FLOWS_TO`) vs v1.2 `FEEDS` from `pid_audit_*_topology.csv`.
3. Instrument's Line per the index vs the Line of the Segment vision placed it on.
4. Drawn trip signals vs C&E `INITIATES` / `ACTUATES` (CQ13).
5. Valve fail position / actuator as drawn vs the index remarks (e.g. "Fail open").
6. Loop membership from drawn signals vs the index `loop` column.

Test fixture: a hand-edited copy of the Phase 3 `graph.json` with exactly one of each discrepancy, in the style of kg_suppression's `ce_chart_K101_rev_B.csv`.

### Phase 7 — Cypher templates for CQ9–CQ13
Fixed, parameterised templates plus the memory-backend equivalents, each with a test asserting both backends agree on U-100.
CQ10 output is headed "candidates for curation — not compensating measures" and never writes `COMPENSATES_FOR`.

### Phase 8 — Eval
1. Extend the U-100 gold set: every Segment-level instrument placement, every equipment-level flow pair, every loop and its members.
2. `eval/topology_eval.py`: precision / recall for tags, flow edges and loops; instrument-placement accuracy; share of facts flagged by T5;
   review workload (pending count per sheet).
3. Also run pid-to-kg's own `scripts/eval_kg.py` against a gold file in its format, so the two scores can be compared.
4. Record the baseline numbers in `CLAUDE.md`. No pass threshold is set in this plan: Alan sets it after seeing the first run.

### Phase 9 — Real-drawing stress test (extraction only)
1. Download by hand into `data/external/` (gitignored): the Pahala WWTP set (digital) and the Virden WWTF set (scanned), from the links in
   https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets.
2. Run Phase 3 on each. There is no index for these plants, so run `load_pidkg.py --no-master --report-only`: counts, QA issues, T5 flag rate. Nothing is applied.
3. Hand-check one sheet of each into a gold file and score it.
4. **Never commit the drawings, the renders, the marked-up PDFs or the extracted graphs.** The repo's own notes say the drawings remain under their
   original owners' terms. Commit only the scores and a short `docs/STRESS_TEST.md`.

### Phase 10 — DEXPI class and plant summary
1. Carry `dexpi_class` into `dexpiClass` (section 2.4). Extend the anchoring check to list nodes with a CFIHOS class and no DEXPI class, and the reverse.
2. `reports/summary_<unit>.md`: equipment-level flow, instruments with locations, loops, SIFs with initiators and final elements, alarms.
   Generated from the governed graph under the T7 filter, with a header stating the unit, document revisions and the count of pending facts left out.

### Phase 11 — Close out
1. Update `CLAUDE.md` (lists, files, known-good answers), the ontology doc and the README cheat sheet.
2. `git tag v1.3.0`.
3. Regenerate `reports/graph_U-100.json` and confirm kg_suppression still passes against it:
   `cd ..\..\kg_suppression ; python load_pid.py ..\ai-engineering-tools\pid_graph\reports\graph_U-100.json ; python -m pytest -q`
   Its `load_pid.py` skips unknown labels and relationship types by design (they are counted under "skipped by design"), so the new
   `Segment`, `InlineItem`, `ControlLoop`, `FLOWS_TO`, `SIGNAL_TO`, `MEMBER_OF`, `SEGMENT_OF` and Segment-level `MEASURES` should arrive as skips. Confirm that, do not assume it.

### Later (separate plan, not this build)
- kg_suppression: use accepted Segment topology to *propose* the `MEASURES` Instrument→Equipment rows that today come back as
  "measures a Line only" exceptions. Proposals to a review CSV, never straight to `nodes.csv` / `edges.csv`.
- soe_recon: `FLOWS_TO` order as a plausibility check on causal chains.
- Compensating-measure candidate ranking from CQ10 plus alarm priority and setpoint margin.

---

## 5. First prompt to paste into Claude Code

```
Read CLAUDE.md and PIDKG_UPGRADE.md in full. Do Phase 0 only: inventory the repo against the
"Assumed v1.2 baseline", run the tests, tag v1.2-baseline, write docs/V1_3_INVENTORY.md, commit.
List every place the repo differs from the plan and stop. Do not start Phase 1 until I say so.
```

Then one phase per prompt: `Do Phase N of PIDKG_UPGRADE.md. Tests first. One commit. Stop and report.`

## 6. Cheat sheet (Windows, PowerShell)

```
cd C:\Users\alanm\ai-engineering-tools\pid_graph
copy $HOME\Downloads\PIDKG_UPGRADE.md .
.\.venv\Scripts\Activate.ps1
python -m pytest -q
git status
claude
```

If something goes wrong mid-phase: `git stash` (or `git reset --hard` to the last commit), then re-run the phase prompt.
To abandon the whole upgrade: `git reset --hard v1.2-baseline`.
