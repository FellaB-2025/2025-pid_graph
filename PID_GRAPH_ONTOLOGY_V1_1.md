# pid_graph — v1.1 Ontology & Competency Questions

Supersedes `PID_GRAPH_ONTOLOGY_V1.md` (kept unchanged for the record). This document
is the closed schema: if a node label or relationship type isn't listed here, it
doesn't go in the graph. Change the schema by changing this document first.

## 0. Changes from v1 (9 Sep 2026)

Each change was forced by a competency question the v1 schema could not answer or by
a fact Phase 1/2 loading could not represent. Decisions D-P1-01, D-P1-06, D-P2-02 and
decisions section 6 are the sources.

| # | Change | Why |
|---|---|---|
| 1 | New relationship `RAISES` (SIF → Alarm) and new **CQ9** | C&E charts list alarm effects (e.g. `PAHH-1001 / Alarm`). v1 had no way to say "this trip announces itself"; the loader had to drop them (D-P2-02). |
| 2 | New relationship `CASCADES_TO` (SIF → SIF) and new **CQ10** | Unit-to-plant ESD hierarchies are SIF-to-SIF logic (decisions section 6). Added now so the loader is ready when a C&E shows it. |
| 3 | `extracted_by` gains the value `table` | Deterministic loads of tabular registers are neither pid_audit, llm nor manual (D-P1-01). |
| 4 | Relationship identity includes `source_doc` | An index claim and a drawing extraction of the same fact are two edges with two provenances (D-P1-06), which is what CQ7 needs. |
| 5 | `Document.doc_type` gains `CUR` | Curated registers (compensating measures) are controlled documents too (D-P2-10). |
| 6 | Stub convention written down | Nodes referenced but not yet loaded carry `stub: true` and `stub_unit` (decisions section 6). |

Relationship count: 11 → 13. Labels unchanged (7).

---

## 1. Competency questions (the acceptance test)

The graph exists to answer these. Each is tagged with its retrieval granularity. If a
proposed schema change doesn't help answer one of these, it's scope creep.

**CQ1 — Lookup** *(node)*
What is instrument X — type, service, range, setpoints — and which documents show it,
at which revision?

**CQ2 — Bypass compensating measures** *(subgraph)* — the flagship
If instrument X is bypassed or fails, which SIFs lose an initiator, what protection do
those SIFs provide, which sibling initiators remain, and which alarms or states can
serve as compensating measures?

**CQ3 — MOC impact** *(path, k≤3)*
If line/equipment X is modified, which instruments, SIFs, alarms, and documents are
affected?

**CQ4 — Alarm shelving impact** *(subgraph)*
If alarm X is shelved, what hazard indication is lost, and does any SIF or other alarm
still cover that scenario?

**CQ5 — Dynamic suppression design** *(subgraph)*
For equipment X, which alarms are only valid in which equipment states, and what is
the first-out grouping for its trip functions?

**CQ6 — Trip troubleshooting** *(path)*
SIF X tripped: which initiators can cause it, what does each measure, and what does
the SIF actuate?

**CQ7 — Cross-document consistency** *(node + provenance)*
Where do the P&ID, instrument database, and C&E disagree about instrument X?
(The TagSentry question — conflicts are findings, both facts stored.)

**CQ8 — Document scope** *(node)*
Which entities does document X (at revision Y) show — i.e. what must be re-verified
when it revises?

**CQ9 — Trip announcement** *(node)* — new in v1.1
When SIF X trips, which alarms announce it to the operator, and is any of those alarms
also relied on as a compensating measure for another SIF (so that shelving it hides a
trip)?

**CQ10 — Cascade** *(path)* — new in v1.1
If SIF/ESD level X activates, which other SIFs (and therefore which units and final
elements) trip as a consequence?

---

## 2. Node labels (7)

| Label | What it is | Key properties |
|---|---|---|
| `Instrument` | Any tagged device: transmitters, switches, valves, final elements | `tag` (canonical, unique), `type` (PT/TT/LT/XV/…), `service`, `range`, `units`, `io_type` |
| `Equipment` | Pumps, vessels, exchangers, compressors | `tag` (unique), `type`, `service` |
| `Line` | Process lines | `line_no` (canonical, unique), `size`, `spec`, `fluid` |
| `SIF` | Safety instrumented function | `sif_id` (unique), `sil`, `description`, `voting` (e.g. 2oo3), `logic_solver` |
| `Alarm` | A configured alarm | `alarm_id` (unique: source tag + alarm type, e.g. `PT-1001A.PAH`), `alarm_tag` (the register's own tag, e.g. `PAH-1001`), `priority`, `setpoint`, `alarm_type` |
| `State` | An equipment/process state used in logic | `state_id` (unique, e.g. `P-101.RUNNING`), `description` |
| `Document` | A source document at a revision | `doc_no` + `rev` (unique together; `doc_key = doc_no|rev` carries the constraint), `doc_type` (PID/CE/IDX/CUR), `title` |

Canonical key rule: full tag with unit prefix, one normalised format (deterministic
regex, per pid_audit), enforced with Neo4j uniqueness constraints. `ProcessUnit` is a
property (`unit`) on every node, not a label — promote it to a node only if cross-unit
traversal ever becomes a real CQ.

Stub convention: a node that a document references but whose owning source has not
loaded (battery limits, tags only seen on a drawing, drawings whose title block has not
been read, alarms only named by a C&E) is created with `stub: true` and `stub_unit` =
the loading unit, so edges have endpoints and the gap is visible. The owning source's
load clears the flag by MERGE on the same key.

## 3. Relationship types (13, closed list)

Direction is part of the definition — never reversed, never synonymed. Relationship
identity is (type, start, end, `source_doc`): the same fact witnessed by two documents
is two parallel edges, each with its own provenance.

| Relationship | Direction | Meaning | Primary source |
|---|---|---|---|
| `MEASURES` | Instrument → Line/Equipment | What the device senses | P&ID / index |
| `INSTALLED_ON` | Instrument → Line/Equipment | Physical location | P&ID |
| `FEEDS` | Line/Equipment → Line/Equipment | Process flow direction | P&ID |
| `INITIATES` | Instrument → SIF | Trip initiator (`voting`, `setpoint` on the edge, per cause group) | C&E |
| `ACTUATES` | SIF → Instrument | Final element action (`action`) | C&E |
| `PROTECTS` | SIF → Equipment/Line | What the SIF safeguards | C&E / SRS |
| `RAISES` | SIF → Alarm | The trip announces itself through this alarm | C&E (alarm effect columns) |
| `CASCADES_TO` | SIF → SIF | Activation of the first initiates the second (ESD hierarchy) | C&E / SIS logic |
| `GENERATES` | Instrument → Alarm | Device raises this alarm | Alarm list / DB |
| `VALID_IN` | Alarm → State | Alarm only meaningful in this state | Suppression design |
| `HAS_STATE` | Equipment → State | State belongs to equipment | Logic docs |
| `COMPENSATES_FOR` | Alarm → SIF | Curated compensating measure (`rank`, `basis`, `conditions`, `curated_by`) | Engineering judgement (manually curated, never LLM-extracted) |
| `SHOWN_ON` | any → Document | Provenance as a traversable edge | All |

## 4. Provenance (on every node and relationship)

Properties: `source_doc`, `source_rev`, `source_sheet`, `extracted_by`
(`pid_audit` / `llm` / `manual` / `table`), `load_run` (transmittal-prefixed run id),
`source_ref` (file:sheet:row or file:page).
`SHOWN_ON` edges additionally make provenance traversable for CQ7/CQ8.
Conflict rule: when sources disagree, store both facts with both provenances —
never pick a winner at load time. For properties this is a recorded conflict (register
X6); for relationships it is two parallel edges.

## 5. Answerability check (schema sign-off)

CQ2 sketch — the one the schema must earn:

```cypher
MATCH (i:Instrument {tag: $tag})-[:INITIATES]->(s:SIF)
OPTIONAL MATCH (sib:Instrument)-[:INITIATES]->(s) WHERE sib.tag <> $tag
OPTIONAL MATCH (s)-[:PROTECTS]->(p)
OPTIONAL MATCH (c:Alarm)-[:COMPENSATES_FOR]->(s)
RETURN s.sif_id, s.sil, s.voting,
       collect(DISTINCT sib.tag)  AS remaining_initiators,
       collect(DISTINCT p.tag)    AS protects,
       collect(DISTINCT c.alarm_id) AS compensating_alarms
```

CQ3 sketch:

```cypher
MATCH (x {tag: $tag})
MATCH path = (x)-[:MEASURES|INSTALLED_ON|FEEDS|INITIATES|ACTUATES|GENERATES*..3]-(affected)
RETURN DISTINCT labels(affected), affected.tag, length(path)
ORDER BY length(path)
```

CQ9 sketch (new):

```cypher
MATCH (s:SIF {sif_id: $sif})-[:RAISES]->(a:Alarm)
OPTIONAL MATCH (a)-[:COMPENSATES_FOR]->(other:SIF)
RETURN a.alarm_id, a.alarm_tag, collect(DISTINCT other.sif_id) AS also_compensates_for
```

CQ10 sketch (new):

```cypher
MATCH p = (root:SIF {sif_id: $sif})-[:CASCADES_TO*1..5]->(s:SIF)
OPTIONAL MATCH (s)-[:ACTUATES]->(fe:Instrument)
RETURN s.sif_id, s.unit, length(p) AS depth, collect(DISTINCT fe.tag) AS final_elements
ORDER BY depth
```

CQ1, CQ3, CQ6, CQ7, CQ8 have been run against the loaded U-100 graph
(`pid_graph/validate.py`); CQ4/CQ5 wait for a suppression design; CQ9/CQ10 are sketched
here and wired into the validator.

## 6. Deliberately out of scope for v1.1

No procedures/work instructions, no maintenance history, no 3D/layout data,
no cross-unit topology beyond FEEDS edges and CASCADES_TO, no historical revisions
(current rev only — supersession handling is a v2 decision), no PI/historian data,
no logic-solver node (kept as `SIF.logic_solver` until a CQ needs solver-level
traversal). Each is a future increment with its own competency questions and gold
set — added when a CQ demands it, not before.
