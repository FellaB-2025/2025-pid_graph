# pid_graph — v1 Ontology & Competency Questions

Design deliverable for the cross-document knowledge graph (P&ID + instrument
database + C&E). This document is the closed schema: if a node label or
relationship type isn't listed here, it doesn't go in the graph. Change the
schema by changing this document first.

---

## 1. Competency questions (the acceptance test)

The graph exists to answer these. Each is tagged with its retrieval
granularity. If a proposed schema change doesn't help answer one of these,
it's scope creep.

**CQ1 — Lookup** *(node)*
What is instrument X — type, service, range, setpoints — and which documents
show it, at which revision?

**CQ2 — Bypass compensating measures** *(subgraph)* — the flagship
If instrument X is bypassed or fails, which SIFs lose an initiator, what
protection do those SIFs provide, which sibling initiators remain, and which
alarms or states can serve as compensating measures?

**CQ3 — MOC impact** *(path, k≤3)*
If line/equipment X is modified, which instruments, SIFs, alarms, and
documents are affected?

**CQ4 — Alarm shelving impact** *(subgraph)*
If alarm X is shelved, what hazard indication is lost, and does any SIF or
other alarm still cover that scenario?

**CQ5 — Dynamic suppression design** *(subgraph)*
For equipment X, which alarms are only valid in which equipment states, and
what is the first-out grouping for its trip functions?

**CQ6 — Trip troubleshooting** *(path)*
SIF X tripped: which initiators can cause it, what does each measure, and
what does the SIF actuate?

**CQ7 — Cross-document consistency** *(node + provenance)*
Where do the P&ID, instrument database, and C&E disagree about instrument X?
(The TagSentry question — conflicts are findings, both facts stored.)

**CQ8 — Document scope** *(node)*
Which entities does document X (at revision Y) show — i.e. what must be
re-verified when it revises?

---

## 2. Node labels (7)

| Label | What it is | Key properties |
|---|---|---|
| `Instrument` | Any tagged device: transmitters, switches, valves, final elements | `tag` (canonical, unique), `type` (PT/TT/LT/XV/…), `service`, `range`, `units`, `io_type` |
| `Equipment` | Pumps, vessels, exchangers, compressors | `tag` (unique), `type`, `service` |
| `Line` | Process lines | `line_no` (canonical, unique), `size`, `spec`, `fluid` |
| `SIF` | Safety instrumented function | `sif_id` (unique), `sil`, `description`, `voting` (e.g. 2oo3) |
| `Alarm` | A configured alarm | `alarm_id` (unique: tag + alarm type, e.g. `PT-1001.PAHH`), `priority`, `setpoint`, `alarm_type` |
| `State` | An equipment/process state used in logic | `state_id` (unique, e.g. `P-101.RUNNING`), `description` |
| `Document` | A source document at a revision | `doc_no` + `rev` (unique together), `doc_type` (PID/CE/IDX), `title` |

Canonical key rule: full tag with unit prefix, one normalised format
(deterministic regex, per pid_audit), enforced with Neo4j uniqueness
constraints. `ProcessUnit` is a property (`unit`) on every node, not a label —
promote it to a node only if cross-unit traversal ever becomes a real CQ.

## 3. Relationship types (11, closed list)

Direction is part of the definition — never reversed, never synonymed.

| Relationship | Direction | Meaning | Primary source |
|---|---|---|---|
| `MEASURES` | Instrument → Line/Equipment | What the device senses | P&ID / index |
| `INSTALLED_ON` | Instrument → Line/Equipment | Physical location | P&ID |
| `FEEDS` | Line/Equipment → Line/Equipment | Process flow direction | P&ID |
| `INITIATES` | Instrument → SIF | Trip initiator | C&E |
| `ACTUATES` | SIF → Instrument | Final element action | C&E |
| `PROTECTS` | SIF → Equipment/Line | What the SIF safeguards | C&E / SRS |
| `GENERATES` | Instrument → Alarm | Device raises this alarm | Alarm list / DB |
| `VALID_IN` | Alarm → State | Alarm only meaningful in this state | Suppression design |
| `HAS_STATE` | Equipment → State | State belongs to equipment | Logic docs |
| `COMPENSATES_FOR` | Alarm → SIF | Curated compensating measure | Engineering judgement (manually curated, never LLM-extracted) |
| `SHOWN_ON` | any → Document | Provenance as a traversable edge | All |

## 4. Provenance (on every node and relationship)

Properties: `source_doc`, `source_rev`, `source_sheet`, `extracted_by`
(pid_audit / llm / manual), `load_run` (timestamp or run ID).
`SHOWN_ON` edges additionally make provenance traversable for CQ7/CQ8.
Conflict rule: when sources disagree, store both facts with both provenances —
never pick a winner at load time.

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
MATCH path = (x)-[:MEASURES|INSTALLED_ON|FEEDS|INITIATES|GENERATES*..3]-(affected)
RETURN DISTINCT labels(affected), affected.tag, length(path)
ORDER BY length(path)
```

Both traverse cleanly over the 11 relationships → schema passes. Do this
sketch for every CQ before freezing; a CQ you can't sketch means the ontology
isn't done.

## 6. Deliberately out of scope for v1

No procedures/work instructions, no maintenance history, no 3D/layout data,
no cross-unit topology, no historical revisions (current rev only —
supersession handling is a v2 decision), no PI/historian data. Each is a
future increment with its own competency questions and gold set — added when
a v1 CQ demands it, not before.
