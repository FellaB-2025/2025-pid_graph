# pid_graph (Neo4j, v1 ontology)

Cross-document knowledge graph for the functional-safety layer of a process unit:
instrument index + P&IDs + C&E, on Neo4j, with a closed schema.

* Schema: `PID_GRAPH_ONTOLOGY_V1_2.md` (8 labels, 15 relationships, provenance on everything; v1 and v1.1 kept for the record)
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
  ontology.py      closed schema + validators
  tags.py          canonical tag regex, prefix classification
  records.py       MemoryStore (MERGE semantics, conflicts)
  neo4j_store.py   constraints, wipe-per-unit, batched MERGE, read-back
  db.py            driver from .env
  loaders/         tables.py, titleblock.py, docs.py, index_loader.py, ce_table.py, ce_loader.py,
                   srs_loader.py, lopa_loader.py, curated_loader.py, pid_loader.py
  reconcile.py     exception register
  queries.py       parameterised query templates + CLI
  mcp_server.py    read-only MCP server over the templates (stdio)
  validate.py      structural checks + CQ sketches
  intake.py        readiness check for a new document (aliases, tag shapes, title-block region)
  explorer.py      self-contained HTML explorer of the graph
  report.py        CM register, bypass assessment, shift handover, trip investigation pack (md + docx)
  oos.py           live out-of-service register -> node properties; combined protection status
  pipeline.py      build_store()
  run_all.py       python -m pid_graph
eval/              gold set + scorer
tests/             pytest (Phase 1 and Phase 2)
scripts/           setup_neo4j.ps1, make_dummy_pdf.py, make_dummy_srs_lopa.py
data/              sample unit documents (dummy, incl. synthetic P&ID PDFs)
reports/           outputs (git-ignored)
```
