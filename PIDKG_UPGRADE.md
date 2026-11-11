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

**Phase 0 was run on 10 Nov 2026** and this file was corrected against the repo the same day: baseline, competency-question
numbers, vocabulary, the anchoring and pid_audit assumptions, and the review register location. The findings and the
remaining differences are in `docs/V1_3_INVENTORY.md`.

### v1.2 baseline (verified in Phase 0)
The baseline is the **v1.2 schema** as stated in `README.md`, `PID_GRAPH_ONTOLOGY_V1_2.md` and `pid_graph/ontology.py` —
not the set of labels that happen to appear in the U-100 dump.
- Labels (8): `Instrument, Equipment, Line, SIF, Alarm, State, Document, Scenario`
- Relationships (15): `MEASURES, INSTALLED_ON, FEEDS, INITIATES, ACTUATES, PROTECTS, RAISES, CASCADES_TO, GENERATES,
  VALID_IN, HAS_STATE, COMPENSATES_FOR, CREDITS, THREATENS, SHOWN_ON`
- The U-100 dump shows only 7 labels and 12 relationships, because nothing in the dummy documents produces `State`,
  `CASCADES_TO`, `VALID_IN` or `HAS_STATE`. All four are in the closed schema and keep their v1.2 meaning.
- Dump shape: `{"nodes": [{label, key, props}], "rels": [{type, start_label, start_key, end_label, end_key, props}], "conflicts": []}`
- Provenance on every node and relationship: `source_doc, source_rev, source_sheet, extracted_by, load_run, source_ref`
  (`extracted_by` is one of `pid_audit`, `llm`, `manual`, `table`; U-100 uses `table`, `manual` and `pid_audit`); nodes also carry `stub`
- Topology today is line-level: `FEEDS` Equipment→Line→Equipment from `data/pid_audit_U100_topology.csv`, with a `confidence`
- Valves are `Instrument` with a `role` (`final_element`, `manual_valve`, …)
- Ontology document: `PID_GRAPH_ONTOLOGY_V1_2.md`
- Competency questions CQ1–CQ13 already exist (CQ9–CQ10 from v1.1, CQ11–CQ13 from v1.2)
- **Not in the repo** (Phase 0 finding): CFIHOS / QUDT reference-data anchoring, and pid_audit itself. Only pid_audit's
  topology export format is known, from the dummy CSV. There is no text-layer tag extraction and no PDF markup code.

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
| Title-block reader: drawing number + revision per sheet | Off-page connector pairing across sheets |
| Fixed Cypher templates for safety-relevant queries | Drawn signal lines and ISA-loop grouping |
| Gold-set eval, tagged baselines | Page classification, tiling, scan enhancement, OCR hints |
| pid_audit topology export (CSV) as the v1.2 `FEEDS` source | Confidence scale (0.95 / 0.85 / 0.7 / 0.5), DEXPI class, LLM plant summary |

Deliberately **not** adopted:
- Their derived `TRIPS` and `ACTUATES` relationships. In pid_graph, SIF logic comes from the C&E and SRS only. A drawn trip signal is
  used as a *cross-check* against the C&E (Phase 6), never as a source of `INITIATES` / `ACTUATES`.
- Tag-as-id merging without a master list. The index still decides which tagged nodes exist.
- Their `CASCADES_TO` and their state-like items (anything resembling `HAS_STATE` / `State`). pid_graph v1.2 already owns
  those names with a different meaning: `CASCADES_TO` is SIF → SIF ESD hierarchy from the C&E, and `HAS_STATE` / `VALID_IN`
  are reserved for the suppression design. pid-to-kg's are **not mapped** onto ours. Skipped and counted.
- DuckDB as the store. pid_graph keeps its own backends; pid-to-kg's `graph.json` is read as an input file only.

---

## 2. Ontology v1.3 (additive)

Write `PID_GRAPH_ONTOLOGY_V1_3.md` as v1.2 plus the items below. Nothing in v1.2 is removed or renamed.
Labels 8 → 11; relationships 15 → 19. Checked in Phase 0: none of the 3 new labels or 4 new relationships clashes with a
v1.2 name.

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

### 2.2 New relationships (4)

| Relationship | From → To | Props |
|---|---|---|
| `SEGMENT_OF` | Segment → Line | — |
| `FLOWS_TO` | Segment / Equipment / Instrument (in-line or valve) / InlineItem → same set | `flow_direction` (`shown`/`inferred`), `off_page`, `confidence`, `review` |
| `SIGNAL_TO` | Instrument → Instrument / Equipment | `signal_type`, `purpose` (`control`, `measurement`, `trip`, `alarm`, `status`, `unknown`), `confidence`, `review` |
| `MEMBER_OF` | Instrument → ControlLoop | `role` (`sensor`, `controller`, `relay`, `final_element`) |

### 2.3 Existing relationships with a wider range
- `MEASURES`: Instrument → **Segment** now allowed, alongside the v1.2 Instrument → Line / Equipment. The index-sourced Line relationship stays;
  the Segment relationship is added beside it with its own provenance.
- `INSTALLED_ON`: Instrument (valve) → **Segment** allowed, same rule.
- `FEEDS`: unchanged. A second, **derived** `FEEDS` set is computed by walking `FLOWS_TO` (props `derived=true`, `via_lines`), and is
  compared against the v1.2 `FEEDS` from `data/pid_audit_*_topology.csv` in Phase 6. Disagreement is a `conflict`, never a silent overwrite.

### 2.4 New provenance values and the review property
- `extracted_by="pidkg_vision"` on everything this loader writes. `source_ref` = `<pdf>:p<page>:bbox=<x0,y0,x1,y1>`.
- `confidence` carried through unchanged from pid-to-kg.
- `review` ∈ `pending | accepted | rejected`. Default `pending` for every `pidkg_vision` fact.
- `dexpiClass` on Equipment / Instrument / InlineItem, as a standalone property. Informative only. (There is no CFIHOS
  `refClass` or any other reference-data anchoring in the repo to sit beside; none is built by this plan.)

### 2.5 New competency questions (add to the existing thirteen, CQ1–CQ13)
- CQ14 **Isolation**: which valves (tagged or not) sit between instrument X's tap and the next equipment, each way?
- CQ15 **Same-pressure-system candidates**: which other instruments sense a segment reachable from sensor X without crossing a
  closed-in-normal-operation or actuated valve? (Feeds the compensating-measure *candidate* list. Curation stays manual.)
- CQ16 **MOC blast radius**: everything downstream of valve or segment X up to the next equipment, and every loop and SIF that touches it.
- CQ17 **Loop membership**: for final element X — its loop, its sensor, and the segment the sensor measures.
- CQ18 **Drawing vs C&E**: every drawn `purpose=trip` signal with no matching `INITIATES`/`ACTUATES`, and every C&E cause/effect
  with no drawn trip signal.

---

## 3. Trust rules (the gate)

| # | Rule |
|---|---|
| T1 | Index is master. A tagged pid-to-kg node whose normalised tag is not in the index → exception `on P&ID (vision), not in index`. No node. |
| T2 | Index tag never seen by vision on any sheet it is `SHOWN_ON` → exception `in index, not found on P&ID (vision)`. |
| T3 | Tag check per sheet: index vs vision only (pid_audit's text-layer tags are not available in this repo). Report the three regions — both, index only, vision only; only "both" is clean. |
| T4 | Every `pidkg_vision` fact is written with `review=pending`. |
| T5 | Auto-flag for priority review: `confidence < 0.85`, `flow_direction=inferred`, `off_page=true`, any relationship touching an `InlineItem`. |
| T6 | Items in pid-to-kg's `unreadable` list and every pid-to-kg QA `error` / `warning` → one exception row each. Never a node. |
| T7 | **Safety-relevant Cypher templates traverse only facts where `extracted_by IN ['table','manual','pid_audit'] OR review='accepted'`.** Exploratory templates may use `pending` facts, and must say so in their output header. |
| T8 | A `rejected` fact stays in the review register (with reviewer and reason) and is removed from the graph on the next load. |

Review register: `reports/review_register_<unit>.xlsx`, beside `reports/exception_register_<unit>.xlsx` and in the same
format (openpyxl workbook; a `Summary` sheet of metric / value, then a `Review` sheet with a bold header row). One row per
`pidkg_vision` relationship and node —
`fact_id, type, from, to, sheet, bbox, confidence, flags, review, reviewer, reviewed_on, comment`.
The loader reads it back on every run, so a decision survives a re-extraction (match on `fact_id` = stable hash of type + endpoints + sheet).
Unlike the exception register it is an input as well as an output: it is never overwritten blind, and it is the one file in
`reports/` that is committed (`.gitignore` makes the exception for `reports/review_register_*.xlsx`).
Also emit a colour-coded PDF markup of pending facts, so review is done on the drawing, not in a spreadsheet alone.
The markup is written fresh with PyMuPDF in Phase 5; there is no pid_audit markup code to re-use.

---

## 4. Phases

### Phase 0 — Inventory and baseline (no code changes)
1. Read `CLAUDE.md`, `PID_GRAPH_ONTOLOGY_V1_2.md`, the decisions doc and the loaders.
2. Run the tests and the U-100 build. Confirm the dump matches the baseline above (labels, relationships, provenance keys).
3. `git tag v1.2-baseline`.
4. Write `docs/V1_3_INVENTORY.md`: actual file names for the loaders, the exception register, the Cypher templates, the eval and the gold set; any difference from this plan's assumptions.
5. **Stop and report if a label or relationship in section 2 already exists with a different meaning.**

Done when: tag exists, inventory committed, tests green.

### Phase 1 — Ontology v1.3 on paper and in the validators
1. `PID_GRAPH_ONTOLOGY_V1_3.md` (section 2). Update the closed lists in `CLAUDE.md`.
2. Extend the schema/validators: 3 labels, 4 relationships, widened ranges, `review`, the `InlineItem` safety-relationship ban.
3. Tests: a made-up five-node graph per new label/relationship; a test that an `InlineItem` on an `INITIATES` relationship is refused.

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
| `Boundary` | existing `Equipment` (battery limit / header) whose tag appears in the flag text (`FEED GAS FROM BL-100` → `BL-100`); none or several → exception |
| `Instrument` (tagged) | existing `Instrument`; not in index → exception (T1) |
| `Instrument` that is an interlock symbol (not in the index; every signal in and out is a trip — the `I-1` diamond) | no node; collapsed into direct trip signals (see `SIGNAL_TO`); one exception row per symbol. Decided by Alan, 10 Nov 2026 |
| `Component` with a tag | existing `Instrument` (valve); not in index → exception (T1) |
| `Component` without a tag | new `InlineItem` |
| `PipeSegment` | new `Segment` + `SEGMENT_OF` its `Line` (`line_number` → `line_no`; unknown line → exception) |
| `OffPageConnector` | no node; paired → `FLOWS_TO off_page=true`; unpaired → exception |
| `ControlLoop` | new `ControlLoop` |
| `Plant` | skipped |
| `FLOWS_TO` | `FLOWS_TO` (carry `flow_direction`, `off_page`, `confidence`) |
| `MEASURES` → PipeSegment | `MEASURES` Instrument → Segment |
| `MEASURES` → Equipment | compare with existing index `MEASURES`; same → skip; different → conflict |
| `SIGNAL_TO` | `SIGNAL_TO`. Through an interlock symbol: one `SIGNAL_TO` initiator → final element, `purpose=trip`, `via` = the symbol, `via_name` = what the drawing notes call it |
| `MEMBER_OF` | `MEMBER_OF` |
| `FEEDS` (derived) | not loaded; pid_graph derives its own in Phase 6 |
| `ACTUATES`, `TRIPS`, `CASCADES_TO`, `PART_OF`, any state-like node or relationship | skipped by design; counted. Never mapped onto pid_graph's own `ACTUATES`, `CASCADES_TO`, `HAS_STATE` or `State`. `TRIPS` is **not** used for the Phase 6 cross-check: pid-to-kg derives it by tag number and it over-reaches (on U-100 it has PI-1001 and LG-1002 tripping valves). The loader returns the drawn trip signals as `drawn_trips` instead |
| `issues`, per-sheet `unreadable` | exception rows (T6) |

Also: normalise tags with pid_graph's own normaliser, not theirs; idempotent `--apply`; every written fact gets
`extracted_by=pidkg_vision`, `review=pending` (or the decision already in the review register), full provenance.

As built (10 Nov 2026), `pid_graph/load_pidkg.py`:
- Signature is `reconcile(pidkg_graph, index, existing_graph, *, unit, load_run, review=None)`; it also returns `conflicts`,
  `seen` (tag → drawings vision found it on), `drawn_trips` and `summary`. `apply(store, result)` does the merge.
- `--apply` is new with this loader (no v1.2 loader has it). The standalone CLI is a dry run unless `--apply` is given.
  In the full pipeline the loader is switched on with `python -m pid_graph --pidkg <graph.json>`; off is the default and gives the v1.2 graph.
- The master for `Equipment` is the existing graph: a non-stub `Equipment` node. There is no equipment list.
- Exception codes X21–X29 (titles in `reconcile.TITLES`): X21 on P&ID not in index (T1), X22 in index not on P&ID (T2), X23 sheet matches
  no drawing revision, X24 boundary unmatched, X25 line not in the graph, X26 off-page connector unpaired, X27 pid-to-kg QA issue /
  unreadable (T6), X28 not representable, X29 interlock symbol collapsed.
- A line drawn on two sheets gets segment numbers `1..n` running across the sheets, so `<line_no>.<k>` cannot collide.
- A line with no number gets no `Segment` (X25), because `line_no` is a required property; section 2.1's `<doc_no>.<local>.<k>` key is not used.
- An `InlineItem` or `ControlLoop` that no loaded relationship touches is not written. New nodes are `SHOWN_ON` their drawing.
  Existing nodes are not given a vision `SHOWN_ON`: relationship identity is (type, start, end, `source_doc`), so it would merge
  into pid_audit's and be lost. What vision saw is in `seen`.
- `MEMBER_OF` roles map `transmitter`/`element`/`switch` → `sensor`; `gauge`, `indicator` and `other` are not in the closed list and are skipped.
- `--no-master --report-only` (Phase 9) is not built yet.

Tests: on the Phase 3 fixture — every row of the table above has a case; counts are computed from the fixture, not hard-coded;
running `--apply` twice changes nothing; with the loader off the v1.2 dump is byte-identical.

### Phase 5 — Review register, gate and markup
1. Write/read `reports/review_register_<unit>.xlsx` (section 3). Priority flags per T5.
2. PDF markup of pending facts, written fresh with PyMuPDF (already a dependency; nothing to re-use): green accepted, amber pending, red rejected / exception.
3. Add the T7 filter to every safety-relevant template. Test: a `pending` segment is invisible to a safety template and visible to an exploratory one.

As built (10 Nov 2026), `pid_graph/review.py`:
- Register columns are the twelve of section 3 plus `detail` (what the fact says). The `SHOWN_ON` of a new node is not a row; it follows
  the node's decision. A decision counts only with a closed value **and a named reviewer**; otherwise it is reported and the fact stays pending.
- The pipeline (`python -m pid_graph --pidkg ...`) reads the register in `--out`, passes the decisions to the loader, writes the register back
  (unchanged content is not rewritten) and, when `--pdf` is given, writes `review_markup_<unit>.pdf` beside it. `reports/review_register_U-100.xlsx` is committed.
- Markup: boxes for InlineItems, for instruments with a segment-level `MEASURES` and for exceptions; a line per Segment between the two located
  things it joins, coloured by the worst of the segment and its two `FLOWS_TO`; a thin dashed line per `SIGNAL_TO`. `MEMBER_OF` and `SEGMENT_OF` have
  no place on the sheet and are reviewed in the register only. Positions come from pid-to-kg's bounding boxes and are approximate. The source PDF is never modified.
- T7 has one definition in two forms: `ontology.trusted()` and `queries.trusted_rel()`. It is applied to every relationship type the vision loader can
  write that a template names (`MEASURES`, `INSTALLED_ON`, `SHOWN_ON`), to every variable-length path, and to the nodes reached, in `queries.py` and
  in the report queries. Types vision can never write (`INITIATES`, `ACTUATES`, `PROTECTS`, `GENERATES`, `COMPENSATES_FOR`, `CREDITS`, `RAISES`,
  `CASCADES_TO`) are not filtered. `records.TrustedView` is the same gate over either store; the explorer is built from it unless `--include-pending`.
- Verified against a live Neo4j on 10 Nov 2026 (pid_graph's own container, `neo4j-pidgraph`, bolt 7688): with every vision fact pending, all four templates return exactly the v1.2 answers; with one Segment and one `MEASURES` accepted, only those two facts appear. That run found one defect, now fixed and tested: a `Segment` carries `line_no`, so a query that looked a node up by `line_no` matched an accepted Segment as if it were the Line. Queries now say `:Line`, and name a Segment by its `segment_id`.

### Phase 6 — Reconciliation checks (the part neither tool has alone)
Each check writes rows to the exception register or `conflicts`, with both sources named:
1. Tag check, index vs vision (T3).
2. Derived `FEEDS` (walk `FLOWS_TO`) vs v1.2 `FEEDS` from `data/pid_audit_*_topology.csv`.
3. Instrument's Line per the index vs the Line of the Segment vision placed it on.
4. Drawn trip signals (`SIGNAL_TO` with `purpose=trip`, i.e. the loader's `drawn_trips`; not pid-to-kg's `TRIPS`) vs C&E `INITIATES` / `ACTUATES` (CQ18).
5. Valve fail position / actuator as drawn vs the index remarks (e.g. "Fail open").
6. Loop membership from drawn signals vs the index `loop` column.

Test fixture: a hand-edited copy of the Phase 3 `graph.json` with exactly one of each discrepancy, in the style of kg_suppression's `ce_chart_K101_rev_B.csv`.

As built (10 Nov 2026), `pid_graph/vision_checks.py`:
- Findings are exception rows X30–X36, each naming both sources: X30 index drawing reference vs vision, X31 flow vs pid_audit, X32 instrument's line,
  X33 drawn trip not in the C&E, X34 C&E cause and effect not drawn, X35 fail position or actuator, X36 loop membership. Check 1's other two regions are
  the loader's X21 and X22; the per-sheet table of all three regions is in the load report (`vision_checks.tag_check`) and printed.
- **Derived `FEEDS` are computed and reported, not written to the graph.** An equipment-to-equipment `FEEDS` would shorten the "within two `FEEDS` hops"
  of the v1.2 templates, and rule 2 says no v1.2 relationship changes meaning. Section 2.3 is read accordingly: the derived set is in the load report
  (`vision_checks.derived_feeds`, with `derived`, `via_lines`, `via_items`, `off_page` and the worst `review` on the path).
- The comparison with pid_audit is per line, on equipment pairs. A pid_audit `FEEDS` that reaches a line and no equipment beyond it (L-105) is not a pair and is not compared.
- X36 is raised only where vision puts the instrument in a loop other than the index's; an instrument vision puts in no loop is not flagged.
- The checks read vision facts whatever their review state. They are how a reviewer finds what to accept or reject, not a safety-relevant answer.
- The fixture is `tests/fixtures/pidkg_U-100/graph_discrepancies.json`, made by `scripts/make_pidkg_discrepancies.py` (six edits, listed in `DISCREPANCIES.md`).
- On the real U-100 extraction the checks give two findings: X30 XV-1002 and X34 SIF-100-03 (PT-1001D → XV-1001 is in the C&E and not drawn).

### Phase 7 — Cypher templates for CQ14–CQ18
Fixed, parameterised templates plus the memory-backend equivalents, each with a test asserting both backends agree on U-100.
CQ15 output is headed "candidates for curation — not compensating measures" and never writes `COMPENSATES_FOR`.

As built (10 Nov 2026), `pid_graph/topology_queries.py`:
- `isolation(tag)` CQ14, `same_pressure(tag)` CQ15, `blast_radius(id)` CQ16, `loop_membership(tag)` CQ17, `drawing_vs_ce()` CQ18. The first argument is a
  Neo4j driver or a store; the answer has the same shape. Each template is written once over a dozen backend primitives, and each primitive has a Cypher
  form and an in-memory form. The agreement test runs every template in both modes on both backends and requires identical answers.
- T7: CQ14–CQ17 use trusted facts only by default, on every relationship and node, and report `vision_facts_left_out`. `include_pending=True` (CLI
  `--include-pending`) uses everything and the header begins `EXPLORATION ONLY`. CQ18 is a consistency check on what is drawn, so it reads pending facts by
  default and says so. With nothing accepted, CQ14–CQ17 return empty answers for U-100, with a note that the facts may be awaiting review.
- A walk that stops before reaching equipment reports `open_ends`, so a gap left by a pending or rejected fact is visible in the answer.
- CQ15 walks both ways and through equipment (a vessel is one pressure system); it stops at an actuated valve (`role = final_element`) or an untagged valve
  with `normal_position = closed`. A manual valve with no stated position is taken as open. It knows nothing of pumps, compressors or check valves.
- Paths are followed for at most 40 relationships. The templates are not exposed as MCP tools yet.
- Verified on `neo4j-pidgraph` in two states: everything pending, and 72 facts accepted with 1 rejected. Both backends agreed in both.

### Phase 8 — Eval
1. Extend the U-100 gold set: every Segment-level instrument placement, every equipment-level flow pair, every loop and its members.
2. `eval/topology_eval.py`: precision / recall for tags, flow relationships and loops; instrument-placement accuracy; share of facts flagged by T5;
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
1. Carry `dexpi_class` into `dexpiClass` (section 2.4) as a standalone property. There is no anchoring check to extend: add one validator check listing Equipment / Instrument / InlineItem nodes seen by vision with no `dexpiClass`.
2. `reports/summary_<unit>.md`: equipment-level flow, instruments with locations, loops, SIFs with initiators and final elements, alarms.
   Generated from the governed graph under the T7 filter, with a header stating the unit, document revisions and the count of pending facts left out.

### Phase 11 — Close out
1. Update `CLAUDE.md` (lists, files, known-good answers), the ontology doc and the README cheat sheet.
2. `git tag v1.3.0`.
3. Regenerate `reports/graph_U-100.json` and confirm kg_suppression still passes against it:
   `cd ..\..\kg_suppression ; python load_pid.py ..\ai-engineering-tools\pid_graph\reports\graph_U-100.json ; python -m pytest -q`
   Its `load_pid.py` skips unknown labels and relationships by design (they are counted under "skipped by design"), so the new
   `Segment`, `InlineItem`, `ControlLoop`, `FLOWS_TO`, `SIGNAL_TO`, `MEMBER_OF`, `SEGMENT_OF` and Segment-level `MEASURES` should arrive as skips. Confirm that, do not assume it.

### Later (separate plan, not this build)
- kg_suppression: use accepted Segment topology to *propose* the `MEASURES` Instrument→Equipment rows that today come back as
  "measures a Line only" exceptions. Proposals to a review CSV, never straight to `nodes.csv` / `edges.csv`.
- soe_recon: `FLOWS_TO` order as a plausibility check on causal chains.
- Compensating-measure candidate ranking from CQ15 plus alarm priority and setpoint margin.

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
