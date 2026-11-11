# pid_graph — v1.3 Ontology & Competency Questions

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Supersedes `PID_GRAPH_ONTOLOGY_V1_2.md`, `PID_GRAPH_ONTOLOGY_V1_1.md` and `PID_GRAPH_ONTOLOGY_V1.md` (all kept for the record). This document
is the closed schema: if a node label or relationship type isn't listed here, it
doesn't go in the graph. Change the schema by changing this document first.

## 0b. Changes from v1.2 (10 Nov 2026): segment topology from vision extraction

v1.3 is v1.2 plus the items below (`PIDKG_UPGRADE.md` section 2). It is **additive only**: no v1.2 label,
relationship, property or key is removed, renamed or changes meaning. The new facts come from one new loader
source, the third-party tool `pid-to-kg`, which reads the drawings with vision. pid_graph decides what is
allowed into the graph: **vision proposes, the instrument index disposes, an engineer accepts.**

| # | Change | Why |
|---|---|---|
| 12 | New label `Segment` (a stretch of one Line between two in-line items) | Line-level topology cannot say where on a line an instrument taps or which valves isolate it. CQ14, CQ15, CQ16. |
| 13 | New label `InlineItem` (an **untagged** in-line valve or fitting) | Untagged check valves, reducers, manual valves, strainers and blinds matter for isolation and have no index row. CQ14. |
| 14 | New label `ControlLoop` (a loop grouped from ISA tag numbers and drawn signal lines) | Loop membership as drawn, to compare with the index `loop` column (D-P1-09 kept the loop number as a property until a label was needed). CQ17. |
| 15 | New relationship `SEGMENT_OF` (Segment → Line) | Joins segment topology to the v1.2 Line node. |
| 16 | New relationship `FLOWS_TO` (Segment / Equipment / Instrument / InlineItem → same set) | Process flow at segment level, with `flow_direction` stated as `shown` or `inferred`. CQ14–CQ16. |
| 17 | New relationship `SIGNAL_TO` (Instrument → Instrument / Equipment) | Drawn signal lines. A drawn trip signal is a **cross-check** against the C&E, never a source of `INITIATES` / `ACTUATES`. CQ18. |
| 18 | New relationship `MEMBER_OF` (Instrument → ControlLoop) | Loop membership with a `role`. CQ17. |
| 19 | `MEASURES` and `INSTALLED_ON` may also end on a `Segment` | The index-sourced Line / Equipment relationship stays; the Segment relationship is added beside it with its own provenance. |
| 20 | `extracted_by` gains the value `pidkg_vision` | Everything the new loader writes. |
| 21 | New property `review` (`pending` / `accepted` / `rejected`) | Every `pidkg_vision` fact is written `pending`. Safety-relevant templates read only accepted or non-vision facts (trust rule T7). |
| 22 | New properties `confidence` (carried through from pid-to-kg) and `dexpiClass` (Equipment / Instrument / InlineItem; standalone, informative only) | |

Labels 8 → 11; relationships 15 → 19. None of the new names clashes with a v1.2 name. pid-to-kg's own
`CASCADES_TO`, `ACTUATES`, `TRIPS` and state-like items are **not** mapped onto this schema: `CASCADES_TO`,
`ACTUATES`, `HAS_STATE` and `State` keep their v1.2 meaning and their v1.2 sources.

Rules that come with the new labels:

- A **tagged** valve stays an `Instrument` (the index is master). It is not duplicated as an `InlineItem`.
- `InlineItem` is the one place a node may exist without an index row, because it has no tag to index. It
  carries `indexed = false`, and it can never be the start or end of `INITIATES`, `ACTUATES`, `PROTECTS`,
  `CREDITS`, `COMPENSATES_FOR` or `GENERATES`. The validator refuses it.
- Off-page connectors are **not** nodes. A paired connector becomes one `FLOWS_TO` with `off_page = true`. An
  unpaired one is an exception.
- Battery limits and headers stay `Equipment` as in v1.2 (`BL-100`, `FLARE-HDR`).
- `FEEDS` is unchanged (Line / Equipment → Line / Equipment). A derived `FEEDS` set computed by walking
  `FLOWS_TO` (`derived = true`, `via_lines`) is compared with the v1.2 `FEEDS`; disagreement is a conflict,
  never a silent overwrite.

**CQ14 — Isolation** *(path)* — new in v1.3
Which valves (tagged or not) sit between instrument X's tap and the next equipment, each way?

**CQ15 — Same-pressure-system candidates** *(subgraph)* — new in v1.3
Which other instruments sense a segment reachable from sensor X without crossing a closed-in-normal-operation
or actuated valve? (Feeds the compensating-measure *candidate* list. Curation stays manual; this never writes
`COMPENSATES_FOR`.)

**CQ16 — MOC blast radius** *(path)* — new in v1.3
Everything downstream of valve or segment X up to the next equipment, and every loop and SIF that touches it.

**CQ17 — Loop membership** *(node + path)* — new in v1.3
For final element X: its loop, its sensor, and the segment the sensor measures.

**CQ18 — Drawing vs C&E** *(node + provenance)* — new in v1.3
Every drawn `purpose = trip` signal with no matching `INITIATES` / `ACTUATES`, and every C&E cause / effect
with no drawn trip signal.

### As built (v1.3.0, 10 Nov 2026)

Where the loader (`pid_graph/load_pidkg.py`) had to settle something the table above leaves open:

- **Properties on vision facts**, beside the provenance set: `review`, `confidence`, and `fact_id`, a stable hash of
  type + endpoints + drawing that the review register matches on. `SIGNAL_TO` may carry `via` and `via_name`: an
  interlock symbol on the drawing (not an indexed device, so not a node) is collapsed into direct
  initiator → final element trip signals that name the symbol they passed through.
- **`dexpiClass`** is on every `InlineItem` and on the `Equipment` / `Instrument` nodes vision saw, with
  `dexpiClass_source`. It is the only thing the vision loader adds to a v1.2 node.
- **Segment numbering:** `<line_no>.<k>` with `k` running 1..n over the sheets the line is drawn on. A line with no
  number gets no `Segment`, because `line_no` is required; the `<doc_no>.<local>.<k>` form is not used.
- **`ControlLoop.loop_key`** is the first letter and the number (`P-1005`). The index loop number (`PIC-1005`) stays a
  property of the instrument; the two are compared, not merged.
- **`MEMBER_OF.role`** maps the tool's `transmitter` / `element` / `switch` to `sensor`; a gauge or indicator has no
  role in the closed list and is not a member.
- **Derived `FEEDS`** (equipment to equipment, by walking `FLOWS_TO`) are computed and reported, never written: a
  direct equipment-to-equipment `FEEDS` would change what "within two `FEEDS` hops" means in the v1.2 templates.
- **Existing nodes get no vision `SHOWN_ON`.** Relationship identity is (type, start, end, `source_doc`), so it
  would merge into pid_audit's for the same drawing.
- **Trust rule T7** has one definition, `ontology.trusted()`: `extracted_by` in `table`, `manual`, `pid_audit`, or
  `review = accepted`. Every safety-relevant template, report, summary and the explorer read through it.
- **Exception codes** X21–X29 (loader) and X30–X36 (vision against the registers) join X1–X20 in one register;
  titles are in `reconcile.TITLES`.

## 0a. Changes from v1.1 (9 Sep 2026): SRS and LOPA

Forced by three competency questions the safety documents answer and nothing else does.

| # | Change | Why |
|---|---|---|
| 7 | New label `Scenario` (LOPA hazard scenario) | LOPA is organised by scenario, not by SIF: initiating event, consequence, tolerable frequency, and the layers credited against it. CQ11. |
| 8 | New relationship `CREDITS` (Scenario → SIF / Alarm / Instrument) with `ipl_type`, `pfd`, `required_rrf`, `required_sil` | Which independent protection layers a scenario relies on, and what it demands of the SIF. CQ11, CQ12. |
| 9 | New relationship `THREATENS` (Scenario → Equipment / Line) | What the scenario endangers; joins LOPA to the plant. |
| 10 | SRS requirements as properties on `SIF` (`sil_srs`, `rrf_target`, `pfd_target`, `demand_mode`, `safe_state`, `process_safety_time`, `response_time`, `setpoint_srs`, `sensor_architecture`, `fe_architecture`, `proof_test_interval`, `bypass_conditions`, `manual_shutdown`, `reset`, `hazard`, `functional_description`) witnessed by `SHOWN_ON` → Document(SRS) | The SRS is the design requirement the C&E must honour. Kept as separate, source-named properties so the C&E's `sil`/setpoint and the SRS's stay side by side (conflict rule). CQ12, CQ13. |
| 11 | `Document.doc_type` gains `SRS` and `LOPA` | |

Labels 7 → 8; relationships 13 → 15.

**CQ11 — IPL independence** *(subgraph)* — new in v1.2
For hazard scenario X, which protection layers does the LOPA credit, and are they independent of each
other in the graph: does a credited alarm derive from a sensor that initiates the credited SIF, do two
credited layers share a sensor, final element or logic solver, is every credited layer actually in the
registers?

**CQ12 — SIL consistency** *(node + provenance)* — new in v1.2
For SIF X, do the LOPA-required SIL, the SRS SIL target and the C&E SIL agree? Where they differ, which
document says what?

**CQ13 — SRS conformance** *(node)* — new in v1.2
What does the SRS require of SIF X (safe state, process safety time, response time, trip setpoint,
sensor and final-element architecture, proof-test interval, bypass conditions), and does the as-built
C&E honour the setpoint and architecture?

CQ11 sketch:

```cypher
MATCH (sc:Scenario {scenario_id: $scenario})-[c:CREDITS]->(ipl)
OPTIONAL MATCH (ipl)<-[:GENERATES]-(src:Instrument)-[:INITIATES]->(s:SIF)<-[:CREDITS]-(sc)
RETURN labels(ipl)[0] AS layer, coalesce(ipl.sif_id, ipl.alarm_id, ipl.tag) AS id, c.ipl_type, c.pfd,
       coalesce(ipl.stub, false) AS not_in_registers,
       collect(DISTINCT src.tag + ' also initiates ' + s.sif_id) AS shares_sensor_with_credited_sif
```

CQ12 sketch:

```cypher
MATCH (s:SIF) OPTIONAL MATCH (sc:Scenario)-[c:CREDITS]->(s)
RETURN s.sif_id, s.sil AS sil_ce, s.sil_srs, collect(DISTINCT c.required_sil) AS sil_lopa
```

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

## 2. Node labels (11)

| Label | What it is | Key properties |
|---|---|---|
| `Instrument` | Any tagged device: transmitters, switches, valves, final elements | `tag` (canonical, unique), `type` (PT/TT/LT/XV/…), `service`, `range`, `units`, `io_type` |
| `Equipment` | Pumps, vessels, exchangers, compressors | `tag` (unique), `type`, `service` |
| `Line` | Process lines | `line_no` (canonical, unique), `size`, `spec`, `fluid` |
| `SIF` | Safety instrumented function | `sif_id` (unique), `sil`, `description`, `voting` (e.g. 2oo3), `logic_solver` |
| `Alarm` | A configured alarm | `alarm_id` (unique: source tag + alarm type, e.g. `PT-1001A.PAH`), `alarm_tag` (the register's own tag, e.g. `PAH-1001`), `priority`, `setpoint`, `alarm_type` |
| `State` | An equipment/process state used in logic | `state_id` (unique, e.g. `P-101.RUNNING`), `description` |
| `Document` | A source document at a revision | `doc_no` + `rev` (unique together; `doc_key = doc_no|rev` carries the constraint), `doc_type` (PID/CE/IDX/CUR/SRS/LOPA), `title` |
| `Scenario` | A LOPA hazard scenario | `scenario_id` (unique), `initiating_event`, `ie_frequency`, `consequence`, `severity`, `tolerable_frequency`, `conditional_modifiers`, `required_rrf`, `required_sil` |
| `Segment` | A stretch of one Line between two in-line items (v1.3) | `segment_id` (unique: `<line_no>.<k>`, or `<doc_no>.<local>.<k>` when the line has no number); required `line_no`, `size`, `service`, `review` |
| `InlineItem` | An **untagged** in-line valve or fitting: check valve, reducer, untagged manual valve, strainer, blind (v1.3) | `item_id` (unique: `<doc_no>.<local>`); required `kind`, `normal_position`, `indexed = false`, `review`; optional `dexpiClass` |
| `ControlLoop` | A loop grouped from ISA tag numbers and drawn signal lines (v1.3) | `loop_key` (unique, e.g. `P-1005`); required `loop_type`, `variable`, `review` |

Canonical key rule: full tag with unit prefix, one normalised format (deterministic
regex, per pid_audit), enforced with Neo4j uniqueness constraints. `ProcessUnit` is a
property (`unit`) on every node, not a label — promote it to a node only if cross-unit
traversal ever becomes a real CQ.

Stub convention: a node that a document references but whose owning source has not
loaded (battery limits, tags only seen on a drawing, drawings whose title block has not
been read, alarms only named by a C&E) is created with `stub: true` and `stub_unit` =
the loading unit, so edges have endpoints and the gap is visible. The owning source's
load clears the flag by MERGE on the same key.

## 3. Relationship types (19, closed list)

Direction is part of the definition — never reversed, never synonymed. Relationship
identity is (type, start, end, `source_doc`): the same fact witnessed by two documents
is two parallel edges, each with its own provenance.

| Relationship | Direction | Meaning | Primary source |
|---|---|---|---|
| `MEASURES` | Instrument → Line/Equipment/Segment | What the device senses (Segment: v1.3, beside the Line / Equipment relationship) | P&ID / index / vision |
| `INSTALLED_ON` | Instrument → Line/Equipment/Segment | Physical location (Segment: v1.3) | P&ID / vision |
| `FEEDS` | Line/Equipment → Line/Equipment | Process flow direction | P&ID |
| `INITIATES` | Instrument → SIF | Trip initiator (`voting`, `setpoint` on the edge, per cause group) | C&E |
| `ACTUATES` | SIF → Instrument | Final element action (`action`) | C&E |
| `PROTECTS` | SIF → Equipment/Line | What the SIF safeguards | C&E / SRS |
| `RAISES` | SIF → Alarm | The trip announces itself through this alarm | C&E (alarm effect columns) |
| `CASCADES_TO` | SIF → SIF | Activation of the first initiates the second (ESD hierarchy) | C&E / SIS logic |
| `GENERATES` | Instrument → Alarm | Device raises this alarm | Alarm list / DB |
| `VALID_IN` | Alarm → State | Alarm only meaningful in this state | Suppression design |
| `HAS_STATE` | Equipment → State | State belongs to equipment | Logic docs |
| `CREDITS` | Scenario → SIF / Alarm / Instrument | LOPA credits this layer against the scenario (`ipl_type`, `pfd`; for the SIF also `required_rrf`, `required_sil`) | LOPA |
| `THREATENS` | Scenario → Equipment / Line | What the scenario endangers | LOPA |
| `COMPENSATES_FOR` | Alarm → SIF | Curated compensating measure (`rank`, `basis`, `conditions`, `curated_by`) | Engineering judgement (manually curated, never LLM-extracted) |
| `SHOWN_ON` | any → Document | Provenance as a traversable edge | All |
| `SEGMENT_OF` | Segment → Line | The segment is a stretch of this line (v1.3) | Vision |
| `FLOWS_TO` | Segment / Equipment / Instrument (in-line or valve) / InlineItem → same set | Process flow at segment level (`flow_direction` = `shown` / `inferred`, `off_page`, `confidence`, `review`) (v1.3) | Vision |
| `SIGNAL_TO` | Instrument → Instrument / Equipment | A drawn signal line (`signal_type`, `purpose` = `control` / `measurement` / `trip` / `alarm` / `status` / `unknown`, `confidence`, `review`) (v1.3) | Vision |
| `MEMBER_OF` | Instrument → ControlLoop | Loop membership (`role` = `sensor` / `controller` / `relay` / `final_element`) (v1.3) | Vision |

An `InlineItem` can never start or end `INITIATES`, `ACTUATES`, `PROTECTS`, `CREDITS`, `COMPENSATES_FOR` or
`GENERATES`.

## 4. Provenance (on every node and relationship)

Properties: `source_doc`, `source_rev`, `source_sheet`, `extracted_by`
(`pid_audit` / `llm` / `manual` / `table` / `pidkg_vision`), `load_run` (transmittal-prefixed run id),
`source_ref` (file:sheet:row or file:page; for `pidkg_vision`, `<pdf>:p<page>:bbox=<x0,y0,x1,y1>`).
v1.3: every `pidkg_vision` fact also carries `review` (`pending` / `accepted` / `rejected`, default `pending`)
and the `confidence` pid-to-kg gave it, unchanged. A `rejected` fact stays in the review register and is
removed from the graph on the next load.
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
here and wired into the validator. CQ14–CQ18 (v1.3) have fixed templates in `pid_graph/topology_queries.py`
(`isolation`, `same_pressure`, `blast_radius`, `loop_membership`, `drawing_vs_ce`), on Neo4j and on the in-memory
store, verified to agree on U-100. CQ14–CQ17 use accepted facts only, so they answer nothing until the segment
topology has been reviewed; CQ18 is a consistency check and reads pending facts, saying so.

## 6. Deliberately out of scope

No procedures/work instructions, no maintenance history, no 3D/layout data,
no cross-unit topology beyond FEEDS edges and CASCADES_TO, no historical revisions
(current rev only — supersession handling is a v2 decision), no PI/historian data,
no logic-solver node (kept as `SIF.logic_solver` until a CQ needs solver-level
traversal). v1.3 adds: no off-page connector nodes, no pid-to-kg derived trip or actuation logic, no
reference-data anchoring (`dexpiClass` is a standalone, informative property). Each is a future increment with its own competency questions and gold
set — added when a CQ demands it, not before.
