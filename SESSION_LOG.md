# pid_graph session log

## 2026-09-08 - Session 1 (Claude Code, laptop)

### Done
- Found the earlier NetworkX prototype at `C:\Users\alanm\Documents\pid_graph` (3 Sep 2026): loaders
  with header aliasing, matrix C&E converter, findings F1-F6, queries, MCP server, MOC and bypass
  studies, plus `dummy_docs/`. Ported its table reading and C&E tag extraction; copied `dummy_docs`
  to `data/` as the Phase 1 sample unit (U-100).
- Built Phase 1 per decisions section 8, on the closed v1 ontology:
  `ontology.py` (validators), `tags.py`, `records.py` (MemoryStore with MERGE semantics and
  conflict capture), `neo4j_store.py` (constraints, wipe-per-unit, batched MERGE, read-back),
  `loaders/index_loader.py`, `loaders/pid_loader.py`, `loaders/ce_tags.py`, `reconcile.py`
  (exception register X1-X8 + coverage), `eval/score.py` + `eval/gold_PID-100-001.json`,
  `run_all.py` (`python -m pid_graph`). Tests in `tests/test_phase1.py`.
- End-to-end run on U-100 (`--backend memory`): 35 nodes, 113 edges, 0 conflicts;
  coverage 94.1% both ways; 13 exceptions, and every discrepancy planted in the dummy docs is
  caught (TT-1003 X1, FT-1006 X2, XV-1002 X3, PT-1001D and PAHH-1001 X4, one low-confidence edge X5).
  Gold set PID-100-001: nodes P 1.00 / R 0.955, edges P 1.00 / R 0.952 (the one miss is TT-1003,
  deliberately absent from the extraction).
- Decisions D-P1-01 to D-P1-10 appended to `PID_GRAPH_DECISIONS.md` section 10.

### Not verified
- The Neo4j backend has not been executed: Docker is not installed on this laptop. The Cypher
  in `neo4j_store.py` is generated and unit-tested for shape only. First real run should be
  `python -m pid_graph --unit U-100 --backend neo4j` and the counts must match the memory run
  (35 nodes / 113 rels).

### Blocked on (user)
1. Install Docker Desktop, create `neo4j-kg` (`docker run -d --name neo4j-kg -p 7474:7474 -p 7687:7687
   -e NEO4J_AUTH=neo4j/<password> -v neo4j-kg-data:/data neo4j:5`), copy `.env.example` to `.env`.
2. Confirm or correct the gold set (`eval/gold_PID-100-001.json`), especially TT-1003.
3. pid_audit itself is not on this machine; only its export format is known (from the dummy CSV).

### Next
- Run the neo4j backend; check constraints with `SHOW CONSTRAINTS`; sketch CQ1/CQ3/CQ7/CQ8 in Cypher
  against the loaded graph (ontology section 5 says do this before freezing the schema).
- Then Phase 2 per the decisions doc: C&E loader (SIF, INITIATES, ACTUATES, PROTECTS), Aconex PDF
  title-block pass (rev discovery, re-keying UNKNOWN documents), query templates.

### Open decisions
- Whether `table` should be added to the ontology's `extracted_by` list (D-P1-01).
- Whether P&ID-only instruments should be stubs in the graph or register-only (D-P1-07).

### Ontology change requests
- Add `table` to the `extracted_by` enumeration in section 4.
- Note in section 3 that relationship identity includes `source_doc` (parallel edges per witness).

### 2026-09-08 later - Docker install (same session)
- Installed via winget: Docker Desktop 4.90.0 and Microsoft.WSL 2.7.13 (kernel 6.18). Virtualization is
  enabled in firmware. User is in the docker-users group. Windows reports a pending reboot.
- Added `scripts/setup_neo4j.ps1`: reads NEO4J_PASSWORD from `.env`, creates/starts `neo4j-kg`
  (neo4j:5, volume neo4j-kg-data), waits for bolt, runs check_env.
- After reboot: start Docker Desktop, accept its in-app terms, create `.env`, run the script, then
  `python -m pid_graph --unit U-100 --backend neo4j`.

### 2026-09-09 - Neo4j verified (same session, after reboot)
- Docker Desktop 29.7.2 engine running; container `neo4j-kg` created by `scripts/setup_neo4j.ps1`
  (Neo4j Kernel 5.26.30, image neo4j:5, volume neo4j-kg-data, restart unless-stopped).
- `python -m pid_graph --unit U-100 --backend neo4j`: 35 nodes / 113 rels written, identical to the
  memory run; reconcile and eval read back from the DB give the same 13 exceptions and the same scores.
  Second run wiped 35 and rewrote 35/113 - full rebuild per unit is idempotent.
- Added `pid_graph/validate.py`: 7 constraints present; no labels or relationship types outside the
  ontology; no orphans; no nodes or edges without provenance; no duplicate tags; 7 stubs remaining
  (2 Documents rev UNKNOWN, 4 off-page Equipment, 1 P&ID-only Instrument FT-1006).
  CQ1, CQ3, CQ7, CQ8 sketches run and return the expected answers (CQ7 finds XV-1002 as the one
  index-vs-drawing disagreement; 15 instruments agree).

### Next (Phase 2, per decisions doc)
- C&E loader: SIF nodes, INITIATES (voting on the edge), ACTUATES, PROTECTS; then CQ2/CQ6 sketches.
- Aconex per-unit PDF title-block pass to replace `rev: UNKNOWN` Documents (decisions section 7);
  check one real PDF has a text layer first.
- Query templates `out_of_service(tag)`, `moc_impact(tag)`, `shelve_impact(alarm_id)` as tested Cypher.
- Confirm the gold set (TT-1003) with a human before freezing it.

## 2026-09-09 - Session 2 (Claude Code): Phase 2

### Done
- `loaders/ce_table.py` + `loaders/ce_loader.py`: matrix C&E -> SIF nodes, INITIATES (voting, setpoint),
  ACTUATES (action), PROTECTS, SHOWN_ON -> Document(CE). Alarm effects and the logic solver handled per
  D-P2-02 / D-P2-03.
- `reconcile.py`: X4 now graph-based; new X9 (alarm effect not modelled), X10 (voting arity),
  X11 (alarm shares SIF sensor), X12 (drawing registered, nothing extracted), X13 (PDF page problem).
- `loaders/titleblock.py` + `loaders/docs.py`: title-block reader, revision map, re-issue diff, Document
  registration with real revisions; index and topology loaders take the revision map.
- `scripts/make_dummy_pdf.py`: synthetic U-100 P&ID PDFs, first issue TX-0042 and re-issue TX-0057.
- `queries.py`: out_of_service / shelve_impact / moc_impact / trip templates with CLI.
- `validate.py`: CQ2 and CQ6 sketches added; orphan check excludes registered-but-unextracted drawings.
- `run_all.py`: `--ce`, `--ce-sheet`, `--pdf`, `--transmittal`; step 0 prints the title-block read and
  the diff against the graph.
- `tests/test_phase2.py`: 7 tests (34 total, all passing; the query test runs only when Neo4j is up).

### Verified against Neo4j
- Graph for U-100 with C&E + PDF: 41 nodes / 139 rels (Alarm 4, Document 5, Equipment 5, Instrument 19,
  Line 5, SIF 3; ACTUATES 5, FEEDS 9, GENERATES 4, INITIATES 6, INSTALLED_ON 23, MEASURES 11,
  PROTECTS 3, SHOWN_ON 78). 15 exceptions; no X7 left once the PDF is supplied.
- Re-issue TX-0057 diff: PID-100-001 C -> D detected, PID-100-002/003 unchanged, re-extract = [PID-100-001].
- out_of_service PT-1001A: SIF-100-01 DEGRADED (2 of 3 remain), own alarm PT-1001A.PAH lost,
  candidate compensation PT-1005 (PAH @ 60 barg, BPCS, 2 hops) then PI-1001 (field gauge).
  out_of_service XV-1001: SIF-100-03 DEFEATED (no final element left). trip SIF-100-02: 2oo3 listed 2.
- All structural checks pass; CQ1/2/3/6/7/8 sketches return the expected answers.

### Next
- Curate COMPENSATES_FOR for the three U-100 SIFs (engineering judgement, manual entries) and add
  VALID_IN / HAS_STATE from suppression design when that document exists (CQ4/CQ5).
- Ontology v1.1: `(SIF)-[:RAISES]->(Alarm)` (D-P2-02), `table` in extracted_by (D-P1-01), edge identity
  includes source_doc (D-P1-06), and `CASCADES_TO` when C&Es show ESD hierarchy (decisions section 6).
- First real inputs: a real instrument index (check header aliases), a real Aconex PDF (calibrate
  title-block region/regexes; check text layer), pid_audit's real export and tag regex (D-P1-02).
- MCP server exposing the four templates read-only, as the prototype did (decisions section 4 keeps
  free-form NLP-to-Cypher for exploration only).

### Open decisions
- Whether to feed the re-extract list back to pid_audit (D-P2-07) or keep full-unit rebuilds.
- Whether the X13 cover-page exception is useful or noise (could be suppressed for pages that
  contain the word TRANSMITTAL).

### 2026-09-09 - compensating measures (Session 2, continued)
- Drafted `data/curated/compensating_measures_U-100.csv` (3 proposals + 1 gap) with full rationale from
  the graph; built `loaders/curated_loader.py`, X14, `--curated` in run_all; 2 tests (36 total pass).
- Dry run: 0 edges loaded (all rows `proposed`), X14 on all three SIFs quoting the proposals / gap.
- AWAITING: engineer review of the register. To approve a row set status=approved and curated_by=<name>,
  then re-run the neo4j pipeline; `queries out_of_service` will then return curated_compensating_alarms.
- APPROVED by AB on 2026-09-09 (all three proposals; SIF-100-03 stays a recorded gap). Reloaded Neo4j:
  42 nodes / 144 rels incl. COMPENSATES_FOR x3; register 16 exceptions, X14 only on SIF-100-03.
- `out_of_service` now returns curated alarms with rank, basis, conditions, curator, and a validity flag:
  an alarm generated by the bypassed element itself is marked INVALID NOW (PT-1001A.PAH when PT-1001A
  is bypassed) and valid when a sibling is bypassed. 37 tests pass.

### 2026-09-09 - MCP server (Session 2, continued)
- `pid_graph/mcp_server.py` (mcp 2.2.0, MCPServer, stdio): 12 tools - graph_info, find, describe, list_sifs,
  documents, out_of_service, shelve_impact, moc_impact, trip, exceptions, schema_reference, read_cypher.
  `.mcp.json` points Claude Code at the venv python. `tests/test_mcp_smoke.py` starts it over stdio and
  calls every tool (pytest, skipped without Neo4j). Verified: a DETACH DELETE via read_cypher is rejected
  by the keyword filter, and a CREATE that bypasses the filter is rejected by the read transaction.
- Next session in this folder: Claude Code will offer the `pid_graph` server for approval; check with /mcp.

### 2026-09-09 - "do all in sequence" (Session 2, continued)
1. MCP check: `claude mcp list` in the project folder discovers `pid_graph` from `.mcp.json` and reports
   "Pending approval (run claude to approve)" - the interactive approval is the user's step.
2. Ontology v1.1 (`PID_GRAPH_ONTOLOGY_V1_1.md`, D-P2-12): RAISES + CQ9, CASCADES_TO + CQ10, `table`,
   edge identity, CUR, stub convention. Code follows the doc: ontology.py (13 rels), ce_loader
   (RAISES resolves via alarm_tag, stub otherwise; CASCADES_TO from SIF/ESD effects), reconcile X9
   redefined, queries.trip adds announced_by_alarms/cascades_to, shelve_impact adds announces_trip_of,
   validate CQ9/CQ10 + ontology lists taken from ontology.py, mcp schema_reference, check_env.
   Neo4j reloaded: 43 nodes / 146 rels (RAISES 1 -> stub Alarm PAHH-1001), 16 exceptions, all
   structural checks pass; CQ9 answers, CQ10 empty (no cascades in the dummy C&E). 39 tests pass.
3. Real inputs: blocked on the documents. Prepared `pid_graph/intake.py` (D-P2-13) and ran it on the
   four dummy files as a baseline (all recognised).

### Next
- User: approve the MCP server in a fresh session; provide a real index / C&E / pid_audit export /
  Aconex PDF and run `python -m pid_graph.intake` on each before the first pipeline run.
- Then: calibrate aliases / tag regex / title-block region from the intake report; first real
  reconciliation report; gold set on one real drawing.

### 2026-09-09 - MCP server approved and verified end to end
- User logged the terminal CLI in, approved the `pid_graph` project server (/mcp shows 12 tools), and asked
  "what happens if XV-1001 is bypassed?". Claude answered from the graph: SIF-100-03 DEFEATED (only final
  element), SIF-100-01/02 DEGRADED, curated alarms with rank/basis/validity and curator AB, X14 for
  SIF-100-03. First successful plain-English answer with graph provenance.
- The terminal's /auto-mode-setup wizard also ran (user-triggered); it added permission rules for that CLI
  profile only (docker neo4j-kg allow, tripwire on non-local Neo4j wipes). Not part of the project.

### 2026-09-09 - visual explorer
- `pid_graph/explorer.py` writes `reports/explorer_<unit>.html`: self-contained SVG force-layout explorer of
  the live graph (no libraries, no login). Captions = canonical keys, arrows labelled by type, stubs dashed,
  label/relationship filters, presets, find box, click-for-properties with provenance. SHOWN_ON hidden by
  default. Verified rendering in the app's browser pane via `.claude/launch.json` (python http.server on
  reports/, port 8771). Neo4j Browser (http://localhost:7474) remains the live alternative; its node
  captions default to a provenance property and must be set to tag/sif_id/alarm_id per label.

### 2026-09-09 - engineer reports
- `pid_graph/report.py`: `compensating-measures` (register for the unit: source documents + revisions, summary
  table, per-SIF trip function, voting check, trip announcement, curated measures with basis/conditions/
  rationale/curator, data caveats from the exception register) and `bypass <tag>` (draft SIS bypass
  assessment: per-SIF DEGRADED/DEFEATED, curated measures with validity, alarms lost, candidate shortlist
  labelled heuristic, required actions). Markdown + Word (python-docx). Generated for U-100 and XV-1001.
- Explorer gained in-page reports (no server, no login): "Bypass assessment for selected" (instrument) and
  "Compensating measures register", same logic as report.py, printable / save-as-PDF. Verified in the app
  browser pane: XV-1001 -> worst case DEFEATED; PT-1001A -> PT-1001A.PAH flagged INVALID NOW; register shows
  the SIF-100-03 gap and the SIF-100-02 voting mismatch.
- Explorer: "Source documents" section lists every Document node (type, number, rev, transmittal, title) and
  the extraction file, each linked to the file under data/ (PDFs open at the drawing's page). Selecting any
  node or arrow shows a link to its source document and the extraction file plus the file:sheet:row ref.
  The register report's source table links the files too. Links are relative (../data/...) so they work
  offline as long as the reports/ and data/ folders travel together.
- Explorer routine assessments (in-page, printable): Bypass assessment (instrument), MOS assessment
  (initiator; same logic as bypass with override wording), Alarm shelving impact (CQ4: indication lost,
  SIFs on the same sensor, other alarms on the variable at the location / within 2 FEEDS hops, curated
  compensating-measure role flagged HIGH, trip announcement, VALID_IN states), MOC impact analysis (CQ3:
  BFS over the impact relationships, hops 1-5, MOC reference, affected items with 'reached via',
  affected SIFs with curated measures, documents to re-verify with links, review actions). Buttons
  enable per selection type. Verified in the app browser pane on PT-1001A / PT-1005.PAH / L-101.

## 2026-09-09 - Session 3 (Claude Code): operations features
- `pid_graph/oos.py` + `data/oos/out_of_service_U-100.csv` (dummy: XV-1001 bypass, LT-1006.LAH shelved,
  one closed MOS): apply / list / status; `run_all` re-applies after rebuild (D-P3-01).
- Combined protection status verified: SIF-100-01 DEGRADED (2 valid measures), SIF-100-02 DEGRADED with
  NO valid measure because LT-1006.LAH is shelved, SIF-100-03 DEFEATED.
- Explorer: red-ringed BYPASSED / SHELVED badges, "Out of service now" list (expiry countdown, CM confirmed),
  all assessments combined with the register ("already out" table, INVALID NOW for shelved measures),
  "Shift handover protection status" and "Trip investigation pack" buttons.
- `report.py`: `handover` and `trip-pack <sif>` (md + docx). `tests/test_phase3.py` (41 tests pass).

## 2026-09-09 - Session 4 (Claude Code): SRS and LOPA (ontology v1.2)
- `PID_GRAPH_ONTOLOGY_V1_2.md` (CQ11-CQ13; Scenario, CREDITS, THREATENS; SRS props on SIF; SRS/LOPA doc types).
- `scripts/make_dummy_srs_lopa.py` -> `data/U100-SRS-001-Rev-B.xlsx`, `data/U100-LOPA-001-Rev-A.xlsx` (dummy,
  4 planted discrepancies). `loaders/srs_loader.py`, `loaders/lopa_loader.py`; aliases in tables.py; intake
  recognises both. Reconcile X15-X20. run_all `--srs`, `--lopa` (defaults to the dummy files).
- Verified (memory and Neo4j, 49 nodes / 164 rels, 20 exceptions): X15 SIF-100-02 (LOPA SIL 2 vs SRS/C&E
  SIL 1), X16 SIF-100-01 (65 vs 68 barg), X17 PT-1001A.PAH (credited alongside SIF-100-01 it shares a sensor
  with), X18 PSV-1001 (credited, not in index). CQ11/12/13 sketches run in validate.py.
- Explorer: Scenario nodes (teal), "SIF design basis (SRS + LOPA)" button, SRS-vs-C&E comparison and LOPA
  scenarios in the register report, SRS safe state / response time in the trip pack, SRS bypass conditions
  quoted in bypass and MOS assessments. report.py: same sections in the Word register and trip pack.
- MCP instructions mention v1.2. `tests/test_phase4.py` (44 tests pass).
- `oos.py` gained `close <id> --by`, `add <element> --kind --hours --by --requester --reason [--cm-confirmed]`,
  `remove <id>... | --all`; each re-applies the register to the graph unless `--no-apply`. Entries the user adds
  get the next OOS-<year>-NNN id. The sample register was reset to its two active demo entries after testing
  (the user had closed OOS-2026-042 themselves while trying the close command).
- Vocabulary rule D-P4-06 applied: node/relationship on engineering surfaces, element on the handover page.

## 2026-11-10 - Session 5 (Claude Code): v1.3 upgrade, Phases 0 and 1
- Phase 0 (`PIDKG_UPGRADE.md`): git initialised, v1.2 as found tagged `v1.2-baseline`; `CLAUDE.md` and
  `docs/V1_3_INVENTORY.md` written; plan corrected against the repo (CQ14-CQ18, 8 labels / 15 relationships
  baseline, no anchoring or pid_audit code, review register in `reports/`). 41 passed, 4 skipped (Neo4j down).
- Phase 1, branch `v1.3/phase-1-ontology`: `PID_GRAPH_ONTOLOGY_V1_3.md`; `ontology.py` gains Segment, InlineItem,
  ControlLoop, SEGMENT_OF, FLOWS_TO, SIGNAL_TO, MEMBER_OF, Segment in the range of MEASURES / INSTALLED_ON,
  `pidkg_vision`, `review`, required properties of the new labels, closed values on the new relationships and
  the InlineItem safety-relationship ban; `records.py` calls the new checks; MCP `schema_reference` lists the
  new relationships. `tests/test_v13_phase1.py` (88 cases) plus the frozen dump
  `tests/fixtures/graph_U-100_v1_2.json`: the U-100 build is byte-identical to v1.2. 129 passed, 4 skipped.
- Not verified: the 4 Neo4j tests (Neo4j not running). `ensure_schema` will create three more uniqueness
  constraints (segment_id, item_id, loop_key) on the next neo4j run.
- Open before Phase 3: the synthetic P&ID PDFs have no drawing graphics (inventory section 7, item 1).
- Phase 2, branch `v1.3/phase-2-pidkg-tool`: pid-to-kg cloned to `third_party/pid-to-kg` at commit 7ee3a82
  (git-ignored, unmodified); separate `.venv-pidkg` (Python 3.14.3); its own tests: 78 passed. OCR package not
  installed (needs Python 3.10-3.12), so OCR hints and auto-orientation will be skipped in Phase 3.
  `THIRD_PARTY_NOTICES.md` records source, commit, licence, set-up and the run log. `tests/test_v13_phase2.py`.
- Drawn dummy P&IDs, branch `v1.3/dummy-drawings`: `scripts/make_dummy_pdf.py` now draws the three sheets
  (ISA-style, vector) from the index, the pid_audit topology export and the C&E; `--all` rebuilds both issues
  and `data/U100-PIDS-DRAWN-CONTENT.json` (answer key). Planted discrepancies kept: TT-1003 and PT-1001D not
  drawn, FT-1006 on PID-100-002, XV-1002 on PID-100-001. Title blocks and the v1.2 dump unchanged.
  `tests/test_dummy_drawings.py`. 148 passed, 4 skipped.
- Open: `eval/gold_PID-100-001.json` still lists TT-1003 on L-101 "pending human confirmation"; the drawing
  now says it is not there. Gold set left untouched for Alan to decide.
- Phase 3, branch `v1.3/phase-3-extraction`: pid-to-kg run on `data/U100-PIDS-TX-0057.pdf` pages 2-4 in
  `work/U-100` (probe, render, hints, three page extractions by a fresh subagent that did not see the answer
  key, build, QA). 84 nodes / 140 relationships, QA 0 errors and 1 checked warning (F-1004 has no final
  element). Fixture frozen in `tests/fixtures/pidkg_U-100/` (graph.json, qa_report.md, extract/, RUN.md);
  `tests/test_v13_phase3.py`. Extraction agrees with `data/U100-PIDS-DRAWN-CONTENT.json` on every tag, line,
  fitting, fail position and off-page pair.
- For Phase 4 / 6 (details in RUN.md): interlock diamonds I-1 / I-2 came out as Instruments, so drawn trips are
  two-hop; pid-to-kg's derived TRIPS wrongly includes PI-1001 and LG-1002; boundary names are flag text
  ("FEED GAS FROM BL-100"), not tags.
- Phase 4, branch `v1.3/phase-4-loader`: `pid_graph/load_pidkg.py` (pure `reconcile`, `apply`, dry-run CLI with
  `--apply`), `--pidkg` switch in `run_all` (off by default), exception codes X21-X29 in the same register.
  Decided by Alan: interlock symbols are collapsed into direct initiator -> final element trip signals (`via`),
  one X29 row per symbol. Also: pid-to-kg's derived TRIPS is not used; boundaries match on the tag inside the
  flag text; Equipment master = non-stub Equipment in the graph. On U-100: +32 nodes, +120 relationships, all
  review=pending, 15 new exceptions, 0 conflicts. `tests/test_v13_phase4.py` (25 cases). 183 passed, 4 skipped.
- Not verified: Neo4j write of the new labels (Neo4j not running). `--no-master --report-only` (Phase 9) not built.
- Phase 5, branch `v1.3/phase-5-review`: `pid_graph/review.py` (review register read / write-back, T5 flags, PDF
  markup), `reports/review_register_U-100.xlsx` committed (120 facts, all pending, 20 priority), T7 gate as
  `ontology.trusted()` / `queries.trusted_rel()` / `records.TrustedView`, applied in `queries.py`, `report.py`
  and the explorer (`--include-pending` to see everything). MCP instructions and `read_cypher` note say that
  lookup tools may show pending facts. `tests/test_v13_phase5.py` (17 cases). 200 passed, 4 skipped.
- NOT VERIFIED: the edited Cypher in `queries.py` and `report.py` has not been run against Neo4j (not running).
  First thing to do when Neo4j is up: `python -m pytest -q` (4 Neo4j tests) and one of each template.
- Neo4j verification (same branch, second commit). The shared container `neo4j-kg` (7687) turned out to hold the
  kg_suppression graph (K-101; 35 nodes) and no U-100 data, so nothing was loaded into it. pid_graph now has its
  own container `neo4j-pidgraph` (bolt 7688, browser 7475, volume neo4j-pidgraph-data); `scripts/setup_neo4j.ps1`
  takes NEO4J_CONTAINER / NEO4J_URI / NEO4J_HTTP_PORT, refuses another container's ports and waits for a real
  connection; `check_env` and `.env.example` follow.
- Results on 7688: v1.2 load 49 / 164; vision layer 81 / 284, 11 constraints, structural checks clean. All
  pending: four templates identical to v1.2 answers. Segment L-101.3 + PT-1001A MEASURES accepted in a scratch
  register: only those appear (moc_impact, trip, shelve_impact, CM register, trip pack). Reports and explorer run.
  Database left with the vision layer loaded and nothing accepted.
- Defect found and fixed: queries matched nodes on `line_no`, which a Segment also carries; an accepted Segment
  was matched as the Line (duplicate moc_impact rows, shown as "L-101"). Now `(x:Line AND x.line_no = $id)` and
  `segment_id` in the id / measures columns; regression test in `tests/test_v13_phase5.py`.
- OPEN, needs Alan: `.env` still has NEO4J_URI=bolt://localhost:7687. Until it says 7688, `tests/test_mcp_smoke.py`
  fails (the MCP server it starts reads `.env`) and the pid_graph MCP server in Claude Code talks to kg_suppression's
  database. With NEO4J_URI=bolt://localhost:7688 in the environment: 204 passed, 1 failed (that test); the same
  test body passes when the server is given the environment.
- `.env` now points at `bolt://localhost:7688` (changed at Alan's request; the file is git-ignored). With no
  overrides: environment check OK, 205 passed, 0 skipped, 0 failed. The open item above is closed.
- Phase 6, branch `v1.3/phase-6-checks`: `pid_graph/vision_checks.py` (six reconciliation checks, exceptions
  X30-X36, tag regions per sheet, derived FEEDS reported and not written), wired into `run_all --pidkg` and the
  `load_pidkg` dry run. Fixture `tests/fixtures/pidkg_U-100/graph_discrepancies.json` (one planted discrepancy per
  check, `scripts/make_pidkg_discrepancies.py`, `DISCREPANCIES.md`). Loader: a trip drawn without an interlock
  symbol is now in `drawn_trips` too. Real U-100: X30 XV-1002, X34 SIF-100-03. `tests/test_v13_phase6.py`
  (27 cases). 232 passed, Neo4j up.
- Phase 7, branch `v1.3/phase-7-templates`: `pid_graph/topology_queries.py` - CQ14 isolation, CQ15 same_pressure,
  CQ16 blast_radius, CQ17 loop_membership, CQ18 drawing_vs_ce; each written once over backend primitives with a
  Cypher form and an in-memory form; trusted facts only unless `--include-pending` (labelled EXPLORATION ONLY);
  CQ18 reads pending by default. `tests/test_v13_phase7.py` (15 cases) including Neo4j-vs-memory agreement, which
  mirrors whatever review state the database holds. Verified on `neo4j-pidgraph` all-pending and with 72 accepted /
  1 rejected (scratch register); database restored to all-pending. 247 passed.
- Not done: the new templates are not MCP tools; `validate.py` has no CQ14-CQ18 sketches.
- Phase 8, branch `v1.3/phase-8-eval`: `eval/gold_topology_U-100.json` (tags, 11 placements, 7 flow pairs, 5 loops)
  and `eval/gold_pidkg_U-100.json`, both built by `eval/make_topology_gold.py` from the drawings' answer key;
  `eval/topology_eval.py` (scores before the gate, review workload after it, `--pidkg-eval` runs pid-to-kg's
  own scorer); `eval/TOPOLOGY_BASELINE.md`. Baseline: tags P 0.913 R 1.0, flow 1.0 / 1.0, loops P 0.714 R 1.0,
  loop members P 0.68 R 1.0, placement 11 / 11, 20 of 120 facts flagged. No threshold set (Alan's call).
  `tests/test_v13_phase8.py` (11 cases). 258 passed.
- Open for Alan: set the pass thresholds; `eval/gold_PID-100-001.json` still lists TT-1003 pending confirmation.
- Phase 9 (pilot), branch `v1.3/phase-9-stress-test`: `load_pidkg --no-master --report-only`. Alan asked for the two
  public sets to be downloaded; they are in git-ignored `data/external/` (Pahala 7.3 MB epa.gov, Virden 3.3 MB
  gov.mb.ca). Extracted two sheets of each in `work/pahala` and `work/virden` with independent subagents; gold for
  Pahala p.11 and p.20 and Virden p.6 written by separate subagents that could not see the extractions, in
  `data/external/gold/`. Scores in `eval/stress_test_scores.json` (numbers only) and `docs/STRESS_TEST.md`.
  Tags agree well (Virden scan 81 of 81); flow is not scoreable on isolated sheets; T5 flag rate 0.388 / 0.248.
- OPEN for Alan: gold files are not engineer-checked; decide whether to run the other 23 sheets (about 2.5 M tokens);
  no OCR on this machine.
- Phase 10, branch `v1.3/phase-10-summary`: `dexpiClass` carried onto InlineItems and onto the existing Equipment /
  Instrument nodes vision saw (with `dexpiClass_source`; informative, read by nothing; a differing class is a conflict);
  loader lists nodes seen with no class; two `validate.py` checks. `pid_graph/summary.py` writes `summary_<unit>.md`
  from the trusted view (T7), rule-based, stating how many vision facts were left out; the pipeline writes it on every
  run. `tests/test_v13_phase10.py` (11 cases); one Phase 4 test now ignores the dexpiClass pair when it compares v1.2
  nodes. Verified on `neo4j-pidgraph` all-pending and with 72 accepted / 1 rejected; database restored to all-pending
  (and now carries dexpiClass). 282 passed.
- Phase 11, branch `v1.3/phase-11-close-out`, tag `v1.3.0`: README (v1.3 cheat sheet, layout), CLAUDE.md, ontology
  v1.3 "As built", decisions section 14 (D-V13-01..11), check_env and MCP text now name v1.3.
  `tests/test_v13_phase11.py` checks the documents' closed lists against the code. `reports/graph_U-100.json`
  regenerated with the vision layer (81 / 284); the September files are in `reports/_before_v1.3/`.
  kg_suppression (`C:\dev\kg_suppression`): `load_pid.py` dry run to a temporary folder gives output byte-identical
  to that from the v1.2 dump (27 nodes, 26 relationships, 17 exceptions), all v1.3 facts skipped by design; its
  tests 109 passed without `tests/test_neo4j.py`; nothing in that folder changed. 289 passed here.
- STATE AT CLOSE: `main` ends at the Phase 0 commit. Branches v1.3/phase-1-ontology ... v1.3/phase-11-close-out are
  one straight line on top of it; nothing is pushed. Neo4j `neo4j-pidgraph` (7688) holds U-100 with the vision
  layer, everything pending. `reports/review_register_U-100.xlsx`: 120 facts, none decided.
- OPEN FOR ALAN: review the register (nothing is usable by the safety templates until accepted); merge the branches
  to main; set eval pass thresholds; check the stress-test gold files; TT-1003 in `eval/gold_PID-100-001.json`;
  Python 3.12 for OCR; whether to run the other 23 public sheets.
- 2026-11-10, after the tag: `main` fast-forwarded to `v1.3.0` at Alan's request (a8c4aa0); 289 passed on main.
  The "main ends at the Phase 0 commit" notes above and in PIDKG_UPGRADE.md Phase 11 describe the state before
  this. The phase branches are still there and can be deleted. Nothing is pushed; there is no remote.


## 2026-11-12 - Session 6 (Claude Code): GitHub backup and test documents, batch 1

- Remote added: https://github.com/FellaB-2025/2025-pid_graph (private). Pushed `main` and tags `v1.2-baseline`, `v1.3.0`;
  the phase branches were not pushed.
- `docs/TAG_LOCATION_INVENTORY.xlsx` (draft, untracked): document types D01-D28 and questions Q1-Q8, amber columns for Alan.
- Branch `batch-1/dummy-documents`: `scripts/make_dummy_batch1.py` writes `U100-SILV-001-Rev-A.xlsx`, `U100-MADB-001-Rev-A.xlsx`,
  `U100-CFG-EXPORT-Rev-A.xlsx`, `U100-MOC-REG-Rev-A.xlsx` and `U100-BATCH1-ANSWER-KEY.json` (23 planted items, every Q1-Q8
  covered). Three rows added to `U100-DOC-REGISTER.csv`. No loader reads them yet; no schema change.
  `tests/test_batch1_documents.py` (17 cases). 300 passed, 6 skipped (Neo4j not running).
- OPEN for Alan: review the planted items in the answer key; decide how the new document types enter the ontology
  (Document.doc_type is closed: PID, CE, IDX, CUR, SRS, LOPA).
- Same day, branch `demo/scenario-explorer` (on top of batch 1). Alan's aim: a demonstration for colleagues where he
  picks a scenario (bypass, shelving, MOC ...) and the graph shows the relationships. Built without a schema change
  (D-V13-12): five loaders for the operations documents (off by default), `ops_checks.py` (C1-C16, MOC impact rules
  I1-I5, scorecard), `demo.py` (nine templates, 93 scenarios on U-100), `demo_page.py`. `U100-DOC-REGISTER.csv` gained a
  title block (Rev A) so it has a revision; `tests/test_batch1_documents.py` reads it through `read_table` now.
  Published privately: https://claude.ai/artifact/6q2YAhHoohUn2HyCCV3XFa. `docs/DEMO_GUIDE.md`, skill
  `.claude/skills/kg-demo`. `tests/test_ops_demo.py` (18 cases).
- Honest limits, also in the guide: the checks were written knowing what batch 1 planted, so 23 of 23 shows the method
  works end to end, not that it finds unknown problems; the as-installed SIL figure for SIF-100-02 is in the answer key,
  not computed by the graph; Neo4j was not used (memory backend) and the MCP server does not expose the C-checks.
- OPEN for Alan: walk the nine showcase scenarios and say which wording is wrong for an engineer; decide whether batch 2
  should be a blind test (documents planted by one agent, checks unchanged); fill the amber columns of the inventory.
- Same day, later. Build-your-own situation: `pid_graph/situation.py` (rules S1-S8, Python reference + the page's JavaScript,
  compared by `tests/test_situation.py` on 900-odd combinations) and a tab on the page. The demonstrator is unit-neutral now
  (`demo.unit_config`, `ops_checks.sheet_aliases`); tag `blind-freeze-1` marks the checks before the blind test.
- Blind test on U-200 (protocol and full result in `docs/BLIND_TEST.md`): 12 of 24 found outright, 3 partly, 9 missed; 5 of 8 traps wrongly flagged; 15 false alarms in 85 findings.
  Planter and scorer were separate agents; the runner committed the sealed findings before opening the key.
- Alan asked for pushes to happen automatically after every commit from now on (both private repositories).
- OPEN: fix the false alarms and the missing comparisons as general rules (BLIND_TEST.md sections 6 and 9), fix the two wrong
  scenario statements the test exposed, then a new blind unit. U-200 has no P&IDs, so X1 fires 37 times there.


## 2026-11-12 - Session 7 (Claude Code): fixes after the blind test

- Working tree at the start: clean apart from `docs/TAG_LOCATION_INVENTORY.xlsx` (still untracked). Its "In pid_graph today" and
  "Gap today" cells and its Read me were brought up to date with the operations loaders; the amber columns are still Alan's.
- Fixes as general rules (BLIND_TEST.md sections 6 and 9; the result is in its new section 10, the record above it untouched):
  `pid_graph/quantities.py` (values compared with their units); C5, C7 and C11 made unit-aware, per cent of span read through the
  index range, the compound SRS proof-test cell split; X16 in `reconcile.py` compares quantities (the v1.2 dump is still byte-identical);
  C10 extended to final elements; new checks C17-C26; a rule can set a finding's level (`add(level=)`: C3 trip notification is
  information, C20 and C21 are stop when a SIF is involved); `silv_loader` keeps `rrf_target_silv` and `target_source_silv`.
- Scenario templates: a recorded bypass quotes its out-of-service entry; a trip verdict looks at C17, C10 final elements and C20;
  a bypass of a device not on the logic solver is a stop; a closed MOC with an as-found disagreement is a caution; a temporary
  change is judged on whether it was removed; C19 does not count as "impaired" for a compensating alarm; "Everything impaired
  now" shows C24 and C25.
- U-200 after the fixes (regression, self-checked): 24 of 24 planted items have a finding; 87 findings. U-100: 66 findings, 23 of 23.
- `tests/test_blind_fixes.py` (12 cases). `blind-freeze-1` no longer matches the checks, so `eval/blind_run.py` refuses to run
  against it: the next blind unit needs a new freeze tag.
- One existing test edited, with Alan's agreement (the one exception to rule 12, noted in the test):
  `tests/test_ops_demo.py::test_every_check_fires_on_the_test_documents_and_names_its_sources` now takes the test documents to be
  those of U-100 and U-200, because eight new checks (C18, C20-C26) have nothing to fire on in U-100; it still requires C2-C16 on
  U-100 alone. 371 passed, 6 skipped (Neo4j not running).
- Page rebuilt and republished at the same link (version 5): 93 scenarios, 66 findings, 23 of 23.
- OPEN for Alan: is C19 the right comparison for a pre-alarm; should trip notifications be in the MADB (C3 is information for now);
  whether to narrow MOC impact rule I2; the next blind unit.
