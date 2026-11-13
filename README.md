# pid_graph (Neo4j, ontology v1.3)

Cross-document knowledge graph for the functional-safety layer of a process unit:
instrument index + P&IDs + C&E, on Neo4j, with a closed schema.

* Schema: `PID_GRAPH_ONTOLOGY_V1_3.md` (11 labels, 19 relationships, provenance on everything; v1, v1.1 and v1.2 kept for the record).
  v1.2 is the register layer (8 labels, 15 relationships); v1.3 adds the vision layer read from the P&IDs.
* Working rules and known-good answers: `CLAUDE.md`. Upgrade plan and what was built: `PIDKG_UPGRADE.md`
* Reasoning and decisions: `PID_GRAPH_DECISIONS.md` (sections 10 and 11 are the implementation decisions)
* Running log for cold pickup: `SESSION_LOG.md`

The earlier NetworkX prototype lives in `C:\Users\alanm\Documents\pid_graph` and is the
source of the table-reading code and the dummy documents used here.

## Run (one unit, dummy documents)

```bash
.venv\Scripts\python -m pid_graph.check_env
```

```bash
powershell -ExecutionPolicy Bypass -File scripts\setup_neo4j.ps1
```

```bash
.venv\Scripts\python -m pid_graph --unit U-100 --backend neo4j --pdf data\U100-PIDS-TX-0042.pdf --transmittal TX-0042
```

```bash
.venv\Scripts\python -m pid_graph.validate
```

```bash
.venv\Scripts\python -m pid_graph.queries out_of_service PT-1001A
```

```bash
.venv\Scripts\python -m pytest -q
```

## Vision layer (v1.3): segment topology read from the P&IDs

Vision proposes, the instrument index disposes, an engineer accepts. A third-party tool, pid-to-kg
(`THIRD_PARTY_NOTICES.md`), reads the drawings and writes a `graph.json`; pid_graph decides what is
allowed in. Every vision fact is loaded `review = pending` and stays invisible to the safety-relevant
templates, reports and summary until it is accepted in the review register.

```bash
.venv\Scripts\python -m pid_graph.load_pidkg --graph tests\fixtures\pidkg_U-100\graph.json --pdf data\U100-PIDS-TX-0057.pdf --transmittal TX-0057
```

is a dry run: it prints what would be loaded, the exceptions and the reconciliation checks, and writes nothing.

```bash
.venv\Scripts\python -m pid_graph --unit U-100 --backend neo4j --pdf data\U100-PIDS-TX-0057.pdf --transmittal TX-0057 --pidkg tests\fixtures\pidkg_U-100\graph.json
```

loads the registers and the vision layer, and writes into `reports\`: the exception register (now with
codes X21-X36), `review_register_U-100.xlsx`, `review_markup_U-100.pdf` and `summary_U-100.md`.
Without `--pidkg` the graph is v1.2, byte for byte.

To review: open `reports\review_markup_U-100.pdf` beside `reports\review_register_U-100.xlsx`; set
`review` to `accepted` or `rejected` and put your initials in `reviewer`; run the load again. A rejected
fact leaves the graph and stays in the register with your reason.

```bash
.venv\Scripts\python -m pid_graph.topology_queries isolation PT-1001A
```

```bash
.venv\Scripts\python -m pid_graph.topology_queries same_pressure PT-1001A --include-pending
```

```bash
.venv\Scripts\python -m pid_graph.topology_queries blast_radius XV-1001
```

```bash
.venv\Scripts\python -m pid_graph.topology_queries loop_membership PV-1005
```

```bash
.venv\Scripts\python -m pid_graph.topology_queries drawing_vs_ce
```

The first four use accepted facts only; `--include-pending` shows everything under an EXPLORATION ONLY header.

```bash
.venv\Scripts\python -m pid_graph.summary --unit U-100
```

```bash
.venv\Scripts\python -m eval.topology_eval --pidkg-eval
```

```bash
.venv\Scripts\python scripts\make_dummy_pdf.py --all
```

The last rebuilds the synthetic P&ID PDFs and their answer key. Extracting a drawing with pid-to-kg is
described in `tests\fixtures\pidkg_U-100\RUN.md`; for a plant with no index use
`load_pidkg --no-master --report-only` (`docs\STRESS_TEST.md`).

## Seeing the graph

```bash
.venv\Scripts\python -m pid_graph.explorer
```

writes `reports\explorer_U-100.html`, a self-contained interactive picture of the live graph (double-click to
open; no login). Neo4j Browser at http://localhost:7475 is the live alternative; set each label's caption to its
key property (tag, sif_id, alarm_id, line_no, doc_no) once, via the label pill above a result.

## Reports for engineers

```bash
.venv\Scripts\python -m pid_graph.report compensating-measures
```

```bash
.venv\Scripts\python -m pid_graph.report bypass XV-1001 --duration "8 h" --requester "Shift Supervisor" --reason "..."
```

```bash
.venv\Scripts\python -m pid_graph.oos add XV-1001 --kind bypass --hours 8 --by "Ops Superintendent" --reason "solenoid replacement"
```

```bash
.venv\Scripts\python -m pid_graph.oos close OOS-2026-001 --by "Shift Supervisor"
```

```bash
.venv\Scripts\python -m pid_graph.oos remove --all
```

```bash
.venv\Scripts\python -m pid_graph.report handover
```

```bash
.venv\Scripts\python -m pid_graph.report trip-pack SIF-100-02
```

All write Markdown and Word into `reports\`. The out-of-service register `data\oos\out_of_service_U-100.csv`
(active bypasses, MOS, shelved alarms) is applied to the graph with `oos apply` and every assessment then
considers the request combined with what is already out. Every fact carries its source document and revision; curated
measures carry the curator's initials and date; register exceptions appear as data caveats.

## Before the first real documents

Run the intake check on each new file before it goes through the pipeline. It reports which headers the
loaders recognise, which tags the canonical regex accepts, whether the PDF has a text layer, and which page
region yields drawing number + revision. Calibrate `loaders/tables.py` (aliases), `tags.py` (prefixes,
regex) and `loaders/titleblock.py` (DEFAULT_REGION) from that report.

```bash
.venv\Scripts\python -m pid_graph.intake path	o
eal-instrument-index.xlsx
```

`--backend memory` runs the whole pipeline against an in-memory store with Neo4j MERGE semantics
and writes `reports/graph_U-100.json`; `--backend neo4j` creates constraints, wipes the unit,
MERGEs, and reads back from the database for reconcile and eval. `--pdf` reads drawing revisions
from the per-unit P&ID PDF's title blocks and diffs them against the graph before loading.
Connection details come from `.env` (see `.env.example`). `scripts\setup_neo4j.ps1` creates or
starts pid_graph's own container, `neo4j-pidgraph` (bolt 7688, browser http://localhost:7475), from those details. It must not share a database with another project: Neo4j Community holds one database per container, and kg_suppression uses `neo4j-kg` on 7687.

## Pipeline

0. `loaders/titleblock.py` - P&ID PDF title blocks -> `Document` nodes with real revisions;
   re-issue diff (new / revised / unchanged / re-extract).
1. `loaders/index_loader.py` - instrument index xlsx -> `Instrument` nodes (master list),
   `MEASURES` / `INSTALLED_ON`, `SHOWN_ON`; Alarm Register sheet -> `Alarm` + `GENERATES`.
2. `loaders/ce_loader.py` - matrix C&E -> `SIF`, `INITIATES` (voting, setpoint), `ACTUATES` (action),
   `PROTECTS`, `RAISES` (alarm effects, resolved to the register alarm) and `CASCADES_TO` (SIF/ESD effects).
   `loaders/srs_loader.py` - SRS register -> requirements on `SIF` (sil_srs, setpoint_srs, safe state, PST,
   response time, PTI, bypass conditions ...). `loaders/lopa_loader.py` - LOPA register -> `Scenario`,
   `THREATENS`, `CREDITS` (IPLs with PFD; required RRF / SIL for the SIF).
3. `loaders/pid_loader.py` - pid_audit topology export -> `INSTALLED_ON`, `FEEDS`, `SHOWN_ON`;
   P&ID-only tags become stub Instruments; battery limits become stub Equipment.
4. `reconcile.py` - coverage per unit and the exception register
   `reports/exception_register_U-100.xlsx` (codes X1-X20, see module docstring).
5. `eval/score.py` + `eval/gold_PID-100-001.json` - node and edge precision/recall for one drawing.

Then: `validate.py` (structural checks + competency-question sketches on the live graph),
`queries.py` (fixed templates: `out_of_service`, `shelve_impact`, `moc_impact`, `trip`), and
`mcp_server.py`, which exposes those templates plus lookup and register tools to Claude Code as
read-only MCP tools. `.mcp.json` registers it for this folder; check with `/mcp` in a session, or run
`python tests/test_mcp_smoke.py` to exercise it over stdio without Claude.

Not yet: `VALID_IN` / `HAS_STATE` (need the suppression design). `COMPENSATES_FOR` is loaded only from approved rows of
`data/curated/compensating_measures_<unit>.csv` (D-P2-10).

## Layout

```
pid_graph/
  ontology.py      closed schema + validators (v1.3), trust rule T7
  tags.py          canonical tag regex, prefix classification
  records.py       MemoryStore (MERGE semantics, conflicts)
  neo4j_store.py   constraints, wipe-per-unit, batched MERGE, read-back
  db.py            driver from .env
  loaders/         tables.py, titleblock.py, docs.py, index_loader.py, ce_table.py, ce_loader.py,
                   srs_loader.py, lopa_loader.py, curated_loader.py, pid_loader.py
  reconcile.py     exception register (X1-X20; titles for X21-X36)
  load_pidkg.py    v1.3: pid-to-kg graph.json -> vision layer (dry run, --apply, --no-master --report-only)
  vision_checks.py v1.3: vision against index, C&E and pid_audit (X30-X36)
  review.py        v1.3: review register, priority flags, PDF markup
  topology_queries.py  v1.3: CQ14-CQ18 on Neo4j or the in-memory store
  summary.py       v1.3: plant summary from trusted facts
  queries.py       parameterised query templates + CLI (T7 filter)
  mcp_server.py    read-only MCP server over the templates (stdio)
  validate.py      structural checks + CQ sketches
  intake.py        readiness check for a new document (aliases, tag shapes, title-block region)
  explorer.py      self-contained HTML explorer of the graph
  report.py        CM register, bypass assessment, shift handover, trip investigation pack (md + docx)
  oos.py           live out-of-service register -> node properties; combined protection status
  pipeline.py      build_store()
  loaders/ (ops)   madb_loader.py, config_loader.py, silv_loader.py, moc_loader.py, docreg_loader.py (off by default)
  ops_checks.py    cross-document checks C1-C26 over the operations documents; MOC impact rules I1-I5
  demo.py          scenario demonstrator: python -m pid_graph.demo -> reports/demo_U-100.html
  demo_page.py     the page it writes (self-contained)
  situation.py     several things out of service at once: python -m pid_graph.situation PT-1001B XV-1001
  run_all.py       python -m pid_graph
eval/              gold sets + scorers (score.py for v1.2; topology_eval.py for the vision layer)
tests/             pytest; fixtures/ holds the frozen v1.2 dump and the frozen pid-to-kg extraction
scripts/           setup_neo4j.ps1, make_dummy_pdf.py, make_dummy_srs_lopa.py, make_pidkg_discrepancies.py
data/              sample unit documents (dummy, incl. drawn synthetic P&ID PDFs); data/external/ is git-ignored
docs/              V1_3_INVENTORY.md, STRESS_TEST.md, DEMO_GUIDE.md, BLIND_TEST.md
reports/           outputs (git-ignored, except review_register_<unit>.xlsx)
third_party/       pid-to-kg, cloned and unmodified (git-ignored; THIRD_PARTY_NOTICES.md)
```

## Scenario demonstrator

```bash
.venv\Scripts\python -m pid_graph.demo
```

Builds U-100 in memory from every document in `data\` (design documents plus the MADB, configuration export, SIL
verification, MOC register and document register) and writes `reports\demo_U-100.html`: pick a bypass, a shelved alarm,
a MOC, a SIF, a trip, a tag or a document and follow the answer step by step, with the documents behind each step.
No Neo4j needed. `docs\DEMO_GUIDE.md` is the presenter's guide. The test documents and their answer key come from
`scripts\make_dummy_batch1.py`.
