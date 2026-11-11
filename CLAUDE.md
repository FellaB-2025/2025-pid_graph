# CLAUDE.md — pid_graph

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Read this file in full before touching anything. It is a summary of `README.md`,
`PID_GRAPH_DECISIONS.md` and `SESSION_LOG.md`; where it and those documents disagree, they win
and this file is corrected.

## 1. Purpose

pid_graph is a cross-document knowledge graph for the functional-safety layer of a process unit:
instrument index + P&IDs + cause & effect chart + SRS + LOPA, on Neo4j, with a closed schema
(ontology v1.2). It answers one family of questions with full provenance: *this element is out of
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
plus the rows marked v1.3; nothing in v1.2 changed meaning. The v1.3 rows are in the schema and the
validators only: no loader writes them until Phase 4 of `PIDKG_UPGRADE.md`.

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
`Document.doc_type` ∈ `PID, CE, IDX, CUR, SRS, LOPA`; unknown revision = `UNKNOWN`.

Competency questions CQ1–CQ18 are defined in the ontology document (CQ14–CQ18 are new in v1.3
and have no templates yet).

## 4. Files

| Path | What it is |
|---|---|
| `PID_GRAPH_ONTOLOGY_V1_3.md` | The closed schema and competency questions (v1, v1.1 and v1.2 kept for the record) |
| `PID_GRAPH_DECISIONS.md` | Reasoning and numbered decisions (D-P1-xx … D-P4-xx) |
| `SESSION_LOG.md` | Running log for cold pickup |
| `PIDKG_UPGRADE.md` | Plan for v1.2 → v1.3 (segment topology + vision extraction) |
| `docs/V1_3_INVENTORY.md` | Phase 0 inventory of the repo against that plan |
| `pid_graph/ontology.py` | Closed schema + validators (`check_label`, `check_key`, `check_rel`, `check_provenance`) |
| `pid_graph/tags.py` | Canonical tag regex, prefix classification, `role()` |
| `pid_graph/records.py` | `MemoryStore` (MERGE semantics, conflicts, `to_dict()` dump) |
| `pid_graph/neo4j_store.py`, `db.py` | Constraints, wipe-per-unit, batched MERGE, read-back; driver from `.env` |
| `pid_graph/loaders/` | `tables.py` (header aliases), `titleblock.py`, `docs.py`, `index_loader.py`, `ce_table.py`, `ce_loader.py`, `srs_loader.py`, `lopa_loader.py`, `curated_loader.py`, `pid_loader.py` |
| `pid_graph/pipeline.py`, `run_all.py` | `build_store()`; `python -m pid_graph` end to end |
| `pid_graph/reconcile.py` | Coverage + exception register (codes X1–X20; titles for X21–X29) |
| `pid_graph/load_pidkg.py` | v1.3 vision layer: pid-to-kg `graph.json` → Segment, InlineItem, ControlLoop, FLOWS_TO, SIGNAL_TO, MEMBER_OF, with exceptions X21–X29. Dry run by default; `--apply` to write. In the pipeline: `python -m pid_graph --pidkg <graph.json>` (off by default) |
| `pid_graph/review.py` | Review register (`reports/review_register_<unit>.xlsx`: read back on every load, decisions need a named reviewer), T5 priority flags, and the PDF markup of vision facts (`review_markup_<unit>.pdf`) |
| `reports/review_register_U-100.xlsx` | The one committed file in `reports/`: the engineer's accept / reject decisions on vision facts |
| `tests/fixtures/pidkg_U-100/` | Frozen pid-to-kg extraction of the synthetic P&IDs (`graph.json`, `qa_report.md`, `extract/`, `RUN.md`) |
| `pid_graph/queries.py` | Fixed Cypher templates: `out_of_service`, `shelve_impact`, `moc_impact`, `trip` (Neo4j only) |
| `pid_graph/validate.py` | Structural checks + CQ sketches on the live graph |
| `pid_graph/mcp_server.py`, `.mcp.json` | Read-only MCP server (12 tools, stdio) |
| `pid_graph/intake.py` | Readiness check for a new document |
| `pid_graph/explorer.py` | Self-contained HTML explorer with in-page assessments |
| `pid_graph/report.py`, `oos.py` | Engineer reports (md + docx); out-of-service register |
| `eval/score.py`, `eval/gold_PID-100-001.json` | Gold-set scorer and gold set |
| `tests/` | `test_phase1.py` … `test_phase4.py`, `test_mcp_smoke.py`, `test_v13_phase1.py`; `tests/fixtures/graph_U-100_v1_2.json` is the frozen v1.2 dump |
| `scripts/` | `setup_neo4j.ps1`, `make_dummy_pdf.py`, `make_dummy_srs_lopa.py` |
| `data/` | Synthetic U-100 documents; `data/curated/`, `data/oos/`, `data/moc/`. The P&ID PDFs carry drawn sheets made by `scripts/make_dummy_pdf.py --all`; `data/U100-PIDS-DRAWN-CONTENT.json` is the answer key for what each sheet shows (not read by any loader) |
| `reports/` | Generated outputs (git-ignored): `exception_register_<unit>.xlsx`, `graph_<unit>.json`, `load_report_<unit>.json`, explorer, reports |
| `src/` | Two early stray copies of `db.py` / `check_env.py`; not imported by anything |

Commands are in `README.md`. The usual build:

```
.venv\Scripts\python -m pid_graph --unit U-100 --backend memory --pdf data\U100-PIDS-TX-0057.pdf --transmittal TX-0057
```

## 5. Known-good answers (U-100)

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

**Review register** (U-100, nothing decided yet): 120 facts, all pending, 20 of them priority
(T5); pending by sheet PID-100-001 85, PID-100-002 35. The trusted view of the graph with the
vision layer loaded is exactly the v1.2 graph (49 nodes / 164 relationships) until facts are accepted.

**Tests:** 204 collected; 200 passed, 4 skipped with Neo4j down. Before Phase 5 it was 187 collected; 183 passed, 4 skipped with Neo4j down. Before Phase 3 it was 152 collected; 148 passed, 4 skipped with Neo4j down. After Phase 1 it was 133 collected; 129 passed, 4 skipped with Neo4j down (the skips are the Neo4j-only
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
