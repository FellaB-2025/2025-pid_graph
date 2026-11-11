"""Engineer-facing reports generated from the live graph (Word + Markdown).

    python -m pid_graph.report compensating-measures            -> reports/CM_register_U-100.docx / .md
    python -m pid_graph.report bypass XV-1001 --duration "8 h" --requester "Shift Supervisor" --reason "..."
                                                                 -> reports/bypass_XV-1001.docx / .md

Every statement in a report is traceable: each section names the source documents and
revisions the facts came from, and the register exceptions that qualify them. Curated
compensating measures carry the curator's initials and date. Nothing is inferred by an LLM.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from . import queries as Q
from .db import DATABASE, get_driver
from .reconcile import TITLES, reconcile

ROOT = Path(__file__).resolve().parent.parent
VOTING_RE = re.compile(r"(\d+)\s*oo\s*(\d+)", re.I)


# ---- data gathering -----------------------------------------------------------------

def _run(driver, cypher, **params):
    with driver.session(database=DATABASE) as s:
        return [r.data() for r in s.run(cypher, **params)]


def _store(driver):
    from .neo4j_store import Neo4jStore

    class S:
        def __init__(self):
            self._s = Neo4jStore(driver, DATABASE)
        nodes = property(lambda self: self._s.nodes)
        rels = property(lambda self: self._s.rels)
        conflicts: list = []
    return S()


def gather_unit(driver, unit: str) -> dict:
    sifs = _run(driver, """
        MATCH (s:SIF) WHERE s.unit = $unit OR $unit = ''
        OPTIONAL MATCH (i:Instrument)-[ini:INITIATES]->(s) OPTIONAL MATCH (i)-[mm:MEASURES]->(m) WHERE __T7_MM__ AND __T7_M__
        WITH s, i, ini, collect(DISTINCT coalesce(m.tag, m.segment_id, m.line_no)) AS measures
        WITH s, collect(DISTINCT CASE WHEN i IS NULL THEN NULL ELSE {tag: i.tag, service: i.service, system: i.system,
             voting: ini.voting, setpoint: ini.setpoint, cause: ini.cause_description, measures: measures,
             stub: coalesce(i.stub, false), source: ini.source_doc + ' rev ' + ini.source_rev} END) AS initiators
        OPTIONAL MATCH (s)-[a:ACTUATES]->(fe:Instrument)
        WITH s, initiators, collect(DISTINCT CASE WHEN fe IS NULL THEN NULL ELSE {tag: fe.tag, action: a.action, service: fe.service} END) AS final_elements
        OPTIONAL MATCH (s)-[:PROTECTS]->(p)
        WITH s, initiators, final_elements, collect(DISTINCT coalesce(p.tag, p.line_no)) AS protects
        OPTIONAL MATCH (s)-[:RAISES]->(ra:Alarm)
        WITH s, initiators, final_elements, protects,
             collect(DISTINCT CASE WHEN ra IS NULL THEN NULL ELSE {alarm: ra.alarm_id, in_register: NOT coalesce(ra.stub, false)} END) AS raises
        OPTIONAL MATCH (c:Alarm)-[cf:COMPENSATES_FOR]->(s) OPTIONAL MATCH (c)<-[:GENERATES]-(src:Instrument)
        WITH s, initiators, final_elements, protects, raises,
             collect(DISTINCT CASE WHEN c IS NULL THEN NULL ELSE {alarm: c.alarm_id, alarm_tag: c.alarm_tag, setpoint: c.setpoint,
             priority: c.priority, description: c.description, source_tag: src.tag, source_system: src.system,
             rank: cf.rank, basis: cf.basis, conditions: cf.conditions, rationale: cf.rationale,
             curated_by: cf.curated_by, curated_on: cf.curated_on, register: cf.source_doc + ' rev ' + cf.source_rev} END) AS measures
        OPTIONAL MATCH (sc:Scenario)-[cr:CREDITS]->(s)
        WITH s, initiators, final_elements, protects, raises, measures,
             collect(DISTINCT CASE WHEN sc IS NULL THEN NULL ELSE {scenario: sc.scenario_id, initiating_event: sc.initiating_event,
             ie_frequency: sc.ie_frequency, consequence: sc.consequence, severity: sc.severity, tolerable_frequency: sc.tolerable_frequency,
             required_rrf: cr.required_rrf, required_sil: cr.required_sil, notes: sc.notes, source: sc.source_doc + ' rev ' + sc.source_rev} END) AS scenarios
        OPTIONAL MATCH (s)-[so:SHOWN_ON]->(d:Document) WHERE __T7_SO__
        RETURN s.sif_id AS sif, s.sil AS sil, s.description AS description, s.logic_solver AS logic_solver, s.unit AS unit,
               [x IN initiators WHERE x IS NOT NULL] AS initiators, [x IN final_elements WHERE x IS NOT NULL] AS final_elements,
               protects, [x IN raises WHERE x IS NOT NULL] AS raises, [x IN measures WHERE x IS NOT NULL] AS measures,
               [x IN scenarios WHERE x IS NOT NULL] AS scenarios,
               {sil_srs: s.sil_srs, rrf_target: s.rrf_target, pfd_target: s.pfd_target, demand_mode: s.demand_mode, safe_state: s.safe_state,
                process_safety_time: s.process_safety_time, response_time: s.response_time, setpoint_srs: s.setpoint_srs,
                sensor_architecture: s.sensor_architecture, fe_architecture: s.fe_architecture, proof_test_interval: s.proof_test_interval,
                bypass_conditions: s.bypass_conditions, manual_shutdown: s.manual_shutdown, reset: s.reset, hazard: s.hazard,
                functional_description: s.functional_description, srs_ref: s.srs_ref} AS srs,
               collect(DISTINCT d.doc_no + ' rev ' + d.rev) AS documents
        ORDER BY sif""".replace("__T7_MM__", Q.trusted_rel("mm")).replace("__T7_M__", Q.trusted_rel("m")).replace("__T7_SO__", Q.trusted_rel("so")), unit=unit)
    ipls = _run(driver, "MATCH (sc:Scenario)-[c:CREDITS]->(ipl) RETURN sc.scenario_id AS scenario, labels(ipl)[0] AS layer, "
                        "coalesce(ipl.sif_id, ipl.alarm_id, ipl.tag) AS id, c.ipl_type AS ipl_type, c.pfd AS pfd, c.credit_description AS basis, "
                        "coalesce(ipl.stub, false) AS stub ORDER BY scenario, layer, id")
    for s in sifs:
        for sc in s["scenarios"]:
            sc["ipls"] = [x for x in ipls if x["scenario"] == sc["scenario"]]
    for s in sifs:
        s["measures"].sort(key=lambda m: (m["rank"] or 99, m["alarm"]))
        votes = {i["voting"] for i in s["initiators"] if i["voting"]}
        s["voting_check"] = [{"voting": v, "listed": sum(1 for i in s["initiators"] if i["voting"] == v),
                              "expected": int(VOTING_RE.search(v).group(2)) if VOTING_RE.search(v) else None} for v in sorted(votes)]
    docs = _run(driver, "MATCH (d:Document) RETURN d.doc_no AS doc_no, d.rev AS rev, d.doc_type AS doc_type, d.title AS title, "
                        "coalesce(d.stub, false) AS stub, d.transmittal AS transmittal, d.load_run AS load_run ORDER BY doc_type, doc_no")
    rec = reconcile(_store(driver), unit=unit)
    return {"unit": unit, "sifs": sifs, "documents": docs, "register": rec}


# ---- markdown -----------------------------------------------------------------------

def _tbl(rows: list[list[str]], header: list[str]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return out


def cm_markdown(data: dict) -> str:
    unit, today = data["unit"], date.today().isoformat()
    L = [f"# Compensating Measures Register - {unit}", "",
         f"Generated {today} from the pid_graph knowledge graph. Compensating measures are engineering judgement "
         "(COMPENSATES_FOR, curated register), never inferred. Every fact below carries its source document and revision.", "",
         "## Source documents", ""]
    L += _tbl([[d["doc_no"], d["rev"], d["doc_type"], d["title"] or "", d["transmittal"] or "", "referenced only" if d["stub"] else "loaded"]
               for d in data["documents"]], ["Document", "Rev", "Type", "Title", "Transmittal", "Status"])
    L += ["", "## Summary", ""]
    L += _tbl([[s["sif"], s["sil"], s["description"], ", ".join(f"{i['tag']}" for i in s["initiators"]),
                ", ".join(f"{f['tag']} {f['action'] or ''}".strip() for f in s["final_elements"]),
                ", ".join(m["alarm"] for m in s["measures"]) or "NONE - see gap"] for s in data["sifs"]],
              ["SIF", "SIL", "Function", "Initiators", "Final elements", "Curated compensating alarms"])
    for s in data["sifs"]:
        L += ["", f"## {s['sif']} - {s['description']}", "",
              f"SIL {s['sil'] or '?'} | logic solver {s['logic_solver'] or '?'} | protects {', '.join(s['protects']) or '?'} | "
              f"source: {', '.join(s['documents'])}", "", "### Trip function", ""]
        L += _tbl([[i["tag"] + (" (NOT IN INDEX)" if i["stub"] else ""), i["service"] or "", i["system"] or "", i["voting"] or "", i["setpoint"] or "",
                    ", ".join(i["measures"]) or "?", i["cause"] or ""] for i in s["initiators"]],
                  ["Initiator", "Service", "System", "Voting", "Setpoint", "Measures", "Cause"])
        for v in s["voting_check"]:
            if v["expected"] is not None and v["listed"] != v["expected"]:
                L += ["", f"**Voting mismatch:** {v['voting']} implies {v['expected']} initiators; the C&E lists {v['listed']} (register X10)."]
        L += [""]
        L += _tbl([[f["tag"], f["action"] or "", f["service"] or ""] for f in s["final_elements"]], ["Final element", "Action", "Service"])
        if s["raises"]:
            L += ["", "Trip announced by: " + ", ".join(r["alarm"] + ("" if r["in_register"] else " (not in alarm register)") for r in s["raises"])]
        srs = s.get("srs") or {}
        L += ["", "### Design basis (SRS)", ""]
        if srs.get("sil_srs") or srs.get("safe_state"):
            ce_sp = ", ".join(sorted({i["setpoint"] for i in s["initiators"] if i["setpoint"]}))
            ce_v = ", ".join(sorted({i["voting"] for i in s["initiators"] if i["voting"]}))
            same = lambda a, b: bool(a) and bool(b) and str(a).replace(" ", "").lower() == str(b).replace(" ", "").lower()
            L += _tbl([["SIL", srs.get("sil_srs") or "-", s["sil"] or "-", "agree" if same(srs.get("sil_srs"), s["sil"]) else "DIFFER"],
                       ["Trip setpoint", srs.get("setpoint_srs") or "-", ce_sp or "-", "agree" if same(srs.get("setpoint_srs"), ce_sp) else "DIFFER"],
                       ["Sensor architecture", srs.get("sensor_architecture") or "-", ce_v or "-",
                        "agree" if ce_v and str(srs.get("sensor_architecture") or "").lower().startswith(ce_v.lower()) else "DIFFER"]],
                      ["Requirement", "SRS says", "C&E says", ""])
            L += [""]
            L += _tbl([[lbl, srs.get(k) or "-"] for k, lbl in (("safe_state", "Safe state"), ("process_safety_time", "Process safety time"), ("response_time", "SIF response time"),
                                                             ("rrf_target", "RRF target"), ("pfd_target", "PFDavg target"), ("demand_mode", "Demand mode"),
                                                             ("fe_architecture", "Final element architecture"), ("proof_test_interval", "Proof test interval"),
                                                             ("bypass_conditions", "Bypass conditions"), ("manual_shutdown", "Manual shutdown"), ("reset", "Reset"),
                                                             ("hazard", "Hazard / consequence")) if srs.get(k)], ["Requirement", "Value"])
            L += ["", f"Source: SRS {srs.get('srs_ref') or ''}"]
        else:
            L.append("No SRS entry loaded for this SIF.")
        L += ["", "### LOPA scenarios crediting this SIF", ""]
        if s["scenarios"]:
            for sc in s["scenarios"]:
                L += [f"**{sc['scenario']}** - {sc['consequence'] or ''}. Initiating event: {sc['initiating_event'] or '?'} ({sc['ie_frequency'] or '?'} /yr); "
                      f"severity {sc['severity'] or '?'}; tolerable frequency {sc['tolerable_frequency'] or '?'} /yr. Demanded of this SIF: RRF {sc['required_rrf'] or '?'}, **SIL {sc['required_sil'] or '?'}**"
                      + (f" (C&E says SIL {s['sil']}, SRS says SIL {srs.get('sil_srs') or '?'})" if sc["required_sil"] and str(sc["required_sil"]) != str(s["sil"]) else "") + ".", ""]
                L += _tbl([[x["id"] + (" (this SIF)" if x["id"] == s["sif"] else ""), x["ipl_type"] or "", x["pfd"] if x["pfd"] is not None else "-", x["basis"] or "",
                            "NOT IN REGISTERS" if x["stub"] else ""] for x in sc["ipls"]], ["Credited layer", "Type", "PFD", "Basis", "Status"])
                L += [f"Source: LOPA {sc['source']}" + (f" - {sc['notes']}" if sc["notes"] else ""), ""]
        else:
            L.append("No LOPA scenario credits this SIF.")
        L += ["", "### Compensating measures (curated)", ""]
        if s["measures"]:
            for m in s["measures"]:
                L += [f"**{m['rank'] or '-'}. {m['alarm']}** ({m['alarm_tag'] or ''}) - {m['description'] or ''}", "",
                      f"- Source: {m['source_tag'] or '?'} ({m['source_system'] or '?'}), setpoint {m['setpoint'] or '?'}, priority {m['priority'] or '?'}",
                      f"- Basis: {m['basis']}", f"- Conditions: {m['conditions'] or '-'}", f"- Rationale: {m['rationale'] or '-'}",
                      f"- Curated by {m['curated_by']} on {m['curated_on'] or '?'} ({m['register']})", ""]
        else:
            gap = next((e["detail"] for e in data["register"]["exceptions"] if e["code"] == "X14" and e["id"] == s["sif"]), "")
            L += ["**NONE CURATED.** " + (gap or "No compensating measure has been curated for this SIF."), ""]
        ex = [e for e in data["register"]["exceptions"]
              if e["id"] == s["sif"] or any(e["id"] == i["tag"] for i in s["initiators"]) or any(e["id"] == f["tag"] for f in s["final_elements"])
              or any(e["id"] == m["alarm"] for m in s["measures"]) or any(e["id"] == r["alarm"] for r in s["raises"])]
        if ex:
            L += ["### Data caveats (exception register)", ""]
            L += _tbl([[e["code"], e["id"], e["detail"]] for e in ex if e["code"] != "X14"], ["Code", "Node", "Detail"])
    L += ["", "---", "", f"Exception codes: " + "; ".join(f"{k} = {v}" for k, v in TITLES.items()), ""]
    return "\n".join(L)


def bypass_markdown(res: dict, unit_data: dict, duration: str, requester: str, reason: str) -> str:
    tag, today = res["tag"], date.today().isoformat()
    L = [f"# SIS Bypass Assessment - {tag}", "", "| | |", "|---|---|", f"| Element out of service | {tag} |",
         f"| Requester | {requester or '-'} |", f"| Reason | {reason or '-'} |", f"| Requested duration | {duration or '-'} |",
         f"| Generated | {today} from the pid_graph knowledge graph |",
         "| Status | DRAFT - requires authorisation per the site bypass procedure |", ""]
    worst = "UNAFFECTED"
    for r in res["as_initiator"] + res["as_final_element"]:
        if r["status"].startswith("DEFEATED"):
            worst = "DEFEATED"
        elif worst != "DEFEATED":
            worst = "DEGRADED"
    L += [f"**Summary:** {len(res['as_initiator']) + len(res['as_final_element'])} SIF(s) affected; worst case **{worst}**.", ""]
    for r in res["as_initiator"]:
        L += [f"## {r['sif']} - {r['status']}", "", f"{r['description']} (SIL {r['sil']}). {tag} is an initiator, voting {r['voting'] or '1oo1'} @ {r['setpoint'] or '?'} ({r['source']}).",
              f"Remaining initiators: {', '.join(r['remaining_initiators']) or 'NONE'} (needs {r['initiators_needed']}). "
              f"Final elements: {', '.join(r['final_elements']) or '?'}. Protects: {', '.join(r['protects']) or '?'}.", ""]
        L += _cm_section(r["curated_compensating_alarms"])
    for r in res["as_final_element"]:
        L += [f"## {r['sif']} - {r['status']}", "", f"{r['description']} (SIL {r['sil']}). {tag} is a final element ({r['action']}).",
              f"Remaining final elements: {', '.join(r['remaining_final_elements']) or 'NONE'}. Protects: {', '.join(r['protects']) or '?'}.", ""]
        L += _cm_section(r["curated_compensating_alarms"])
    if res["own_alarms_lost"]:
        L += ["## Alarms lost with the element", ""] + [f"- {a['alarm']} @ {a['setpoint']} ({a['priority']})" for a in res["own_alarms_lost"]] + [""]
    if res["sif_sensor_alarms_still_active"]:
        L += ["## SIF sensor alarms still active", ""] + [f"- {a['alarm']} on {a['sensor']} @ {a['setpoint']}: {a['note']}" for a in res["sif_sensor_alarms_still_active"]] + [""]
    if res["candidate_compensation"]:
        L += ["## Candidate shortlist (heuristic - for engineering judgement, not a conclusion)", ""]
        L += _tbl([[c["device"], c["system"] or "", c["at"], "; ".join(c["relations"]), ", ".join(c["alarms"]) or "-", c["how_operations_sees_it"]]
                   for c in res["candidate_compensation"]], ["Device", "System", "At", "Relation", "Alarms", "How operations sees it"])
        L += [""]
    L += ["## Required actions", ""]
    actions = ["Confirm the bypass is authorised at the level the site bypass procedure requires and logged in the bypass register.",
               "Brief the panel operator: which SIF(s) are degraded or defeated, which compensating alarms or readings to watch, and the manual response.",
               "Confirm the compensating alarms are not shelved or suppressed and are at the required priority.",
               "Define the field round interval for any manual-only measure and record readings.",
               f"Limit the bypass to the authorised duration{(' (' + duration + ')') if duration else ''}; extend only by re-assessment.",
               "On removal: restore the SIF, confirm no forces or overrides remain, proof test where required, close the register entry."]
    if worst == "DEFEATED":
        actions.insert(0, "A SIF is DEFEATED while this element is out of service: obtain the higher authorisation level your procedure requires and confirm the process can stay within its operating envelope with the measures listed, or bring it to a safe state.")
    L += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
    L += ["", "_IEC 61511-1 clause 11 (design) and clause 16 (operation and maintenance) require compensating measures while a SIF is bypassed, "
          "authorisation, time limits and operator awareness. Confirm sub-clause references against the edition in force on the project._", ""]
    return "\n".join(L)


def _cm_section(cms: list[dict]) -> list[str]:
    if not cms:
        return ["**No curated compensating measure for this SIF.** A measure or an alternative safeguard must be defined before the bypass is authorised.", ""]
    L = ["Curated compensating measures:", ""]
    for m in sorted(cms, key=lambda m: (m["rank"] or 99)):
        flag = "" if m["validity"] == "valid" else f"  **{m['validity']}**"
        L.append(f"- {m['rank'] or '-'}. {m['alarm']} ({m['basis']}){flag}. Conditions: {m['conditions'] or '-'} [curated by {m['curated_by']} {m['curated_on'] or ''}]")
    return L + [""]


def handover_markdown(status: dict, unit: str) -> str:
    L = [f"# Shift Handover - Protection Status - {unit}", "",
         f"As of {status['as_of']}, generated from the pid_graph knowledge graph and the out-of-service register.", ""]
    worst = "DEFEATED" if any(s["status"] == "DEFEATED" for s in status["sifs"]) else ("DEGRADED" if any(s["status"] == "DEGRADED" for s in status["sifs"]) else "ALL SIFs UNAFFECTED")
    L += [f"**Headline:** {worst}. {len(status["out_of_service"])} element(s) out of service.", "", "## Out of service now", ""]
    if status["out_of_service"]:
        L += _tbl([[n["oos_id"], n["kind"], n["id"], n["start"] or "", (("EXPIRED " if n["expired"] else "") + (n["expiry"] or "-") + (f" ({n['expires_within_h']} h)" if n["expires_within_h"] is not None and 0 <= n["expires_within_h"] <= 24 else "")),
                    n["authorised_by"] or "", n["reason"] or "", "yes" if n["cm_confirmed"] else "NO"] for n in status["out_of_service"]],
                  ["Ref", "Kind", "Element", "Since", "Expiry", "Authorised by", "Reason", "CM confirmed"])
    else:
        L.append("Nothing out of service.")
    L += ["", "## Safety functions", ""]
    L += _tbl([[s["sif"], s["sil"], s["description"], s["status"], s["detail"] or "-", ", ".join(m["alarm"] for m in s["measures_valid"]) or ("-" if s["status"] == "UNAFFECTED" else "NONE"),
                "; ".join(s["flags"]) or "-"] for s in status["sifs"]], ["SIF", "SIL", "Function", "Status", "Detail", "Valid compensating measures", "Flags"])
    L += ["", "## Attention this shift", ""]
    items = [f"- **{s['sif']}**: {f}" for s in status["sifs"] for f in s["flags"]]
    items += [f"- {n['oos_id']} {n['kind']} {n['id']} " + ("has **EXPIRED** - restore or re-authorise" if n["expired"] else f"expires in {n['expires_within_h']} h - plan restoration or re-assessment") for n in status["expiring_24h"] + [x for x in status["expired"] if x not in status["expiring_24h"]]]
    items += [f"- **{n['oos_id']} {n['id']}**: compensating measures not confirmed in the register" for n in status["out_of_service"] if not n["cm_confirmed"]]
    L += items or ["- Nothing requiring attention."]
    return "\n".join(L) + "\n"


def trip_pack_markdown(driver, data: dict, sif_id: str, status: dict) -> str:
    s = next((x for x in data["sifs"] if x["sif"] == sif_id.upper()), None)
    if not s:
        return f"# Trip Investigation Pack - {sif_id}\n\nSIF not in graph.\n"
    st = next((x for x in status["sifs"] if x["sif"] == s["sif"]), {})
    oos = {n["id"]: n for n in status["out_of_service"]}
    state = lambda ident: (f"{oos[ident]['kind']} {oos[ident]['oos_id']}" if ident in oos else "in service")
    pre = _run(driver, "MATCH (i:Instrument)-[:INITIATES]->(:SIF {sif_id: $sif}) MATCH (i)-[:GENERATES]->(a:Alarm) "
                       "RETURN a.alarm_id AS alarm, i.tag AS on, a.setpoint AS sp, a.priority AS pri ORDER BY alarm", sif=s["sif"])
    nearby = _run(driver, "MATCH (i:Instrument)-[:INITIATES]->(:SIF {sif_id: $sif}) MATCH (i)-[m1:MEASURES]->(loc)<-[m2:MEASURES]-(o:Instrument) "
                          "WHERE " + Q.trusted_rel("m1") + " AND " + Q.trusted_rel("m2") + " AND " + Q.trusted_rel("loc") + " AND NOT (o)-[:INITIATES]->(:SIF {sif_id: $sif}) AND NOT coalesce(o.stub, false) MATCH (o)-[:GENERATES]->(a:Alarm) "
                          "RETURN DISTINCT a.alarm_id AS alarm, o.tag AS device, o.system AS system, coalesce(loc.tag, loc.segment_id, loc.line_no) AS at, a.setpoint AS sp ORDER BY alarm", sif=s["sif"])
    casc = _run(driver, "MATCH (s:SIF {sif_id: $sif}) OPTIONAL MATCH (s)-[:CASCADES_TO]->(t:SIF) OPTIONAL MATCH (u:SIF)-[:CASCADES_TO]->(s) "
                        "RETURN collect(DISTINCT t.sif_id) AS to, collect(DISTINCT u.sif_id) AS frm", sif=s["sif"])[0]
    L = [f"# Trip Investigation Pack - {s['sif']}", "",
         f"{s['description']} | SIL {s['sil']} | logic solver {s['logic_solver'] or '?'} | protects {', '.join(s['protects']) or '?'} | "
         f"generated {date.today().isoformat()} from the pid_graph knowledge graph | source {', '.join(s['documents'])}", "",
         f"**Protection status at generation:** {st.get('status', '?')}{(' - ' + st['detail']) if st.get('detail') else ''}. "
         "Fill in the event time, the first-out indication and the sequence-of-events record before working through the checklist.", "",
         "## 1. What can cause this trip", ""]
    L += _tbl([[i["tag"] + (" (NOT IN INDEX)" if i["stub"] else ""), i["service"] or "", i["system"] or "", i["voting"] or "1oo1", i["setpoint"] or "?",
                ", ".join(i["measures"]) or "?", i["cause"] or "", state(i["tag"])] for i in s["initiators"]],
              ["Initiator", "Service", "System", "Voting", "Trip setpoint", "Measures", "Cause", "State now"])
    for v in s["voting_check"]:
        if v["expected"] is not None:
            L += ["", f"{v['voting']}: the trip needs {VOTING_RE.search(v['voting']).group(1)} of {v['expected']} channels to vote"
                  + (f" - **but the C&E lists {v['listed']} channels (register X10); confirm the real architecture before concluding which channels voted**" if v["listed"] != v["expected"] else "") + "."]
    L += ["", "## 2. What should have preceded it", ""]
    L += _tbl([[p["alarm"], p["on"], p["sp"] or "?", p["pri"] or "?", state(p["alarm"])] for p in pre], ["Pre-alarm", "On initiator", "Setpoint", "Priority", "State now"]) if pre else \
         ["No alarm is generated by any initiator of this SIF: there was no pre-alarm from the SIS sensors themselves."]
    if nearby:
        L += ["", "Other alarms on the same measured items (should show the process excursion in the alarm journal):", ""]
        L += _tbl([[x["alarm"], x["device"], x["system"] or "", x["at"], x["sp"] or "?", state(x["alarm"])] for x in nearby], ["Alarm", "On device", "System", "At", "Setpoint", "State now"])
    L += ["", "## 3. What the trip should have done", ""]
    srs = s.get("srs") or {}
    if srs.get("safe_state"):
        L += [f"SRS safe state: **{srs['safe_state']}**; required response time {srs.get('response_time') or '?'} within a process safety time of {srs.get('process_safety_time') or '?'}.", ""]
    L += _tbl([[f["tag"], f["action"] or "?", f["service"] or "", state(f["tag"])] for f in s["final_elements"]], ["Final element", "Expected action", "Service", "State now"])
    L += ["", ("Trip announcement: " + ", ".join(r["alarm"] + ("" if r["in_register"] else " (not in alarm register - confirm it exists on the DCS)") for r in s["raises"]) + " should have annunciated.") if s["raises"] else "No trip-announcing alarm is recorded for this SIF."]
    if casc["to"] or casc["frm"]:
        L += ["", "## 4. Cascade", "", (f"This trip initiates: {', '.join(casc['to'])}. " if casc["to"] else "") + (f"This SIF can be initiated by: {', '.join(casc['frm'])} - check whether the trip was a consequence rather than a cause." if casc["frm"] else "")]
    checklist = ["Event time and first-out indication from the sequence-of-events recorder / logic solver diagnostics.",
                 "Which initiator channel(s) voted? Compare each channel's trend against its trip setpoint at the event time.",
                 "Was any channel overridden, bypassed or in fault at the time? Compare with the out-of-service register (states above are as of generation).",
                 "Did the process actually reach the trip condition (genuine demand), or was it a spurious trip (sensor, wiring, logic)? Compare SIS channels with the BPCS measurements in section 2.",
                 "Did every final element reach its expected state within its stroke time? Record valve position feedback.",
                 "Was the trip annunciated to the operator (section 3)? Was the pre-alarm (section 2) acknowledged before the trip?",
                 "Record the demand in the SIF demand log; a genuine demand feeds the SIL verification demand rate.",
                 "Before reset: root cause understood, initiators healthy, final elements proven, authorisation per procedure."]
    L += ["", "## 5. Investigation checklist", ""] + [f"{i}. {c}" for i, c in enumerate(checklist, 1)]
    L += ["", "## 6. Documents", ""] + _tbl([[d["doc_no"], d["rev"], d["doc_type"], d["title"] or ""] for d in data["documents"]], ["Document", "Rev", "Type", "Title"])
    ids = {s["sif"]} | {i["tag"] for i in s["initiators"]} | {f["tag"] for f in s["final_elements"]} | {r["alarm"] for r in s["raises"]}
    ex = [e for e in data["register"]["exceptions"] if e["id"] in ids]
    if ex:
        L += ["", "## 7. Data caveats (exception register)", ""] + _tbl([[e["code"], e["id"], e["detail"]] for e in ex], ["Code", "Node", "Detail"])
    return "\n".join(L) + "\n"


# ---- markdown -> docx --------------------------------------------------------------------

def md_to_docx(md: str, out: Path) -> Path:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            header = [c.strip() for c in ln.strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            t = doc.add_table(rows=1, cols=len(header))
            t.style = "Light Grid Accent 1"
            for j, h in enumerate(header):
                t.rows[0].cells[j].text = h
            for r in rows:
                cells = t.add_row().cells
                for j, c in enumerate(r[:len(header)]):
                    cells[j].text = _plain(c)
            doc.add_paragraph()
            continue
        if ln.startswith("# "):
            doc.add_heading(_plain(ln[2:]), 0)
        elif ln.startswith("## "):
            doc.add_heading(_plain(ln[3:]), 1)
        elif ln.startswith("### "):
            doc.add_heading(_plain(ln[4:]), 2)
        elif ln.startswith("- "):
            _rich(doc.add_paragraph(style="List Bullet"), ln[2:])
        elif re.match(r"^\d+\. ", ln):
            _rich(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", ln))
        elif ln.strip() == "---":
            doc.add_paragraph().add_run("_" * 60)
        elif ln.strip():
            _rich(doc.add_paragraph(), ln)
        i += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    return out


def _plain(s: str) -> str:
    return re.sub(r"[*_]{1,2}(.+?)[*_]{1,2}", r"\1", s)


def _rich(par, s: str) -> None:
    pos = 0
    for m in re.finditer(r"\*\*(.+?)\*\*|_(.+?)_", s):
        if m.start() > pos:
            par.add_run(s[pos:m.start()])
        if m.group(1):
            par.add_run(m.group(1)).bold = True
        else:
            par.add_run(m.group(2)).italic = True
        pos = m.end()
    if pos < len(s):
        par.add_run(s[pos:])


# ---- CLI -----------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["compensating-measures", "bypass", "handover", "trip-pack"])
    ap.add_argument("tag", nargs="?", help="tag for bypass, SIF id for trip-pack")
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--duration", default="")
    ap.add_argument("--requester", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(argv)
    driver = get_driver()
    try:
        data = gather_unit(driver, a.unit)
        if a.kind == "compensating-measures":
            md = cm_markdown(data)
            base = Path(a.out) / f"CM_register_{a.unit}"
        elif a.kind == "handover":
            from .oos import protection_status
            md = handover_markdown(protection_status(driver), a.unit)
            base = Path(a.out) / f"handover_{a.unit}"
        elif a.kind == "trip-pack":
            if not a.tag:
                ap.error("trip-pack needs a SIF id")
            from .oos import protection_status
            md = trip_pack_markdown(driver, data, a.tag, protection_status(driver))
            base = Path(a.out) / f"trip_pack_{a.tag.upper()}"
        else:
            if not a.tag:
                ap.error("bypass needs a tag")
            res = Q.out_of_service(driver, a.tag)
            md = bypass_markdown(res, data, a.duration, a.requester, a.reason)
            base = Path(a.out) / f"bypass_{a.tag.upper()}"
    finally:
        driver.close()
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    md_to_docx(md, base.with_suffix(".docx"))
    print(base.with_suffix(".md"))
    print(base.with_suffix(".docx"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
