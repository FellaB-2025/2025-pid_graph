"""MCP server exposing the pid_graph query templates as read-only tools (decisions section 4).

Run by an MCP client (Claude Code, Claude Desktop) over stdio:

    python -m pid_graph.mcp_server

The server never writes to the graph. Safety-relevant answers come only from the
fixed templates (out_of_service, shelve_impact, moc_impact, trip); `read_cypher`
is exploration-only and runs inside a read transaction so a write cannot slip
through. Every answer carries the graph's own provenance.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys

from mcp.server.mcpserver import MCPServer

from . import ontology as O
from . import queries as Q
from .db import DATABASE, get_driver
from .reconcile import TITLES, reconcile

log = logging.getLogger("pid_graph.mcp")

INSTRUCTIONS = """\
pid_graph is a Neo4j knowledge graph of the functional-safety layer of a process unit: Instrument,
Equipment, Line, SIF, Alarm, State, Document and Scenario (LOPA) nodes; MEASURES, INSTALLED_ON, FEEDS,
INITIATES, ACTUATES, PROTECTS, RAISES, CASCADES_TO, GENERATES, VALID_IN, HAS_STATE, COMPENSATES_FOR,
CREDITS, THREATENS and SHOWN_ON relationships (ontology v1.2). SIF nodes carry the SRS requirements as
sil_srs, setpoint_srs, safe_state, process_safety_time, response_time, proof_test_interval,
bypass_conditions etc.; the C&E's own sil and INITIATES setpoints sit beside them, and the exception
register (X15-X20) says where LOPA, SRS and C&E disagree. Instrument and Alarm nodes may carry oos_*
properties: the live out-of-service register (bypass, MOS, shelved). Use read_cypher to answer
questions about scenarios, IPL independence and SRS conformance.
Tags are upper-case like PT-1001A, XV-1001, L-101, V-1002, SIF-100-01; alarms are <tag>.<type> like
PT-1001A.PAH.

Use the tools rather than guessing. For anything safety-relevant (bypass, MOS, shelving, interlock
bypass, MOC, trip investigation) use the fixed templates: out_of_service, shelve_impact, moc_impact,
trip. curated_compensating_alarms are engineering judgement (COMPENSATES_FOR); candidate_compensation
is a heuristic shortlist, never a conclusion - say so when you quote it. Every node and edge carries
provenance (source_doc, source_rev, extracted_by, load_run, source_ref); quote it when the user needs
to know why the graph believes something. The exception register (exceptions tool) lists where the
documents disagree or are incomplete - check it before relying on a tag. If a tag is not in the graph,
say so; do not invent connections. The graph is read-only here.

Ontology v1.3 adds a vision layer read from the P&IDs: Segment, InlineItem and ControlLoop nodes;
SEGMENT_OF, FLOWS_TO, SIGNAL_TO and MEMBER_OF relationships. Every such fact has
extracted_by=pidkg_vision and a review property. Until an engineer accepts it in the review register
it is review=pending: the four fixed templates ignore it, but find, describe, documents and
read_cypher DO show it. When you quote a fact from those tools, check its review value and say so if
it is pending. Never base a safety-relevant statement on a pending or rejected fact."""

server = MCPServer(name="pid_graph", version="0.2.0", instructions=INSTRUCTIONS)
_state: dict = {"driver": None}


def _driver():
    if _state["driver"] is None:
        _state["driver"] = get_driver()
    return _state["driver"]


def _read(cypher: str, **params) -> list[dict]:
    with _driver().session(database=DATABASE) as s:
        return s.execute_read(lambda tx: [r.data() for r in tx.run(cypher, **params)])


def _ident(n: dict) -> str:
    return n.get("tag") or n.get("line_no") or n.get("alarm_id") or n.get("sif_id") or n.get("state_id") or \
        (f"{n.get('doc_no')} rev {n.get('rev')}" if n.get("doc_no") else "?")


# ---- Lookup ----------------------------------------------------------------------

@server.tool(description="Summary of the loaded graph: node counts by label, relationship counts by type, units present, "
                         "and the load runs (transmittal-stamped) the data came from.")
def graph_info() -> dict:
    by_label = {r["l"]: r["c"] for r in _read("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY l")}
    by_rel = {r["t"]: r["c"] for r in _read("MATCH ()-[e]->() RETURN type(e) AS t, count(*) AS c ORDER BY t")}
    units = [r["u"] for r in _read("MATCH (n) WHERE n.unit IS NOT NULL RETURN DISTINCT n.unit AS u ORDER BY u")]
    runs = [r["r"] for r in _read("MATCH (n) WHERE n.load_run IS NOT NULL RETURN DISTINCT n.load_run AS r ORDER BY r")]
    return {"nodes_by_label": by_label, "relationships_by_type": by_rel, "units": units, "load_runs": runs}


@server.tool(description="Find nodes whose identifier, service or description contains the query (case-insensitive). "
                         "Optionally restrict to a label: Instrument, Equipment, Line, SIF, Alarm, State, Document.")
def find(query: str, label: str | None = None, limit: int = 25) -> list[dict]:
    if label and label not in O.LABELS:
        return [{"error": f"label must be one of {O.LABELS}"}]
    lab = f":{label}" if label else ""
    rows = _read(f"MATCH (n{lab}) WITH n, labels(n)[0] AS label, "
                 "coalesce(n.tag, n.line_no, n.alarm_id, n.sif_id, n.state_id, n.doc_no, '') AS id, "
                 "coalesce(n.service, n.description, n.title, '') AS text "
                 "WHERE toLower(id) CONTAINS toLower($q) OR toLower(text) CONTAINS toLower($q) "
                 "RETURN label, id, text, n.unit AS unit, coalesce(n.stub, false) AS stub "
                 "ORDER BY (NOT toLower(id) STARTS WITH toLower($q)), label, id LIMIT $limit", q=query, limit=limit)
    return rows


@server.tool(description="Everything the graph knows about one identifier (tag, line number, alarm id, SIF id or document "
                         "number): properties with provenance, every relationship in and out with the relationship's own "
                         "provenance, and any exception-register entries against it.")
def describe(identifier: str) -> dict:
    ident = identifier.upper().strip()
    nodes = _read("MATCH (n) WHERE n.tag = $id OR n.line_no = $id OR n.alarm_id = $id OR n.sif_id = $id "
                  "OR n.state_id = $id OR n.doc_no = $id RETURN labels(n)[0] AS label, properties(n) AS p", id=ident)
    if not nodes:
        hint = find(ident.split("-")[0] if "-" in ident else ident, limit=5)
        return {"identifier": ident, "error": "not in graph", "suggestions": [h["id"] for h in hint]}
    out = []
    for n in nodes:
        edges = _read("MATCH (n) WHERE n.tag = $id OR n.line_no = $id OR n.alarm_id = $id OR n.sif_id = $id "
                      "OR n.state_id = $id OR n.doc_no = $id "
                      "MATCH (n)-[e]-(m) RETURN type(e) AS type, startNode(e) = n AS outgoing, labels(m)[0] AS other_label, "
                      "properties(m) AS other, properties(e) AS props ORDER BY type, outgoing", id=ident)
        rels = [{"type": e["type"], "direction": "out" if e["outgoing"] else "in", "other_label": e["other_label"],
                 "other": _ident(e["other"]), **{k: v for k, v in e["props"].items()}} for e in edges]
        out.append({"label": n["label"], "properties": n["p"], "relationships": rels})
    store = _Store()
    unit = nodes[0]["p"].get("unit")
    ex = [e for e in reconcile(store, unit=unit or "")["exceptions"] if ident in e["id"] or ident in e["detail"]]
    return {"identifier": ident, "matches": out, "exceptions": ex}


@server.tool(description="All SIFs with SIL, description, initiators (voting, setpoint), final elements (action), "
                         "protected items and curated compensating measures.")
def list_sifs() -> list[dict]:
    return _read(
        "MATCH (s:SIF) OPTIONAL MATCH (i:Instrument)-[ini:INITIATES]->(s) "
        "WITH s, collect(DISTINCT i.tag + ' ' + coalesce(ini.voting, '') + ' @ ' + coalesce(ini.setpoint, '')) AS initiators "
        "OPTIONAL MATCH (s)-[a:ACTUATES]->(fe:Instrument) WITH s, initiators, collect(DISTINCT fe.tag + ' ' + coalesce(a.action, '')) AS final_elements "
        "OPTIONAL MATCH (s)-[:PROTECTS]->(p) WITH s, initiators, final_elements, collect(DISTINCT coalesce(p.tag, p.line_no)) AS protects "
        "OPTIONAL MATCH (c:Alarm)-[cf:COMPENSATES_FOR]->(s) "
        "RETURN s.sif_id AS sif, s.sil AS sil, s.description AS description, s.logic_solver AS logic_solver, initiators, "
        "final_elements, protects, collect(DISTINCT c.alarm_id + ' (rank ' + toString(cf.rank) + ', ' + cf.basis + ')') AS curated_compensating "
        "ORDER BY sif")


@server.tool(description="Documents in the graph (instrument index, C&E, P&IDs, curated registers) with revision, type, and "
                         "how many nodes each one witnesses. Use it to see what must be re-verified when a document revises (CQ8).")
def documents() -> list[dict]:
    return _read("MATCH (d:Document) OPTIONAL MATCH (n)-[s:SHOWN_ON]->(d) "
                 "RETURN d.doc_no AS doc_no, d.rev AS rev, d.doc_type AS doc_type, d.title AS title, d.unit AS unit, "
                 "coalesce(d.stub, false) AS stub, d.transmittal AS transmittal, count(DISTINCT n) AS witnesses "
                 "ORDER BY doc_type, doc_no")


# ---- Fixed templates (safety-relevant answers come from these only) --------------------

@server.tool(description="The out-of-service question (bypass, MOS, interlock bypass): if this tag is taken out of service, "
                         "which SIFs lose an initiator or a final element, are they DEGRADED or DEFEATED, what remains, which of "
                         "its own alarms are lost, which curated compensating alarms apply (with validity: an alarm generated by "
                         "the bypassed element itself is INVALID NOW), and a heuristic candidate shortlist for engineering judgement.")
def out_of_service(tag: str) -> dict:
    return Q.out_of_service(_driver(), tag)


@server.tool(description="Alarm shelving impact: what hazard indication is lost, whether a SIF on the same sensor or another "
                         "alarm at the same location (or within two process hops) still covers the scenario, whether this alarm is "
                         "itself a curated compensating measure for a SIF, and the states it is valid in.")
def shelve_impact(alarm_id: str) -> dict:
    return Q.shelve_impact(_driver(), alarm_id)


@server.tool(description="MOC impact: everything within N hops (default 3) of a tag, line, alarm or SIF across MEASURES, "
                         "INSTALLED_ON, FEEDS, INITIATES, ACTUATES, PROTECTS and GENERATES, grouped by label, and the documents "
                         "that must be re-verified.")
def moc_impact(identifier: str, hops: int = 3) -> dict:
    return Q.moc_impact(_driver(), identifier, max(1, min(hops, 5)))


@server.tool(description="Trip troubleshooting for a SIF: every initiator with voting, setpoint, cause and what it measures; "
                         "the final elements and their actions; protected items; source documents; and a voting-arity check.")
def trip(sif_id: str) -> dict:
    return Q.trip(_driver(), sif_id)


# ---- Register --------------------------------------------------------------------

class _Store:
    """Read-only adapter so reconcile() can run against the live database."""

    def __init__(self):
        from .neo4j_store import Neo4jStore
        self._s = Neo4jStore(_driver(), DATABASE)

    def nodes(self, label=None):
        return self._s.nodes(label)

    def rels(self, rel=None):
        return self._s.rels(rel)

    conflicts: list = []


@server.tool(description="The exception register: where the instrument index, C&E, P&ID extraction and curated registers "
                         "disagree or are incomplete (codes X1-X14). Filter by code (e.g. 'X10') or identifier. "
                         "Curation-time entries (X9 alarm effects, X13 PDF pages) are only present in the run's Excel register.")
def exceptions(code: str | None = None, identifier: str | None = None, unit: str = "U-100") -> dict:
    rec = reconcile(_Store(), unit=unit)
    rows = rec["exceptions"]
    if code:
        rows = [r for r in rows if r["code"].upper() == code.upper()]
    if identifier:
        rows = [r for r in rows if identifier.upper() in r["id"].upper()]
    return {"summary": rec["summary"], "codes": TITLES, "count": len(rows), "exceptions": rows}


@server.tool(description="The closed v1 schema: labels with their key properties, relationship types with direction and meaning, "
                         "provenance properties and extracted_by values, and the exception codes.")
def schema_reference() -> dict:
    meaning = {"MEASURES": "Instrument -> Line/Equipment: what the device senses",
               "INSTALLED_ON": "Instrument -> Line/Equipment: physical location",
               "FEEDS": "Line/Equipment -> Line/Equipment: process flow direction",
               "INITIATES": "Instrument -> SIF: trip initiator (voting, setpoint on the edge)",
               "ACTUATES": "SIF -> Instrument: final element action",
               "PROTECTS": "SIF -> Equipment/Line: what the SIF safeguards",
               "RAISES": "SIF -> Alarm: the trip announces itself through this alarm (v1.1)",
               "CASCADES_TO": "SIF -> SIF: activation of the first initiates the second, ESD hierarchy (v1.1)",
               "GENERATES": "Instrument -> Alarm: device raises this alarm",
               "VALID_IN": "Alarm -> State: alarm only meaningful in this state",
               "HAS_STATE": "Equipment -> State",
               "COMPENSATES_FOR": "Alarm -> SIF: curated compensating measure (engineering judgement only)",
               "CREDITS": "Scenario -> SIF/Alarm/Instrument: LOPA credits this layer (ipl_type, pfd; required_rrf/required_sil for the SIF) (v1.2)",
               "THREATENS": "Scenario -> Equipment/Line: what the LOPA scenario endangers (v1.2)",
               "SHOWN_ON": "any -> Document: provenance as a traversable edge; identity includes source_doc",
               "SEGMENT_OF": "Segment -> Line: the segment is a stretch of this line (v1.3)",
               "FLOWS_TO": "Segment/Equipment/Instrument/InlineItem -> same set: process flow at segment level "
                           "(flow_direction shown/inferred, off_page, confidence, review) (v1.3)",
               "SIGNAL_TO": "Instrument -> Instrument/Equipment: drawn signal line (signal_type, purpose, confidence, review); "
                            "a cross-check only, never a source of INITIATES / ACTUATES (v1.3)",
               "MEMBER_OF": "Instrument -> ControlLoop: loop membership (role) (v1.3)"}
    return {"labels": {l: list(k) for l, k in O.KEYS.items()}, "relationships": meaning,
            "provenance": list(O.PROVENANCE) + ["source_ref"], "extracted_by": list(O.EXTRACTED_BY),
            "review": list(O.REVIEW),
            "document_types": list(O.DOC_TYPES), "exception_codes": TITLES}


# ---- Exploration only -----------------------------------------------------------------

_WRITE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|CALL\s+\{|apoc\.|dbms\.)\b", re.I)


@server.tool(description="EXPLORATION ONLY - run a read-only Cypher query. Runs inside a read transaction; any write is rejected. "
                         "Never use this for safety-relevant answers (bypass, shelving, MOC, trip) - use the fixed templates. "
                         "Results are capped at 200 rows.")
def read_cypher(cypher: str) -> dict:
    if _WRITE.search(cypher):
        return {"error": "write keywords are not allowed; this server is read-only"}
    try:
        rows = _read(cypher)          # execute_read: the database itself rejects writes here
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return {"note": Q.EXPLORATORY_NOTE, "count": len(rows[:200]), "rows": rows[:200]}


# ---- Entry point ------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="pid_graph.mcp_server", description=__doc__)
    p.add_argument("--log-level", default="INFO")
    a = p.parse_args(argv)
    logging.basicConfig(level=a.log_level, stream=sys.stderr, format="%(name)s %(levelname)s %(message)s")
    try:
        _driver().verify_connectivity()
        log.info("connected to Neo4j at %s", DATABASE)
    except Exception as exc:  # noqa: BLE001
        log.error("Neo4j not reachable: %s", exc)
        sys.exit(2)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
