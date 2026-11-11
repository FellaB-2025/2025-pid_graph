# pid_graph — Structuring Decisions & Q&A Reference

Companion to `PID_GRAPH_ONTOLOGY_V1.md`. Captures the planning discussion
(Sep 2026) on structure, scale, cross-unit handling, and ingest. Ontology doc
holds the schema; this holds the reasoning.

---

## 1. What is a node?

**The graph models the plant, not the documents.** A node is a thing that
exists in the plant — instrument, line, equipment, SIF, alarm, state.
Documents are witnesses that testify about those things, not the structure
itself.

- A tag mentioned in the index, three P&IDs, and a C&E is **one node** with
  four provenance references — always. Nodes-per-document-mention is the
  fragmentation trap.
- Documents are also nodes, but only for provenance and traceability
  (`SHOWN_ON` edges), never as the organising structure.

## 2. Completeness at scale (300+ P&IDs, 100+ C&Es)

Completeness is measured, not hoped for:

- The **instrument index is the master node list** — it's already a table, so
  it loads deterministically (no LLM) and defines the expected population.
- Everything else reconciles against it: every index tag should appear on at
  least one P&ID; every C&E initiator/final element should match an index tag.
- Mismatches go to an **exception register** (TagSentry logic promoted to
  gatekeeper), never silently into the graph.
- Coverage is a percentage per unit, reported per load run.
- Scale approach: **one process unit end-to-end first** (index + P&IDs only,
  gold set, reconciliation report), then repeat the proven pipeline. The
  reconciliation report is valuable to the project before the graph answers a
  single question — and is the opening slide of the management proposal.

## 3. Is this the book's GraphRAG?

Yes — a self-constructed KG (construction pipeline) with graph-guided
retrieval feeding an LLM (G-indexing → G-retrieval → G-generation). With one
split:

- **Operating procedures stay out of the graph.** They're prose — chunk them
  into ChromaDB and link via Document nodes. Graph for structure, vectors for
  text: the HybridRAG pattern. Don't triplet-ize paragraphs.

## 4. Querying: fixed task templates first, NLP second

- Build **parameterized, tested Cypher templates** where only the tag
  changes: `moc_impact(tag)`, `out_of_service(tag)`, `shelve_impact(alarm_id)`.
  Deterministic retrieval, verified once, reused forever.
- Free-form NLP-to-Cypher sits on top for ad-hoc exploration only — never for
  safety-relevant answers.

**The unifying frame:** shelved alarm, bypassed SIF, interlock bypass, and
MOS (maintenance override switch) are all the **same question** — "this
element is out of service; what protection is lost, what remains, what
compensates?" A MOS is a bypass applied to an initiator; shelving takes an
Alarm node out of service; an interlock bypass takes a SIF out. One query
family, parameterized by node and type.

## 5. Retrieval granularity by task

| Task | Granularity |
|---|---|
| Instrument lookup (CQ1) | Node |
| MOC impact (CQ3), trip troubleshooting (CQ6) | Path, k ≤ 3 hops |
| Bypass compensating measures (CQ2), shelving impact (CQ4), suppression design (CQ5) | Subgraph |

Safety-critical queries always via fixed templates (see §4).

## 6. Cross-unit impacts

**Unit is a loading boundary, never a graph boundary.** Edges cross units
freely — a FEEDS edge from a Unit 100 line to a Unit 200 exchanger is just an
edge, and path queries traverse it with no special handling.

- **Stub nodes:** loading Unit 100 first, off-page/battery-limit references
  to unloaded units MERGE as stubs (tag + `stub: true`). When the far unit's
  index loads, the same MERGE-on-tag fills the properties and clears the
  flag. Remaining-stub count = free load-progress metric (zero stubs = every
  referenced tag fully loaded).
- **Wipe-per-unit stays safe** via provenance: each edge belongs to the
  document that evidences it, so cross-unit edges are recreated when their
  owning unit's documents reload.
- **Cascading trips (planned schema amendment):** unit-to-plant ESD
  hierarchies are SIF-to-SIF logic the v1 relationships can't express. When
  the C&Es show it, amend the ontology doc first: add
  `(SIF)-[:CASCADES_TO]->(SIF)` plus a new competency question — "if ESD-1
  activates, which units and SIFs trip?"
- **Flare/utilities/common systems:** own `unit` value, loaded as a unit of
  their own — they're the biggest cross-unit connectors.

## 7. Ingesting the Aconex per-unit PDFs

Ingest the combined per-unit PDF exactly as the EPC delivers it — no
splitting. PyMuPDF handles large multi-page files; one file per unit = one
loader run.

Non-negotiable inside that: **the page is not the document; the drawing is.**
- The loader reads the title block of every page (deterministic regex,
  pid_audit-style coordinates) and records provenance as **drawing number +
  rev + sheet**, never "Unit100.pdf page 37" — page numbers shift between
  issues; drawing numbers don't.
- **Free change detection:** on re-issue, run the title-block pass on the new
  PDF, diff revisions per drawing against the graph, re-extract only the
  sheets that revised. Update loop solved at file level.
- **Check early** that the PDFs are native vector output with a text layer —
  a scanned/flattened set would gut extraction. Test one file first.
- Stamp the **Aconex transmittal number/date into `load_run`** so every fact
  traces to a controlled document issue.

## 8. Claude Code Phase 1 starting prompt

Run in the pid_graph folder with `PID_GRAPH_ONTOLOGY_V1.md` present:

```
Read PID_GRAPH_ONTOLOGY_V1.md — it is the closed schema; never
create labels or relationships not listed in it.

Build Phase 1 of pid_graph, one process unit only:
1. loaders/index_loader.py — parse the instrument index (xlsx)
   into Instrument nodes. Deterministic, no LLM. Canonical tag
   normalisation via regex. MERGE on tag, provenance properties
   on every node (source_doc, source_rev, extracted_by, load_run).
2. loaders/pid_loader.py — consume pid_audit's extraction output
   to create MEASURES / INSTALLED_ON edges and SHOWN_ON edges.
3. reconcile.py — coverage report: index tags missing from P&IDs,
   P&ID tags missing from index, C&E tags matching neither.
   Output an Excel exception register.
4. eval/ — gold set for one P&ID sheet; score node and edge
   precision/recall separately.
Neo4j on bolt://localhost:7687. Full-rebuild loads (wipe unit,
reload). Stop after Phase 1 — no C&E parsing, no query layer yet.
```

## 9. Open items

- Sketch the remaining competency questions (CQ4–CQ8) in Cypher before
  freezing the schema.
- Review the three flagged design calls: COMPENSATES_FOR curated-only;
  unit-as-property; conflicts stored, never resolved at load.
- Verify one Aconex PDF has a usable text layer.
- Add `CASCADES_TO` + its competency question when C&E evidence appears.

## 10. Phase 1 implementation decisions (Claude Code, 8 Sep 2026)

Made while building Phase 1 against the dummy U-100 documents. Each is reversible; none
changes the ontology.

- **D-P1-01 `extracted_by = table`.** The ontology lists pid_audit / llm / manual. Deterministic
  loads of tabular registers (instrument index, alarm register) are none of these, so a fourth
  value `table` is used. Ontology section 4 should list it when next revised.
- **D-P1-02 Provisional tag regex.** `[unit-]FUNC-NUMBER[SUFFIX]` (`pid_graph/tags.py`), tolerant
  of missing hyphen, spaces and underscores. pid_audit's own rule is not on this machine; swap it
  in when available and re-run the tests.
- **D-P1-03 `rev = UNKNOWN` for referenced drawings.** The index's "P&ID No." column and the
  pid_audit export name drawings without a revision. They get a `Document {doc_no, rev: UNKNOWN,
  stub: true}` node and an X7 exception. The Aconex title-block pass (decisions section 7) will
  re-key them.
- **D-P1-04 Document uniqueness via `doc_key`.** Composite uniqueness constraints are not
  available on Neo4j Community, so `Document.doc_key = doc_no + '|' + rev` carries the uniqueness
  constraint; `doc_no` and `rev` are indexed.
- **D-P1-05 Index location column -> MEASURES for sensors, INSTALLED_ON for valves.** The "Line /
  Equipment No." column is what a sensor measures and where a valve sits. The rule is by tag
  role (prefix), deterministic.
- **D-P1-06 Edge identity includes `source_doc`.** MERGE on `(a)-[:TYPE {source_doc}]->(b)`. An
  index claim and a drawing extraction of the same fact are two parallel edges with two
  provenances (ontology conflict rule; decisions section 6 "each edge belongs to the document
  that evidences it"). Reconcile and CQ7 compare witnesses; nothing is lost at load.
- **D-P1-07 P&ID-only instruments are stub nodes AND exceptions.** They enter the graph flagged
  `stub: true` so topology edges have endpoints, and appear as X2 in the register - visible, not
  silent. Alarm Register rows whose source tag is not in the index are skipped, not stubbed.
- **D-P1-08 Alarm identity.** `alarm_id = <source tag>.<alarm function>` (e.g. `PT-1001A.PAH`);
  the register's own alarm tag (`PAH-1001`) is kept as `alarm_tag`. The register's "Protected
  Equipment" column is not loaded (no Alarm -> Equipment relationship in v1).
- **D-P1-09 Loop Register not loaded.** No `Loop` label in v1; the index's loop number is kept as
  an Instrument property `loop` so nothing is lost if a Loop label is ever added.
- **D-P1-10 C&E read for tags only.** Phase 1 does not load the C&E (section 8), but reconcile
  reads its cause/effect tags to populate X4.

## 11. Phase 2 implementation decisions (Claude Code, 9 Sep 2026)

- **D-P2-01 Load order.** P&ID title blocks (drawing revisions) -> instrument index -> C&E -> P&ID
  topology. The title-block pass runs first so every later reference to a drawing carries its real
  revision; `rev: UNKNOWN` (D-P1-03) now only appears when no PDF was supplied.
- **D-P2-02 C&E alarm effects are not loaded.** A C&E column such as `PAHH-1001 / Alarm` says the SIF
  raises an alarm; v1 has no SIF -> Alarm relationship. These land in the exception register as X9,
  never silently dropped. Ontology change request: add `(SIF)-[:RAISES]->(Alarm)` with a
  competency question ("which alarms does a trip announce?") before loading them.
- **D-P2-03 Logic solver is a SIF property** (`logic_solver`), not a node. Promote to a label only if
  a CQ needs solver-level traversal (shared-solver common-cause analysis is the likely trigger).
- **D-P2-04 Voting lives on the INITIATES edge per cause group** (`voting`, `setpoint`,
  `cause_description`) and is copied to the SIF node as the ontology lists it. The edge is
  authoritative: X10 (voting arity vs initiator count) is computed from edges, so a SIF with a 2oo3
  pressure group and a 1oo2 level group is checked group by group.
- **D-P2-05 Equipment named only in the C&E** (Protected Equipment) that is neither in the index nor
  on a P&ID is created as a stub Equipment node and noted in the load report.
- **D-P2-06 Title-block reader.** Fixed page region (default bottom-right: x 55-100 %, y 80-100 %)
  and three regexes (drawing number, revision, sheet n of m); `extracted_by = pid_audit`. Pages
  without a text layer or without a recognisable title block -> X13. Drawings registered from the
  PDF that no index row or extraction row mentions -> X12. The Aconex transmittal number is the
  prefix of `load_run` (e.g. `TX-0057-20260909T022625Z`), so every fact traces to an issue.
- **D-P2-07 Change detection.** Before the unit is wiped, the new PDF's revision map is diffed
  against the Document nodes in the graph: new / revised / unchanged, and the list of drawings to
  re-extract. Phase 2 still performs the full rebuild of the unit; feeding the re-extract list back
  to pid_audit is the next optimisation.
- **D-P2-08 Query templates** (`pid_graph/queries.py`): `out_of_service`, `shelve_impact`,
  `moc_impact`, `trip`. `COMPENSATES_FOR` stays curated-only; the templates return a heuristic
  `candidate_compensation` shortlist (same measured variable, not SIS, not an initiator of the same
  SIF, at the same location or within two FEEDS hops), labelled as a shortlist for engineering
  judgement, never as a conclusion.
- **D-P2-09 Synthetic PDF.** No real Aconex file is on this machine, so `scripts/make_dummy_pdf.py`
  fabricates one with the right shape (cover page + one page per drawing with a title block). The
  first real file will need a one-time calibration of the region and regexes in
  `loaders/titleblock.py`; check the text layer first (decisions section 7).
- **D-P2-10 Curated register for COMPENSATES_FOR.** `data/curated/compensating_measures_<unit>.csv`
  (sif_id, alarm_id, rank, basis, conditions, rationale, status, curated_by, date) is the only source
  of COMPENSATES_FOR edges. The loader writes an edge only for rows with `status = approved` and a
  named `curated_by`; `extracted_by = manual`, the register is a `Document` of type `CUR`, and each
  edge carries rank, basis, conditions, rationale and the curator. Rows the LLM drafted stay
  `proposed` (reported, not loaded) until an engineer changes them to `approved` - the ontology's
  "never LLM-extracted" rule is enforced by the loader, not by convention. `basis` distinguishes
  `independent_bpcs`, `shares_sif_sensor` (valid only while that sensor is in service) and
  `field_only`; `gap` rows record why no measure exists. Reconcile raises X14 for any SIF with no
  curated edge, quoting the pending proposals or the gap rationale.
- **D-P2-11 MCP server is read-only by construction.** `pid_graph/mcp_server.py` (stdio, `.mcp.json`) exposes
  the four templates plus lookup/register tools. Every query runs in a Neo4j read transaction; the
  exploration tool `read_cypher` additionally rejects write keywords and is labelled exploration-only in
  its description, so a client cannot be talked into using it for a safety-relevant answer (section 4).
  The server holds no write path at all; loads happen only through `python -m pid_graph`.
- **D-P2-12 Ontology v1.1 adopted** (`PID_GRAPH_ONTOLOGY_V1_1.md`; v1 kept for the record). Adds `RAISES`
  (SIF -> Alarm, CQ9) and `CASCADES_TO` (SIF -> SIF, CQ10), writes down `table`, edge identity by
  `source_doc`, `CUR` documents and the stub convention. Loader consequences: a C&E alarm effect is
  resolved to the register's Alarm by `alarm_tag`; if the register lacks it, a stub Alarm keyed by the
  bare tag is created and X9 now means "C&E alarm effect not in the alarm register". An effect column
  whose tag is a SIF/ESD id becomes CASCADES_TO (stub SIF if not defined in this C&E). D-P2-02 is
  superseded.
- **D-P2-13 Intake before the first real run.** `python -m pid_graph.intake <file>` reports, without
  touching the graph, whether the loaders understand a new document: recognised and unrecognised
  headers (alias-map candidates), document number/revision detection, tag-shape acceptance per column
  (regex/prefix candidates), and for PDFs the text layer and which page region yields drawing + rev.
  Calibration of `loaders/tables.py` aliases, `tags.py` prefixes/regex and `loaders/titleblock.py`
  DEFAULT_REGION is expected on the first real set and is done from this report, not by guessing.

## 12. Phase 3 decisions (Claude Code, 9 Sep 2026)

- **D-P3-01 Live out-of-service register as node properties.** Active bypasses, MOS, shelved alarms and
  interlock bypasses live in `data/oos/out_of_service_<unit>.csv` and are applied to the affected
  Instrument / Alarm nodes as `oos_*` properties (id, kind, start, expiry, authoriser, requester, reason,
  compensating-measures-confirmed, notes, source ref) by `python -m pid_graph.oos apply`, without a full
  rebuild; `run_all` re-applies it after every rebuild. Not a label (no ontology change: it is operational
  state, not plant structure) and not an edge. Every assessment now evaluates the request combined with
  everything already out: remaining initiators/final elements exclude out-of-service elements, and a
  curated compensating alarm is INVALID when it is itself shelved or generated by an out-of-service
  element. The register is the operations input the graph was missing; the control room already keeps it.
- **D-P3-02 Shift handover protection status** is derived, never typed: per-SIF UNAFFECTED / DEGRADED /
  DEFEATED given the register, valid vs lost compensating measures, flags (no valid measure while
  degraded; measure shelved while its SIF is degraded), expiring / expired entries, unconfirmed measures.
- **D-P3-03 Trip investigation pack** (CQ6 + CQ9) is a report, not a new schema: causes (initiators with
  voting, setpoint, what they measure, current state), what should have preceded (pre-alarms on the
  initiators and other alarms on the measured items), what the trip should have done (final elements,
  announcing alarm), cascade, a fixed investigation checklist, documents, and register caveats.

## 13. Phase 4 decisions (Claude Code, 9 Sep 2026): SRS and LOPA, ontology v1.2

- **D-P4-01 Ontology v1.2** (`PID_GRAPH_ONTOLOGY_V1_2.md`): `Scenario` label, `CREDITS` and `THREATENS`
  relationships, SRS requirements as source-named properties on `SIF`, doc types `SRS` and `LOPA`;
  competency questions CQ11 (IPL independence), CQ12 (SIL consistency), CQ13 (SRS conformance).
- **D-P4-02 SRS values never overwrite C&E values.** `sil` and INITIATES `setpoint`/`voting` stay the C&E's;
  the SRS lands in `sil_srs`, `setpoint_srs`, `sensor_architecture`, ... with the SRS as a second `SHOWN_ON`
  witness. Reconcile compares them: X15 (SIL: LOPA vs SRS vs C&E), X16 (setpoint), X20 (architecture),
  X19 (SIF present in one document and not the other). Conflict rule kept: both facts, both provenances.
- **D-P4-03 LOPA credits resolve to existing nodes.** Alarm IPLs resolve through the register's `alarm_tag`;
  SIFs by id; anything else tag-shaped becomes an Instrument (stub if not in the index, X18); BPCS loop
  IPLs are not representable (no Loop label) and are reported as X18 rather than invented. A layer listed
  without a PFD is not credited. X17 flags a credited alarm that derives from a sensor initiating a SIF
  credited in the same scenario, and two credited SIFs sharing an initiator or final element.
- **D-P4-04 Registers, not prose.** Real SRS and LOPA are Word/PDF documents; the loaders read the tabular
  register form (one row per SIF / per scenario / per IPL) that a project safety register exports. Turning
  a prose SRS into that table is a document-control task, not an LLM extraction (section 4 of the
  decisions: never LLM-extracted for safety-relevant facts). `scripts/make_dummy_srs_lopa.py` fabricates
  both registers for U-100 with four planted discrepancies.
- **D-P4-05 SRS bypass conditions are quoted in every bypass / MOS assessment** for the affected SIF, so
  the person authorising sees the design requirement next to the graph's answer.
- **D-P4-06 Vocabulary rule.** Two registers, kept strict. Engineering surfaces (ontology, decisions,
  validator, code, MCP tool descriptions, the explorer, the MOC / bypass / MOS / shelving / trip / design-basis
  reports) use Neo4j's words: *node* and *relationship*, never *edge*, never *arrow* or *item*. Plant objects keep
  their engineering names (initiator, final element, protected equipment, compensating measure). The one
  operator-facing surface, the shift handover page, says *element* for a thing out of service rather than
  *node*. Reason: the explorer is visibly nodes and lines and the words should match the picture; the ontology
  and Neo4j already say relationship; an operator reading a handover should not meet database vocabulary.
