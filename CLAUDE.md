# CLAUDE.md — pid_graph

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Read this file in full before touching anything. It is a summary of `README.md`,
`PID_GRAPH_DECISIONS.md` and `SESSION_LOG.md`; where it and those documents disagree, they win
and this file is corrected.

## 1. Purpose

pid_graph is a cross-document knowledge graph for the functional-safety layer of a process unit:
instrument index + P&IDs + cause & effect chart + SRS + LOPA, on Neo4j, with a closed schema
(ontology v1.3: the v1.2 register layer plus a vision layer of segment topology read from the P&IDs,
which an engineer accepts fact by fact). It answers one family of questions with full provenance: *this element is out of
service — what protection is lost, what remains, what compensates?* (bypass, MOS, alarm shelving,
interlock bypass), plus MOC impact, trip investigation and cross-document consistency.

All data in this repository is synthetic (dummy unit U-100). No real project drawings, tags or
documents are ever added.

## 2. Rules

1. **Closed schema.** Only the labels and relationships in section 3 exist. To change the schema,
   change the ontology document first, then `pid_graph/ontology.py`, then the loaders.
2. **The graph models the plant, not the documents.** One tag = one node, however many documents
   mention it. Documents are nodes only for provenance (`SHOWN_ON`).
3. **The instrument index is the master node list.** Everything else reconciles against it.
   Mismatches go to the exception register, never silently into the graph.
4. **Provenance on every node and relationship:** `source_doc`, `source_rev`, `source_sheet`,
   `extracted_by` (`pid_audit` / `llm` / `manual` / `table`), `load_run` (transmittal-prefixed),
   `source_ref`.
5. **Conflicts are stored, never resolved at load.** Property disagreement is a recorded conflict
   (X6); the same fact from two documents is two parallel relationships (identity includes
   `source_doc`, D-P1-06).
6. **Nothing safety-relevant is LLM-extracted.** `COMPENSATES_FOR` comes only from approved rows
   of the curated register (D-P2-10). SRS and LOPA are read from tabular registers (D-P4-04).
7. **Safety-relevant answers come from fixed, tested query templates only** (`queries.py`).
   Free-form Cypher (`read_cypher`) is exploration only. The MCP server is read-only by
   construction (D-P2-11).
8. **Unit is a loading boundary, never a graph boundary.** Full rebuild per unit (wipe, reload);
   referenced-but-unloaded things are stubs (`stub: true`, `stub_unit`).
9. **The page is not the document; the drawing is.** Provenance is drawing number + revision +
   sheet, never a PDF page number.
10. **Vocabulary (D-P4-06).** Engineering surfaces say *node* and *relationship* — never *edge*,
    *arrow* or *item*. The shift handover page alone says *element* for a thing out of service.
11. **British spelling.** Copyright header on every new file:
    `© 2026 Alan Bowden — Bowden Simulators. All rights reserved.`
12. **Tests green before every commit:** `.venv\Scripts\python -m pytest -q`. No existing test is
    edited to make it pass.
13. **Never commit** `.env`, credentials, `work/`, `third_party/`, `data/external/` or anything in
    `reports/` other than the review register.
14. **Trust rule T7.** A safety-relevant template, report or in-page assessment uses only trusted
    facts: `extracted_by` in `table, manual, pid_audit`, or `review = accepted`. One definition, two
    forms: `ontology.trusted()` and `queries.trusted_rel()`; `records.TrustedView` applies it to a
    store. Any new Cypher over `MEASURES`, `INSTALLED_ON`, `SHOWN_ON`, `SEGMENT_OF`, `FLOWS_TO`,
    `SIGNAL_TO`, `MEMBER_OF` or a variable-length path must carry it (a test checks `queries.py`
    and `report.py`). Exploratory output says that it may include pending facts.

## 3. Closed lists (ontology v1.3)

Source of truth: `PID_GRAPH_ONTOLOGY_V1_3.md`, transcribed in `pid_graph/ontology.py`. v1.3 is v1.2
plus the rows marked v1.3; nothing in v1.2 changed meaning. The v1.3 rows are written only by
`load_pidkg.py`, always with `extracted_by = pidkg_vision` and a `review` state.

### Labels (11)

| Label | Key |
|---|---|
| `Instrument` | `tag` |
| `Equipment` | `tag` |
| `Line` | `line_no` |
| `SIF` | `sif_id` |
| `Alarm` | `alarm_id` (`<source tag>.<alarm function>`, e.g. `PT-1001A.PAH`) |
| `State` | `state_id` |
| `Document` | `doc_no` + `rev` (`doc_key = doc_no|rev` carries the constraint) |
| `Scenario` | `scenario_id` |
| `Segment` (v1.3) | `segment_id` (`<line_no>.<k>`); requires `line_no`, `size`, `service`, `review` |
| `InlineItem` (v1.3) | `item_id` (`<doc_no>.<local>`); requires `kind`, `normal_position`, `indexed = false`, `review` |
| `ControlLoop` (v1.3) | `loop_key`; requires `loop_type`, `variable`, `review` |

`State` is in the schema but no loader writes it yet (waits for the suppression design).

### Relationships (19)

| Relationship | Direction |
|---|---|
| `MEASURES` | Instrument → Line / Equipment / Segment (Segment: v1.3) |
| `INSTALLED_ON` | Instrument → Line / Equipment / Segment (Segment: v1.3) |
| `FEEDS` | Line / Equipment → Line / Equipment |
| `INITIATES` | Instrument → SIF |
| `ACTUATES` | SIF → Instrument |
| `PROTECTS` | SIF → Equipment / Line |
| `RAISES` | SIF → Alarm |
| `CASCADES_TO` | SIF → SIF |
| `GENERATES` | Instrument → Alarm |
| `VALID_IN` | Alarm → State |
| `HAS_STATE` | Equipment → State |
| `COMPENSATES_FOR` | Alarm → SIF (curated only) |
| `CREDITS` | Scenario → SIF / Alarm / Instrument |
| `THREATENS` | Scenario → Equipment / Line |
| `SHOWN_ON` | any → Document |
| `SEGMENT_OF` (v1.3) | Segment → Line |
| `FLOWS_TO` (v1.3) | Segment / Equipment / Instrument / InlineItem → same set |
| `SIGNAL_TO` (v1.3) | Instrument → Instrument / Equipment |
| `MEMBER_OF` (v1.3) | Instrument → ControlLoop |

`CASCADES_TO`, `VALID_IN` and `HAS_STATE` are in the schema but have no instances in U-100.

An `InlineItem` can never start or end `INITIATES`, `ACTUATES`, `PROTECTS`, `CREDITS`,
`COMPENSATES_FOR` or `GENERATES`; the validator refuses it.

Other closed values: `extracted_by` ∈ `pid_audit, llm, manual, table, pidkg_vision`;
`review` ∈ `pending, accepted, rejected` (required on every `pidkg_vision` fact);
`FLOWS_TO.flow_direction` ∈ `shown, inferred`; `SIGNAL_TO.purpose` ∈ `control, measurement, trip,
alarm, status, unknown`; `MEMBER_OF.role` ∈ `sensor, controller, relay, final_element`;
`Document.doc_type` ∈ `PID`, `CE`, `IDX`, `CUR`, `SRS`, `LOPA`, `SILV`, `MADB`, `CFG`, `MOC`, `REG`, `PROC`, `PTP`, `LOOP`, `PHIL`, `SISIO` (the ten after `LOPA` are the operations documents, D-V13-12: values only, no new
label or relationship); unknown revision = `UNKNOWN`.

Competency questions CQ1–CQ18 are defined in the ontology document. CQ14–CQ18 are new in v1.3;
their templates are in `pid_graph/topology_queries.py`.

## 4. Files

| Path | What it is |
|---|---|
| `PID_GRAPH_ONTOLOGY_V1_3.md` | The closed schema and competency questions (v1, v1.1 and v1.2 kept for the record) |
| `PID_GRAPH_DECISIONS.md` | Reasoning and numbered decisions (D-P1-xx … D-P4-xx) |
| `SESSION_LOG.md` | Running log for cold pickup |
| `PIDKG_UPGRADE.md` | Plan for v1.2 → v1.3 (segment topology + vision extraction) |
| `docs/V1_3_INVENTORY.md` | Phase 0 inventory of the repo against that plan |
| `docs/STRESS_TEST.md`, `eval/stress_test_scores.json` | Phase 9 pilot: pid-to-kg on two sheets each of two public drawing sets. Numbers only; the drawings, gold files and graphs stay in git-ignored `data/external/` and `work/` and must never be committed. Gold not yet checked by an engineer |
| `pid_graph/ontology.py` | Closed schema + validators (`check_label`, `check_key`, `check_rel`, `check_provenance`) |
| `pid_graph/tags.py` | Canonical tag regex, prefix classification, `role()` |
| `pid_graph/records.py` | `MemoryStore` (MERGE semantics, conflicts, `to_dict()` dump) |
| `pid_graph/neo4j_store.py`, `db.py` | Constraints, wipe-per-unit, batched MERGE, read-back; driver from `.env` |
| `pid_graph/loaders/` | `tables.py` (header aliases), `titleblock.py`, `docs.py`, `index_loader.py`, `ce_table.py`, `ce_loader.py`, `srs_loader.py`, `lopa_loader.py`, `curated_loader.py`, `pid_loader.py` |
| `pid_graph/pipeline.py`, `run_all.py` | `build_store()`; `python -m pid_graph` end to end |
| `pid_graph/reconcile.py` | Coverage + exception register (codes X1–X20; titles for X21–X29) |
| `pid_graph/load_pidkg.py` | v1.3 vision layer: pid-to-kg `graph.json` → Segment, InlineItem, ControlLoop, FLOWS_TO, SIGNAL_TO, MEMBER_OF, with exceptions X21–X29. Dry run by default; `--apply` to write. In the pipeline: `python -m pid_graph --pidkg <graph.json>` (off by default) |
| `pid_graph/summary.py` | Plant summary `summary_<unit>.md` from the trusted view only (T7): documents and revisions, flow, instruments, loops, SIFs, alarms, exceptions; states how many vision facts it left out. Rule-based, not model-written. Written by the pipeline into `--out` |
| `pid_graph/topology_queries.py` | Fixed templates CQ14–CQ18 (`isolation`, `same_pressure`, `blast_radius`, `loop_membership`, `drawing_vs_ce`) over a Neo4j driver or a store; trusted facts only unless `--include-pending`, which is labelled EXPLORATION ONLY |
| `pid_graph/vision_checks.py` | Vision against the registers: tag regions per sheet, derived flow vs pid_audit, instrument's line, drawn trips vs C&E, fail position, loop membership (exceptions X30–X36). Derived `FEEDS` are reported, never written |
| `pid_graph/review.py` | Review register (`reports/review_register_<unit>.xlsx`: read back on every load, decisions need a named reviewer), T5 priority flags, and the PDF markup of vision facts (`review_markup_<unit>.pdf`) |
| `reports/review_register_U-100.xlsx` | The one committed file in `reports/`: the engineer's accept / reject decisions on vision facts |
| `tests/fixtures/pidkg_U-100/` | Frozen pid-to-kg extraction of the synthetic P&IDs (`graph.json`, `qa_report.md`, `extract/`, `RUN.md`) |
| `pid_graph/loaders/madb_loader.py`, `config_loader.py`, `silv_loader.py`, `moc_loader.py`, `docreg_loader.py`, `ops_common.py` | Operations documents (D-V13-12), off by default: `build_store(madb=, config=, silv=, moc=, docreg=)`. Claims land in source-named properties (`*_madb`, `*_cfg`, `*_silv`, `override_*`); a MOC is a Document; the document register links what each document covers |
| `pid_graph/ops_checks.py` | Cross-document checks C1–C16 over those documents (alarm settings, ranges, IPL flags, SIF architecture, SIL verification assumptions, bypass provision, active overrides, MOC close-out and MOC impact rules I1–I5) and the scorecard against the batch 1 answer key. X1–X36 are untouched |
| `pid_graph/demo.py`, `demo_page.py` | Scenario demonstrator: nine fixed templates (bypass, shelve, MOC impact, MOC close-out, SIF out of service, trip, where used, document revised, everything impaired now) run for every element they apply to, memory backend, trusted view. `python -m pid_graph.demo` writes `reports/demo_U-100.html`; `--artifact PATH` writes the form published privately at https://claude.ai/artifact/6q2YAhHoohUn2HyCCV3XFa ("U-100 Scenario Explorer"). After a change, rebuild and republish with the Artifact tool, passing that URL as `url` |
| `pid_graph/situation.py` | Build-your-own situation: `build_model()` reads the graph into a plain model, `evaluate(model, out)` is a pure function (rules S1–S8) for any set of elements out of service together; `SITUATION_JS` is the same function for the page. `tests/test_situation.py` tests each rule on made-up models and runs the JavaScript in node against Python on 900-odd combinations (skips without node). Change the two together or that test fails. CLI: `python -m pid_graph.situation [--unit U] [--as-found] TAG ...` |
| `docs/DEMO_GUIDE.md` | Presenter's guide: the order to show the scenarios in, what each proves, the check codes, what not to claim |
| `.claude/skills/kg-demo/SKILL.md` | How to rebuild, republish and extend the demonstrator (new scenario, new check, new test documents) |
| `pid_graph/queries.py` | Fixed Cypher templates: `out_of_service`, `shelve_impact`, `moc_impact`, `trip` (Neo4j only) |
| `pid_graph/validate.py` | Structural checks + CQ sketches on the live graph |
| `pid_graph/mcp_server.py`, `.mcp.json` | Read-only MCP server (12 tools, stdio) |
| `pid_graph/intake.py` | Readiness check for a new document |
| `pid_graph/explorer.py` | Self-contained HTML explorer with in-page assessments |
| `pid_graph/report.py`, `oos.py` | Engineer reports (md + docx); out-of-service register |
| `eval/score.py`, `eval/gold_PID-100-001.json` | Gold-set scorer and gold set (v1.2, one sheet, pid_audit) |
| `eval/topology_eval.py`, `eval/gold_topology_U-100.json` | v1.3 topology eval of a pid-to-kg extraction: tags, flow pairs, loops, instrument placement, review workload. `eval/make_topology_gold.py` builds the gold (and `gold_pidkg_U-100.json` for pid-to-kg's own `eval_kg.py`); first numbers in `eval/TOPOLOGY_BASELINE.md` |
| `tests/` | `test_phase1.py` … `test_phase4.py`, `test_mcp_smoke.py`, `test_v13_phase1.py`; `tests/fixtures/graph_U-100_v1_2.json` is the frozen v1.2 dump |
| `scripts/` | `setup_neo4j.ps1`, `make_dummy_pdf.py`, `make_dummy_srs_lopa.py`, `make_dummy_batch1.py` (SIL verification, MADB, DCS/SIS configuration export, MOC register, with planted discrepancies and their answer key) |
| `data/` | Synthetic U-100 documents; `data/curated/`, `data/oos/`, `data/moc/`. The P&ID PDFs carry drawn sheets made by `scripts/make_dummy_pdf.py --all`; `data/U100-PIDS-DRAWN-CONTENT.json` is the answer key for what each sheet shows (not read by any loader). Batch 1 (`U100-SILV-001`, `U100-MADB-001`, `U100-CFG-EXPORT`, `U100-MOC-REG`, all Rev A) is not loaded by any loader yet; `data/U100-BATCH1-ANSWER-KEY.json` lists the 23 planted discrepancies with the cells that prove them, tested by `tests/test_batch1_documents.py` |
| `reports/` | Generated outputs (git-ignored): `exception_register_<unit>.xlsx`, `graph_<unit>.json`, `load_report_<unit>.json`, explorer, reports |
| `src/` | Two early stray copies of `db.py` / `check_env.py`; not imported by anything |

Commands are in `README.md`. Add `--pidkg tests\fixtures\pidkg_U-100\graph.json` for the vision layer. The usual build:

```
.venv\Scripts\python -m pid_graph --unit U-100 --backend memory --pdf data\U100-PIDS-TX-0057.pdf --transmittal TX-0057
```

## 5. Known-good answers (U-100)

**Demonstrator** (`python -m pid_graph.demo`, 12 Nov 2026, memory backend, vision layer off): 82 nodes / 308
relationships / 27 documents; 93 scenarios; 63 findings (43 C, 20 X); every one of the 23 planted batch 1 items found.
Showcase verdicts: bypass PT-1001B stop (MOS-1001B active 39.7 h against 8 h, no out-of-service entry, both compensating
alarms impaired); shelve LAH-1006 stop (LOPA IPL, compensating measure and SRS bypass condition for SIF-100-02);
MOC-2026-016 stop (misses the SRS, the MADB and the compensating-measures register); MOC-2026-014 close-out stop (7 of 8
documents not revised); SIF-100-03 out of service stop; SIF-100-02 trip caution (2oo2 configured, 2oo3 in the C&E and SRS).
Tests pin these in one place (`tests/test_ops_demo.py`); everything else there is relative to `data/` and the answer key.

Re-verified on 10 Nov 2026 with the memory backend unless marked *(log)*, which means taken
from `SESSION_LOG.md` (Neo4j, 9 Sep 2026) and not re-run.

**Drawings:** the synthetic P&IDs agree with `data/pid_audit_U100_topology.csv` row for row.
TT-1003 and PT-1001D are not drawn; FT-1006 is drawn on PID-100-002; XV-1002 is drawn on
PID-100-001; PID-100-003 shows two unnumbered utility lines and nothing tagged. Drawn but in no
register: the DCS controllers LIC-1006, FIC-1004 and PIC-1005, ten untagged fittings, the
signal lines, and line sizes and services.

**Vision layer** (memory backend, `--pidkg tests\fixtures\pidkg_U-100\graph.json` added to the
usual build): 32 new nodes (Segment 21, InlineItem 6, ControlLoop 5) and 120 new relationships
(FLOWS_TO 37, SHOWN_ON 32, SEGMENT_OF 21, MEMBER_OF 14, SIGNAL_TO 10, MEASURES 6), all
`review = pending`; graph total 81 nodes / 284 relationships; 0 conflicts. Fifteen more
exceptions: X21 ×4 (FT-1006, LIC-1006, FIC-1004, PIC-1005), X22 TT-1003, X24 ×5 (FUTURE FUEL GAS
and the four utility boundaries), X25 ×2 (the unnumbered utility lines), X27 (pid-to-kg warning
on loop F-1004), X29 ×2 (I-1, I-2). Ten drawn trip signals: PT-1001A/B/C → XV-1001 and BDV-1001
via I-1; LT-1002A/B → XV-1001 and XV-1002 via I-2. With `--pidkg` off the graph is v1.2,
byte for byte.

**Vision checks** (same build): two findings - X30 XV-1002 (index says PID-100-002, vision found it on PID-100-001) and X34
SIF-100-03 (the C&E has PT-1001D closing XV-1001; no such trip is drawn). 37 exceptions in all with the vision layer on.
Tag check: PID-100-001 both 13, index only TT-1003, vision only FIC-1004, LIC-1006, XV-1002; PID-100-002 both 2, index only
XV-1002, vision only FT-1006, PIC-1005. Derived flow agrees with pid_audit on L-101, L-102, L-103 and L-104.

**CQ14–CQ18** (`topology_queries`, with `--include-pending`, since nothing is accepted yet; without it CQ14–CQ17 are empty and say
152 vision facts were left out):

- `isolation PT-1001A`: taps L-101.3; upstream XV-1001 then HV-1001, ending at BL-100; downstream no valves, ending at V-1002.
- `isolation PT-1005`: upstream no valves back to V-1002; downstream an untagged gate valve, PV-1005, an untagged gate valve, ending at BL-200.
- `same_pressure PT-1001A`: candidates PT-1001B, PT-1001C, PI-1001, FT-1004 (same segment) and PT-1005 (5 hops, alarm PT-1005.PAH);
  blocked at BDV-1001, LV-1006, PV-1005, XV-1001. Headed "candidates for curation — not compensating measures".
- `blast_radius XV-1001`: L-101.3, FT-1004, L-101.4, V-1002; instruments FT-1004, PI-1001, PT-1001A/B/C, XV-1001; loops F-1004, L-1002,
  P-1001; SIF-100-01, -02, -03.
- `loop_membership PV-1005`: loop P-1005 (control, pressure); sensor PT-1005 on L-102.2 (index: L-102).
- `drawing_vs_ce`: 10 drawn trips, 11 C&E pairs; not drawn: SIF-100-03 PT-1001D → XV-1001; drawn and not in the C&E: none.
- Neo4j and memory backends give identical answers.

**Topology eval baseline** (`python -m eval.topology_eval --pidkg-eval`, frozen fixture, 10 Nov 2026; no pass threshold set):

| | Gold | Predicted | Correct | Precision | Recall |
|---|---|---|---|---|---|
| Tags | 21 | 23 | 21 | 0.913 | 1.000 |
| Flow pairs | 7 | 7 | 7 | 1.000 | 1.000 |
| Loops | 5 | 7 | 5 | 0.714 | 1.000 |
| Loop members | 17 | 25 | 17 | 0.680 | 1.000 |

Instrument placement 11 / 11 exact. Spurious: the interlock diamonds I-1 and I-2 read as tags and loops, and PI-1001 /
LG-1002 grouped into loops by tag number; none of these is loaded. Review workload: 20 of 120 facts flagged (0.167), none
below 0.85 confidence. pid-to-kg's own `eval_kg.py`: tags P 0.913 R 1.0, flow 1.0 / 1.0, placement 11 / 11, loops recall
1.0 with mean member overlap 0.927. These are clean synthetic sheets; they say nothing about real drawings.

**Stress test pilot** (real public drawings, extraction only, gold from a second model reader and unverified): tags P 0.933 R 1.0 on a
vector sheet (allowing one alias) and 81 of 81 on a 150 dpi scan; instrument placement 2 of 5 and 12 of 12; flow not scoreable on
isolated sheets. T5 flag rate 0.388 and 0.248 against 0.219 for U-100 without a master. Details and caveats in `docs/STRESS_TEST.md`.

**DEXPI class** (informative, with the vision layer on): 17 existing nodes carry `dexpiClass` (V-1002 Vessel; HV-1001 BallValve; 5 OperatedValve;
10 ProcessInstrumentationFunction) and all 6 InlineItems; none was seen without a class.

**Plant summary** (`summary_U-100.md`, nothing accepted): header says 152 vision facts are left out; flow BL-100 → L-101 → V-1002 and V-1002 to
BL-200, BL-103, FLARE-HDR; three index loops (FIC-1004, LIC-1006, PIC-1005); three SIFs; no segment-level flow or drawn loop yet.

**kg_suppression** (`C:\dev\kg_suppression`, `load_pid.py` dry run on `reports\graph_U-100.json` with the vision layer): 27 nodes, 26
relationships, 17 exceptions, byte-identical to its output from the v1.2 dump; every v1.3 label and relationship is "skipped by design".
Its tests: 109 passed (without its Neo4j round-trip test).

**Review register** (U-100, nothing decided yet): 120 facts, all pending, 20 of them priority
(T5); pending by sheet PID-100-001 85, PID-100-002 35. The trusted view of the graph with the
vision layer loaded is exactly the v1.2 graph (49 nodes / 164 relationships) until facts are accepted.

**Tests:** 289 collected; 289 passed with Neo4j up on port 7688 (10 Nov 2026, v1.3.0); 6 are skipped when Neo4j is down. At the v1.2 baseline it was 45. Before Phase 5 it was 187 collected; 183 passed, 4 skipped with Neo4j down. Before Phase 3 it was 152 collected; 148 passed, 4 skipped with Neo4j down. After Phase 1 it was 133 collected; 129 passed, 4 skipped with Neo4j down (the skips are the Neo4j-only
tests). At the v1.2 baseline it was 45 collected, 41 passed, 4 skipped; the session log says 44.
`test_v12_dump_is_byte_identical` rebuilds U-100 with `load_run = TX-0057-BASELINE` and compares
it byte for byte with the frozen fixture.

**Build** (command above): 49 nodes, 164 relationships, 0 conflicts. Identical to
`reports/graph_U-100.json` apart from the `load_run` timestamp.

- Nodes: Alarm 5, Document 8, Equipment 5, Instrument 20, Line 5, SIF 3, Scenario 3.
- Relationships: ACTUATES 5, COMPENSATES_FOR 3, CREDITS 6, FEEDS 9, GENERATES 4, INITIATES 6,
  INSTALLED_ON 23, MEASURES 11, PROTECTS 6, RAISES 1, SHOWN_ON 87, THREATENS 3.
- `extracted_by`: table 144, pid_audit 55, manual 14.

**Reconcile:** index coverage 94.1 %, P&ID match 94.1 %; 3 stub instruments; 20 exceptions:

| Code | Subject |
|---|---|
| X1 | TT-1003 (in index, not extracted) |
| X2 | FT-1006 (on P&ID, not in index) |
| X3 | XV-1002 (index says PID-100-002, extraction says PID-100-001) |
| X4 | PT-1001D (C&E only) |
| X5 ×2 | FT-1006 → L-105 and V-1002 → L-105 (confidence 0.61) |
| X8 ×4 | BL-100, BL-103, BL-200, FLARE-HDR |
| X9 | PAHH-1001 (C&E alarm effect not in the alarm register) |
| X10 | SIF-100-02 (2oo3 with two initiators listed) |
| X11 | PT-1001A.PAH (shares its sensor with SIF-100-01) |
| X12 | PID-100-003 rev A (registered, nothing extracted) |
| X13 | U100-PIDS-TX-0057.pdf page 1 (cover page) |
| X14 | SIF-100-03 (recorded gap, no compensating measure) |
| X15 | SIF-100-02 (LOPA SIL 2 vs SRS / C&E SIL 1) |
| X16 | SIF-100-01 (SRS 65 barg vs C&E 68 barg) |
| X17 | PT-1001A.PAH (credited alongside SIF-100-01) |
| X18 | PSV-1001 (credited, not in any register) |

**Gold set PID-100-001:** nodes P 1.000 / R 0.955; relationships P 1.000 / R 0.952. The one
miss is TT-1003 and its `INSTALLED_ON` L-101, deliberately absent from the extraction.

**Queries** *(log)*:

- `out_of_service PT-1001A`: SIF-100-01 DEGRADED (2 of 3 initiators remain); its own alarm
  PT-1001A.PAH is lost and is INVALID NOW as a compensating measure.
- `out_of_service XV-1001`: SIF-100-03 DEFEATED (only final element); SIF-100-01 and SIF-100-02
  DEGRADED.
- `trip SIF-100-02`: 2oo3 with two initiators listed.
- Re-issue TX-0042 → TX-0057: PID-100-001 C → D; PID-100-002 and -003 unchanged.
- With the sample out-of-service register applied: SIF-100-01 DEGRADED (2 valid measures),
  SIF-100-02 DEGRADED with no valid measure (LT-1006.LAH shelved), SIF-100-03 DEFEATED.
- Neo4j and memory backends give the same counts.

**Neo4j** (re-verified 10 Nov 2026 on `neo4j-pidgraph`, bolt 7688): v1.2 load 49 nodes / 164 relationships; with the vision
layer 81 / 284 and 11 uniqueness constraints. Every answer under *Queries* above was reproduced. With all vision facts
pending the four templates give exactly the v1.2 answers. pid_graph has its own container; `neo4j-kg` (7687) belongs to
kg_suppression and must not be loaded from here. `.env` must say `NEO4J_URI=bolt://localhost:7688`.
