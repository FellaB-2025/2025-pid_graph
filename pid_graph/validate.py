"""Validation queries against the live Neo4j graph.

Structural checks (constraints exist, no orphans, no duplicate keys) plus the
competency-question sketches from PID_GRAPH_ONTOLOGY_V1.md section 5 that Phase 1
data can already answer: CQ1 lookup, CQ3 MOC impact, CQ7 cross-document
disagreement, CQ8 document scope. CQ2/4/5/6 need the C&E (Phase 2).

    python -m pid_graph.validate --tag PT-1001A --line L-101 --sheet PID-100-001
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import ontology as O
from .db import DATABASE, get_driver

# CQ3 names relationship types (INITIATES etc.) that only exist once the C&E is loaded;
# Neo4j warns about each. Those warnings are expected in Phase 1.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

CHECKS = [
    ("constraints", "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes[0] AS label, properties[0] AS property ORDER BY name", {}),
    ("labels outside the ontology", "MATCH (n) UNWIND labels(n) AS l WITH DISTINCT l WHERE NOT l IN $labels RETURN l", {"labels": list(O.LABELS)}),
    ("relationship types outside the ontology", "MATCH ()-[e]->() WITH DISTINCT type(e) AS t WHERE NOT t IN $rels RETURN t", {"rels": list(O.RELS)}),
    ("orphan nodes (no relationships)", "MATCH (n) WHERE NOT (n)--() AND NOT n:Document RETURN labels(n)[0] AS label, coalesce(n.tag, n.line_no, n.alarm_id) AS id", {}),
    ("registered drawings with nothing extracted yet", "MATCH (d:Document {doc_type: 'PID'}) WHERE NOT (d)<-[:SHOWN_ON]-() RETURN d.doc_no AS doc_no, d.rev AS rev, d.title AS title", {}),
    ("nodes without provenance", "MATCH (n) WHERE n.source_doc IS NULL OR n.extracted_by IS NULL OR n.load_run IS NULL RETURN labels(n)[0] AS label, coalesce(n.tag, n.line_no, n.alarm_id, n.doc_no) AS id", {}),
    ("relationships without provenance", "MATCH ()-[e]->() WHERE e.source_doc IS NULL OR e.extracted_by IS NULL RETURN type(e) AS type, count(*) AS n", {}),
    ("duplicate instrument tags (case/format)", "MATCH (n:Instrument) WITH toUpper(replace(n.tag, '-', '')) AS k, collect(n.tag) AS tags WHERE size(tags) > 1 RETURN k, tags", {}),
    ("stub nodes remaining", "MATCH (n) WHERE n.stub = true RETURN labels(n)[0] AS label, coalesce(n.tag, n.line_no, n.doc_no) AS id, n.source_doc AS referenced_on ORDER BY label, id", {}),
]

CQS = [
    ("CQ1 lookup: what is $tag and which documents show it",
     "MATCH (i:Instrument {tag: $tag}) OPTIONAL MATCH (i)-[s:SHOWN_ON]->(d:Document) "
     "RETURN i.tag AS tag, i.type AS type, i.service AS service, i.range AS range, i.units AS units, "
     "collect(DISTINCT d.doc_no + ' rev ' + d.rev + ' [' + s.extracted_by + ']') AS shown_on"),
    ("CQ3 MOC impact: what is within 3 hops of line $line",
     "MATCH (x:Line {line_no: $line}) MATCH p = (x)-[:MEASURES|INSTALLED_ON|FEEDS|INITIATES|GENERATES*..3]-(a) "
     "WITH DISTINCT a, min(length(p)) AS hops RETURN labels(a)[0] AS label, coalesce(a.tag, a.line_no, a.alarm_id) AS id, hops ORDER BY hops, label, id"),
    ("CQ7 disagreement: instruments the index and the P&ID extraction place on different drawings",
     "MATCH (i:Instrument)-[a:SHOWN_ON {extracted_by: 'table'}]->(claimed:Document {doc_type: 'PID'}) "
     "MATCH (i)-[b:SHOWN_ON]->(seen:Document {doc_type: 'PID'}) WHERE b.extracted_by IN ['pid_audit', 'manual'] "
     "WITH i, collect(DISTINCT claimed.doc_no) AS claimed, collect(DISTINCT seen.doc_no) AS seen "
     "WHERE none(c IN claimed WHERE c IN seen) RETURN i.tag AS tag, claimed, seen"),
    ("CQ7 agreement count: instruments where index and extraction agree on a drawing",
     "MATCH (i:Instrument)-[a:SHOWN_ON {extracted_by: 'table'}]->(d:Document {doc_type: 'PID'})<-[b:SHOWN_ON]-(i) "
     "WHERE b.extracted_by IN ['pid_audit', 'manual'] RETURN count(DISTINCT i) AS agreeing_instruments"),
    ("CQ2 bypass: if $tag is bypassed, which SIFs lose an initiator, what remains, what compensates (ontology section 5 sketch)",
     "MATCH (i:Instrument {tag: $tag})-[:INITIATES]->(s:SIF) "
     "OPTIONAL MATCH (sib:Instrument)-[:INITIATES]->(s) WHERE sib.tag <> $tag "
     "OPTIONAL MATCH (s)-[:PROTECTS]->(p) OPTIONAL MATCH (c:Alarm)-[:COMPENSATES_FOR]->(s) "
     "RETURN s.sif_id AS sif, s.sil AS sil, s.voting AS voting, collect(DISTINCT sib.tag) AS remaining_initiators, "
     "collect(DISTINCT coalesce(p.tag, p.line_no)) AS protects, collect(DISTINCT c.alarm_id) AS compensating_alarms"),
    ("CQ6 trip troubleshooting: initiators, what they measure, and what $sif actuates",
     "MATCH (s:SIF {sif_id: $sif}) OPTIONAL MATCH (i:Instrument)-[ini:INITIATES]->(s) OPTIONAL MATCH (i)-[:MEASURES]->(m) "
     "OPTIONAL MATCH (s)-[a:ACTUATES]->(fe:Instrument) "
     "RETURN s.sif_id AS sif, s.sil AS sil, collect(DISTINCT i.tag + ' ' + coalesce(ini.voting, '') + ' @ ' + coalesce(ini.setpoint, '') + ' on ' + coalesce(m.tag, m.line_no, '?')) AS initiators, "
     "collect(DISTINCT fe.tag + ' ' + coalesce(a.action, '')) AS actuates"),
    ("CQ9 trip announcement: which alarms announce $sif, and are any also compensating measures elsewhere (v1.1)",
     "MATCH (s:SIF {sif_id: $sif})-[r:RAISES]->(a:Alarm) OPTIONAL MATCH (a)-[:COMPENSATES_FOR]->(other:SIF) "
     "RETURN a.alarm_id AS alarm, a.alarm_tag AS alarm_tag, coalesce(a.stub, false) AS stub, r.source_doc AS source, "
     "collect(DISTINCT other.sif_id) AS also_compensates_for"),
    ("CQ10 cascade: which SIFs trip as a consequence of $sif (v1.1)",
     "MATCH p = (root:SIF {sif_id: $sif})-[:CASCADES_TO*1..5]->(s:SIF) OPTIONAL MATCH (s)-[:ACTUATES]->(fe:Instrument) "
     "RETURN s.sif_id AS sif, s.unit AS unit, length(p) AS depth, collect(DISTINCT fe.tag) AS final_elements ORDER BY depth"),
    ("CQ11 IPL independence: what LOPA credits per scenario and whether a credited alarm shares a sensor with a credited SIF (v1.2)",
     "MATCH (sc:Scenario)-[c:CREDITS]->(ipl) OPTIONAL MATCH (ipl)<-[:GENERATES]-(src:Instrument)-[:INITIATES]->(s:SIF)<-[:CREDITS]-(sc) "
     "RETURN sc.scenario_id AS scenario, labels(ipl)[0] AS layer, coalesce(ipl.sif_id, ipl.alarm_id, ipl.tag) AS id, c.ipl_type AS type, c.pfd AS pfd, "
     "coalesce(ipl.stub, false) AS not_in_registers, collect(DISTINCT src.tag + ' also initiates ' + s.sif_id) AS shares_sensor_with ORDER BY scenario, layer, id"),
    ("CQ12 SIL consistency: LOPA vs SRS vs C&E per SIF (v1.2)",
     "MATCH (s:SIF) OPTIONAL MATCH (sc:Scenario)-[c:CREDITS]->(s) "
     "RETURN s.sif_id AS sif, s.sil AS sil_ce, s.sil_srs AS sil_srs, collect(DISTINCT c.required_sil) AS sil_lopa ORDER BY sif"),
    ("CQ13 SRS conformance for $sif: requirements vs the as-built C&E (v1.2)",
     "MATCH (s:SIF {sif_id: $sif}) OPTIONAL MATCH (i:Instrument)-[ini:INITIATES]->(s) "
     "RETURN s.sif_id AS sif, s.safe_state AS safe_state, s.process_safety_time AS pst, s.response_time AS response_time, s.proof_test_interval AS pti, "
     "s.setpoint_srs AS srs_setpoint, collect(DISTINCT ini.setpoint) AS ce_setpoints, s.sensor_architecture AS srs_architecture, collect(DISTINCT ini.voting) AS ce_voting, s.bypass_conditions AS bypass_conditions"),
    ("CQ8 document scope: what $sheet shows (must be re-verified when it revises)",
     "MATCH (n)-[s:SHOWN_ON]->(d:Document {doc_no: $sheet}) WHERE s.extracted_by IN ['pid_audit', 'manual'] "
     "RETURN labels(n)[0] AS label, count(DISTINCT n) AS n, collect(DISTINCT coalesce(n.tag, n.line_no))[0..6] AS sample ORDER BY label"),
    ("Coverage per unit (index instruments seen on a P&ID)",
     "MATCH (i:Instrument)-[:SHOWN_ON]->(:Document {doc_type: 'IDX'}) "
     "OPTIONAL MATCH (i)-[s:SHOWN_ON]->(:Document {doc_type: 'PID'}) WHERE s.extracted_by IN ['pid_audit', 'manual'] "
     "WITH i.unit AS unit, i, count(s) > 0 AS seen RETURN unit, count(i) AS index_instruments, sum(CASE WHEN seen THEN 1 ELSE 0 END) AS seen_on_pid, "
     "round(100.0 * sum(CASE WHEN seen THEN 1 ELSE 0 END) / count(i), 1) AS pct"),
]


def run(driver, cypher, params):
    with driver.session(database=DATABASE) as s:
        return [r.data() for r in s.run(cypher, **params)]


def show(title, rows, empty_ok=True):
    flag = "" if rows or not empty_ok else ""
    print(f"\n[{title}] -> {len(rows)} row(s){flag}")
    for r in rows[:25]:
        print("   " + "  ".join(f"{k}={v}" for k, v in r.items()))
    if len(rows) > 25:
        print(f"   ... {len(rows) - 25} more")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="PT-1001A")
    ap.add_argument("--line", default="L-101")
    ap.add_argument("--sheet", default="PID-100-001")
    ap.add_argument("--sif", default="SIF-100-01")
    a = ap.parse_args(argv)
    driver = get_driver()
    failures = 0
    try:
        print("=== structural checks ===")
        for title, cypher, params in CHECKS:
            rows = run(driver, cypher, params)
            show(title, rows)
            if title in ("labels outside the ontology", "relationship types outside the ontology", "orphan nodes (no relationships)",
                         "nodes without provenance", "relationships without provenance", "duplicate instrument tags (case/format)") and rows:
                failures += 1
                print("   FAIL: expected no rows")
        print("\n=== competency question sketches ===")
        for title, cypher in CQS:
            show(title, run(driver, cypher, {"tag": a.tag, "line": a.line, "sheet": a.sheet, "sif": a.sif}))
    finally:
        driver.close()
    print(f"\n{'ALL STRUCTURAL CHECKS PASSED' if not failures else str(failures) + ' STRUCTURAL CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
