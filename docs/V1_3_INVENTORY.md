# V1_3_INVENTORY.md — pid_graph v1.2 as found (Phase 0 of PIDKG_UPGRADE.md)

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Inventory date: 10 Nov 2026. Baseline tag: `v1.2-baseline`. No code was changed in Phase 0.

## 1. Result in one paragraph

The repo matches the plan's baseline once the baseline is read as the v1.2 *schema* (8 labels,
15 relationships) rather than the U-100 dump (7 and 12). None of the plan's 3 new labels or 4 new
relationships clashes with a v1.2 name, so there is no stop under Phase 0 step 5. Two things the
plan assumed are **absent**: CFIHOS / QUDT anchoring, and pid_audit itself (text-layer tags and
PDF markup). One thing is a **blocker for Phase 3**: the synthetic P&ID PDFs have title blocks
and no drawing graphics, so there is nothing for vision to read (section 7, item 1).

## 2. Tests and build

| Check | Result |
|---|---|
| `.venv\Scripts\python -m pytest -q` | **41 passed, 4 skipped** (45 collected) |
| Session log (9 Sep 2026, Session 4) | "44 tests pass" |
| The 4 skips | Neo4j-only tests; Neo4j was not running (`localhost:7687` refused). `test_mcp_smoke.py` ×1, `test_phase2.py` ×2, `test_phase3.py` ×1 |
| Collected per file | `test_phase1.py` 27, `test_phase2.py` 11, `test_phase3.py` 3, `test_phase4.py` 3, `test_mcp_smoke.py` 1 |

The session log says 44 tests and today's run collects 45 (41 passed, 4 skipped). The log does
not say which test is the extra one, and with no git history before today it cannot be traced.
Nothing failed. The four Neo4j tests are unverified today.

U-100 build, memory backend, written to a temporary folder so `reports\` was not touched:

```
.venv\Scripts\python -m pid_graph --unit U-100 --backend memory --pdf data\U100-PIDS-TX-0057.pdf --transmittal TX-0057 --out <temp>
```

| | Today | `reports/graph_U-100.json` (9 Sep 2026) |
|---|---|---|
| Nodes | 49 | 49 |
| Relationships | 164 | 164 |
| Conflicts | 0 | 0 |
| Exceptions | 20 | 20 (session log) |
| Gold set PID-100-001 | nodes P 1.000 / R 0.955; relationships P 1.000 / R 0.952 | same (session log) |

The two dumps are identical apart from the `load_run` timestamp. Rule 3 of the plan
("byte-for-byte") therefore needs a fixed `--load-run` value; the option exists.

## 3. Schema: baseline and clash check

Baseline = `README.md` / `PID_GRAPH_ONTOLOGY_V1_2.md` / `pid_graph/ontology.py`.

| | v1.2 schema | Seen in the U-100 dump | Not instantiated in U-100 |
|---|---|---|---|
| Labels | 8: `Instrument, Equipment, Line, SIF, Alarm, State, Document, Scenario` | 7 | `State` |
| Relationships | 15: `MEASURES, INSTALLED_ON, FEEDS, INITIATES, ACTUATES, PROTECTS, RAISES, CASCADES_TO, GENERATES, VALID_IN, HAS_STATE, COMPENSATES_FOR, CREDITS, THREATENS, SHOWN_ON` | 12 | `CASCADES_TO, VALID_IN, HAS_STATE` |

Clash check of the plan's additions against the full v1.2 lists:

| New in v1.3 | Clash with v1.2? |
|---|---|
| Labels `Segment`, `InlineItem`, `ControlLoop` | None |
| Relationships `SEGMENT_OF`, `FLOWS_TO`, `SIGNAL_TO`, `MEMBER_OF` | None |

Names pid-to-kg uses that pid_graph already owns with a **different meaning** — skipped, never
mapped: `CASCADES_TO` (ours: SIF → SIF ESD hierarchy from the C&E), anything `HAS_STATE` / `State`
-like (ours: reserved for the suppression design), and `ACTUATES` (ours: SIF → final element from
the C&E; already skipped in the plan).

Provenance as found: `ontology.PROVENANCE` = `source_doc, source_rev, source_sheet, extracted_by,
load_run`; `source_ref` is carried on all 213 facts in the dump but is not in that tuple.
`source_sheet` is present on 106 of 213. Every node carries `stub`. `extracted_by` allows
`pid_audit, llm, manual, table`; U-100 uses table 144, pid_audit 55, manual 14. `pidkg_vision`
will be a fifth value (Phase 1).

Competency questions: CQ1–CQ13 exist. The plan's five new ones are now **CQ14–CQ18**.

## 4. Actual file names

| Plan refers to | In the repo |
|---|---|
| Loaders | `pid_graph/loaders/`: `index_loader.py`, `ce_table.py` + `ce_loader.py`, `srs_loader.py`, `lopa_loader.py`, `curated_loader.py`, `pid_loader.py` (pid_audit topology CSV), `titleblock.py` + `docs.py` (P&ID PDF title blocks), `tables.py` (header aliases, shared reader) |
| Pipeline entry | `pid_graph/pipeline.py` (`build_store`), `pid_graph/run_all.py` (`python -m pid_graph`) |
| Schema / validators | `pid_graph/ontology.py` (`LABELS`, `KEYS`, `RELS`, `check_label`, `check_key`, `check_rel`, `check_provenance`) |
| Stores | `pid_graph/records.py` (`MemoryStore`, `to_dict()` writes the dump), `pid_graph/neo4j_store.py` |
| Tag normaliser | `pid_graph/tags.py` (`canonical_tag`, `canonical_id`, `classify`, `role`, `is_offpage`) |
| Exception register | Code: `pid_graph/reconcile.py` (`reconcile`, `write_register`, codes X1–X20). Output: `reports/exception_register_<unit>.xlsx` — sheets `Summary` (metric / value) and `Exceptions` (`code, title, label, id, detail, sources, refs`) |
| `conflicts` | `MemoryStore.conflicts`; top-level `conflicts` list in the dump; surfaced as X6 |
| Cypher templates | `pid_graph/queries.py`: `out_of_service`, `shelve_impact`, `moc_impact`, `trip` |
| CQ sketches / structural checks | `pid_graph/validate.py` |
| Eval | `eval/score.py` |
| Gold set | `eval/gold_PID-100-001.json` (22 nodes, 21 relationships; TT-1003 still awaits human confirmation) |
| Dump | `reports/graph_<unit>.json` |
| Topology input | `data/pid_audit_U100_topology.csv` (`sheet, from, to, line_no, confidence, verified`; 21 rows) |
| P&ID PDFs | `data/U100-PIDS-TX-0042.pdf`, `data/U100-PIDS-TX-0057.pdf` (4 pages: cover + 3 drawings) |
| Index columns used in Phase 6 | `loop` and `remarks` are loaded as Instrument properties (`index_loader.py`) |
| Tests | `tests/test_phase1.py` … `test_phase4.py`, `tests/test_mcp_smoke.py` |
| Ontology | `PID_GRAPH_ONTOLOGY_V1_2.md` |

## 5. Reference-data anchoring and pid_audit (point 6)

**CFIHOS / QUDT anchoring: absent.** No occurrence of CFIHOS, QUDT, `refClass`, RDL or DEXPI in
any source, test, data or document file other than the upgrade plan. No anchoring check exists.
Consequence, recorded and not built: Phase 10 adds `dexpiClass` as a standalone property.

**pid_audit: absent.** What exists is:

- its topology *export format*, known only from the dummy `data/pid_audit_U100_topology.csv`,
  read by `loaders/pid_loader.py` (session log: "pid_audit itself is not on this machine");
- the provenance value `extracted_by = pid_audit`, also stamped by pid_graph's own title-block
  reader (`loaders/titleblock.py`, D-P2-06);
- a provisional tag regex in `tags.py`, pending pid_audit's own rule (D-P1-02).

There is no text-layer tag extraction and no PDF markup code. PyMuPDF is used only to read
title-block text (`titleblock.py`, `intake.py`) and to fabricate the dummy PDFs. Consequences,
recorded and not built: the three-way tag check (T3) becomes index vs vision only, and the
Phase 5 markup is written fresh with PyMuPDF.

## 6. Edits made to PIDKG_UPGRADE.md

| Point | Edit |
|---|---|
| 3 | New competency questions renumbered CQ9–CQ13 → CQ14–CQ18 (section 2.5, Phase 6 item 4, Phase 7, "Later"). "Existing eight" → "existing thirteen". |
| 4 | "Assumed v1.2 baseline" replaced by the verified v1.2 schema (8 labels, 15 relationships), with the dump's 7 / 12 explained. Clash check recorded in section 2. pid-to-kg `CASCADES_TO` and state-like items listed under "not adopted" and in the Phase 4 mapping table as never mapped. |
| 5 | "edge" and "type" → "relationship" throughout (D-P4-06). Left alone on purpose: the dump key `rels`, the review-register column `type`, and kg_suppression's file name `edges.csv`. |
| 6 | Anchoring and pid_audit rows removed from the "keep" table; `dexpiClass` standalone (2.4, Phase 10); T3 and Phase 6 item 1 are index vs vision; Phase 5 markup written fresh with PyMuPDF. |
| 7 | Review register moved from `registers/topology_review_<unit>.csv` to `reports/review_register_<unit>.xlsx`, same workbook format as the exception register. |

## 7. Differences from the plan that were NOT edited (for Alan to decide)

1. **Phase 3 has nothing to extract — blocker.** `data/U100-PIDS-TX-0057.pdf` pages 2–4 are a
   border, a title block and the text "dummy drawing body - no graphics"
   (`scripts/make_dummy_pdf.py`). Vision extraction needs drawn U-100 P&IDs that agree with the
   index and the topology CSV. Either the dummy-PDF script is extended to draw them, or drawings
   are supplied.
2. **Rule 6, "dry run by default, `--apply` to write, same pattern as every other loader".** No
   existing loader has `--apply`. The pattern today is a full rebuild per unit; `--backend
   memory` is the de facto dry run. `--apply` would be new with `load_pidkg.py`.
3. **Phase 7, "memory-backend equivalents".** The four templates in `queries.py` take a Neo4j
   driver; there are no memory-backend versions today (the explorer re-implements them in
   JavaScript). Both sides would be new for CQ14–CQ18, and the "backends agree" test needs Neo4j
   running.
4. **T1, "not in index/equipment list".** There is no equipment list. Equipment nodes come from
   the index location column, the C&E, the LOPA and the topology CSV. The master for Equipment
   needs defining before Phase 4.
5. **T7 filter** lists `table, manual, pid_audit`. The schema also allows `llm` (unused). Leaving
   it out of the safety filter is consistent with the decisions doc; stated here so it is a
   choice, not an oversight.
6. **Review register in `reports\`.** README calls `reports/` git-ignored outputs. The review
   register holds an engineer's decisions and must be committed, so `.gitignore` ignores
   `reports/*` except `reports/review_register_*.xlsx`. Anything that wipes `reports\` would
   lose decisions.
7. **`.gitignore` changes beyond the list asked for.** The old file ignored `data/*`; `data/` is
   now tracked (synthetic, and the tests need it), except `data/external/`. The old file ignored
   only `reports/*.csv` and `*.json`; all of `reports/` is now ignored bar the review register.
   `.pytest_cache/`, `.venv-*/` and `.claude/settings.local.json` are ignored too.
8. **Neo4j not verified today.** 4 tests skipped; the query answers in `CLAUDE.md` marked *(log)*
   come from the session log.
9. **Stray `src/` folder.** `src/db.py` and `src/check_env.py` differ from the `pid_graph/`
   versions and nothing imports them. Committed as found.
10. **Small wording in code.** `ontology.py` error messages say "v1 ontology"; `README.md` title
    says "v1 ontology". Cosmetic.
11. **Phase 11 path to kg_suppression is wrong.** The plan uses `cd ..\..\kg_suppression`, which
    from this folder is `C:\Users\alanm\kg_suppression` and does not exist. kg_suppression is at
    `C:\dev\kg_suppression`. Not edited, because it is outside points 3–7.
12. **`CLAUDE.md` did not exist.** Phase 0 step 1 asks for it to be read; it was created in this
    phase from README, the decisions doc and the session log.
