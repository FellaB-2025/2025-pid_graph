"""Fixed templates for the segment-topology questions CQ14-CQ18 (PIDKG_UPGRADE.md, Phase 7).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

    CQ14 isolation(tag)          valves, tagged or not, between an instrument's tap and the next equipment, each way
    CQ15 same_pressure(tag)      other instruments sensing a segment reachable without crossing an actuated or
                                 normally-closed valve. Candidates for curation only; nothing is ever written.
    CQ16 blast_radius(id)        everything downstream of a valve or segment up to the next equipment, and every
                                 loop and SIF that touches it
    CQ17 loop_membership(tag)    for a final element: its loop, its sensor, and the segment the sensor measures
    CQ18 drawing_vs_ce()         drawn trip signals with no C&E cause and effect, and C&E pairs with no drawn trip

Each template is written once, over a handful of backend primitives. Every primitive has two
forms that must return the same rows: Cypher for Neo4j, and a walk over the in-memory store.
Pass a Neo4j driver or a store as the first argument; the answer has the same shape either way.

Trust rule T7. CQ14-CQ17 are safety-relevant: by default they use trusted facts only
(extracted_by table / manual / pid_audit, or review = accepted), on every relationship and
every node they touch, and report how many vision facts were left out. With
include_pending=True they use everything and their header says EXPLORATION ONLY. CQ18 is a
consistency check on what has been drawn, so it reads pending facts by default, and says so.

    python -m pid_graph.topology_queries isolation PT-1001A
    python -m pid_graph.topology_queries same_pressure PT-1001A --include-pending
    python -m pid_graph.topology_queries blast_radius XV-1001 --backend memory --pidkg tests/fixtures/pidkg_U-100/graph.json
    python -m pid_graph.topology_queries drawing_vs_ce            add --json for machine-readable output

Limits, stated rather than hidden: paths are followed for at most 40 relationships; CQ15 treats
equipment as part of the pressure system (it walks through a vessel) and does not know about
pumps, compressors or check valves; a manual valve with no stated position is taken as open.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import ontology as O
from .queries import trusted_rel

MAX_HOPS = 40
BASIS_TRUSTED = "trusted facts only (T7): vision facts that are pending or rejected are not used"
BASIS_ALL = "EXPLORATION ONLY: includes vision facts that are review=pending or rejected; not a source for safety-relevant answers"
CQ15_HEADING = "candidates for curation — not compensating measures"
VALVE_ROLES = ("final_element", "manual_valve")
KEY_OF = {"Segment": "segment_id", "Instrument": "tag", "InlineItem": "item_id", "Equipment": "tag"}
# What a walk may not pass through (it may still end there).
STOP_AT_EQUIPMENT = "equipment"            # CQ14, CQ16: up to the next equipment
STOP_AT_BLOCKING_VALVE = "blocking_valve"  # CQ15: an actuated valve, or an untagged valve drawn normally closed


def _blocks(label: str, props: dict, stop: str) -> bool:
    if stop == STOP_AT_EQUIPMENT:
        return label == "Equipment"
    return (label == "Instrument" and props.get("role") == "final_element") or \
           (label == "InlineItem" and props.get("normal_position") == "closed")


# ---- backend: Neo4j -------------------------------------------------------------------
class _Neo:
    def __init__(self, driver, include_pending: bool):
        self.d, self.all = driver, include_pending

    def g(self, var: str) -> str:
        """The T7 predicate for one variable, or nothing at all when exploring."""
        return "true" if self.all else trusted_rel(var)

    def _path(self, p: str) -> str:
        return "true" if self.all else (f"all(r_ IN relationships({p}) WHERE {trusted_rel('r_')}) "
                                        f"AND all(n_ IN nodes({p}) WHERE {trusted_rel('n_')})")

    def _run(self, cypher: str, **params) -> list[dict]:
        from .db import DATABASE
        with self.d.session(database=DATABASE) as s:
            return [r.data() for r in s.run(cypher, **params)]

    def left_out(self) -> int:
        if self.all:
            return 0
        rows = self._run("MATCH (n) WHERE n.extracted_by = 'pidkg_vision' AND coalesce(n.review, '') <> 'accepted' RETURN count(n) AS c "
                         "UNION ALL MATCH ()-[e]->() WHERE e.extracted_by = 'pidkg_vision' AND coalesce(e.review, '') <> 'accepted' RETURN count(e) AS c")
        return sum(r["c"] for r in rows)

    def kind_of(self, ident: str) -> list[dict]:
        return self._run(f"MATCH (n) WHERE (n:Instrument AND n.tag = $id) OR (n:Segment AND n.segment_id = $id) OR (n:InlineItem AND n.item_id = $id) "
                         f"WITH n WHERE {self.g('n')} RETURN labels(n)[0] AS label, n.type AS type, n.role AS role, n.system AS system", id=ident)

    def taps(self, tag: str) -> list[str]:
        return [r["s"] for r in self._run(f"MATCH (x:Instrument {{tag: $tag}})-[m:MEASURES]->(s:Segment) WHERE {self.g('m')} AND {self.g('s')} "
                                          "RETURN DISTINCT s.segment_id AS s", tag=tag)]

    def is_in_line(self, label: str, ident: str) -> bool:
        key = KEY_OF[label]
        rows = self._run(f"MATCH (x:{label} {{{key}: $id}})-[f:FLOWS_TO]-(y) WHERE {self.g('f')} AND {self.g('y')} RETURN count(f) AS c", id=ident)
        return bool(rows and rows[0]["c"])

    def reach(self, starts: list[tuple], direction: str, stop: str) -> list[dict]:
        if not starts:
            return []
        arrow = {"down": ("-", "->"), "up": ("<-", "-"), "both": ("-", "-")}[direction]
        blocked = "n_:Equipment" if stop == STOP_AT_EQUIPMENT else \
            "(n_:Instrument AND n_.role = 'final_element') OR (n_:InlineItem AND n_.normal_position = 'closed')"
        out = "(v)-[t:FLOWS_TO]->(w)" if direction != "up" else "(v)<-[t:FLOWS_TO]-(w)"
        return self._run(
            "UNWIND $starts AS st "
            "MATCH (s) WHERE (st.label = 'Segment' AND s:Segment AND s.segment_id = st.id) OR (st.label = 'Instrument' AND s:Instrument AND s.tag = st.id) "
            "OR (st.label = 'InlineItem' AND s:InlineItem AND s.item_id = st.id) "
            f"MATCH p = (s){arrow[0]}[:FLOWS_TO*1..{MAX_HOPS}]{arrow[1]}(v) "
            f"WHERE {self._path('p')} AND none(n_ IN nodes(p)[1..-1] WHERE {blocked}) "
            "WITH v, min(length(p)) AS hops "
            "RETURN labels(v)[0] AS label, coalesce(v.segment_id, v.item_id, v.tag) AS id, hops, v.role AS role, v.kind AS kind, "
            "v.normal_position AS normal_position, v.line_no AS line_no, "
            f"NOT EXISTS {{ MATCH {out} WHERE {self.g('t')} AND {self.g('w')} }} AS terminal",
            starts=[{"label": a, "id": b} for a, b in starts])

    def measuring(self, segments: list[str]) -> list[dict]:
        return self._run(f"MATCH (o:Instrument)-[m:MEASURES]->(s:Segment) WHERE s.segment_id IN $segs AND {self.g('m')} AND {self.g('s')} "
                         "OPTIONAL MATCH (o)-[:GENERATES]->(a:Alarm) "
                         "RETURN o.tag AS tag, s.segment_id AS segment, s.line_no AS line, o.type AS type, o.system AS system, o.role AS role, "
                         "collect(DISTINCT a.alarm_id) AS alarms", segs=segments)

    def loops_of(self, tags: list[str]) -> list[dict]:
        return self._run(f"MATCH (i:Instrument)-[mo:MEMBER_OF]->(l:ControlLoop) WHERE i.tag IN $tags AND {self.g('mo')} AND {self.g('l')} "
                         "RETURN l.loop_key AS loop, l.loop_type AS loop_type, l.variable AS variable, i.tag AS tag, mo.role AS role", tags=tags)

    def members_of(self, loops: list[str]) -> list[dict]:
        return self._run(f"MATCH (i:Instrument)-[mo:MEMBER_OF]->(l:ControlLoop) WHERE l.loop_key IN $loops AND {self.g('mo')} AND {self.g('l')} "
                         "RETURN l.loop_key AS loop, i.tag AS tag, mo.role AS role", loops=loops)

    def sifs_of(self, tags: list[str]) -> list[dict]:
        return self._run("MATCH (i:Instrument)-[:INITIATES]->(s:SIF) WHERE i.tag IN $tags RETURN s.sif_id AS sif, i.tag AS tag, 'initiator' AS as "
                         "UNION MATCH (s:SIF)-[:ACTUATES]->(i:Instrument) WHERE i.tag IN $tags RETURN s.sif_id AS sif, i.tag AS tag, 'final_element' AS as",
                         tags=tags)

    def index_location(self, tags: list[str]) -> list[dict]:
        return self._run("MATCH (i:Instrument)-[r]->(loc) WHERE i.tag IN $tags AND type(r) IN ['MEASURES', 'INSTALLED_ON'] AND r.extracted_by = 'table' "
                         "RETURN i.tag AS tag, coalesce(loc.tag, loc.line_no) AS at", tags=tags)

    def trip_signals(self) -> list[dict]:
        return self._run(f"MATCH (a:Instrument)-[sg:SIGNAL_TO]->(b) WHERE sg.purpose = 'trip' AND {self.g('sg')} "
                         "RETURN a.tag AS from, b.tag AS to, coalesce(sg.via, '') AS via, sg.source_doc AS sheet, sg.review AS review")

    def ce_pairs(self) -> list[dict]:
        return self._run("MATCH (i:Instrument)-[:INITIATES]->(s:SIF)-[:ACTUATES]->(f:Instrument) RETURN DISTINCT s.sif_id AS sif, i.tag AS from, f.tag AS to")


# ---- backend: in-memory store --------------------------------------------------------------
class _Mem:
    def __init__(self, store, include_pending: bool):
        self.s, self.all = store, include_pending
        self.node = {(n["label"], next(iter(n["key"].values()))): n["props"] for n in store.nodes() if n["label"] != "Document"}
        self.out: dict[tuple, list] = {}
        self.inc: dict[tuple, list] = {}
        for r in store.rels("FLOWS_TO"):
            a, b = self._end(r, "start"), self._end(r, "end")
            if self.ok(r["props"]) and self.ok_node(a) and self.ok_node(b):
                self.out.setdefault(a, []).append(b)
                self.inc.setdefault(b, []).append(a)

    @staticmethod
    def _end(r: dict, which: str) -> tuple:
        return r[f"{which}_label"], next(iter(r[f"{which}_key"].values()))

    def ok(self, props: dict) -> bool:
        return self.all or O.trusted(props)

    def ok_node(self, n: tuple) -> bool:
        return n in self.node and self.ok(self.node[n])

    def left_out(self) -> int:
        if self.all:
            return 0
        hidden = lambda p: p.get("extracted_by") == O.VISION and p.get("review") != "accepted"
        return sum(1 for n in self.s.nodes() if hidden(n["props"])) + sum(1 for r in self.s.rels() if hidden(r["props"]))

    def kind_of(self, ident: str) -> list[dict]:
        return [{"label": lab, "type": self.node[(lab, ident)].get("type"), "role": self.node[(lab, ident)].get("role"),
                 "system": self.node[(lab, ident)].get("system")}
                for lab in ("Instrument", "Segment", "InlineItem") if self.ok_node((lab, ident))]

    def taps(self, tag: str) -> list[str]:
        return sorted({r["end_key"]["segment_id"] for r in self.s.rels("MEASURES")
                       if r["start_key"].get("tag") == tag and r["end_label"] == "Segment" and self.ok(r["props"]) and self.ok_node(self._end(r, "end"))})

    def is_in_line(self, label: str, ident: str) -> bool:
        return bool(self.out.get((label, ident)) or self.inc.get((label, ident)))

    def reach(self, starts: list[tuple], direction: str, stop: str) -> list[dict]:
        starts = [s for s in starts if self.ok_node(s)]
        step = {"down": lambda n: self.out.get(n, []), "up": lambda n: self.inc.get(n, []),
                "both": lambda n: self.out.get(n, []) + self.inc.get(n, [])}[direction]
        dist: dict[tuple, int] = {}
        frontier, hops = list(starts), 0
        while frontier and hops < MAX_HOPS:
            hops += 1
            nxt = []
            for n in frontier:
                if n not in starts and _blocks(n[0], self.node[n], stop):
                    continue                                   # reached, never passed through
                for m in step(n):
                    if m not in dist and m not in starts:
                        dist[m] = hops
                        nxt.append(m)
            frontier = nxt
        onward = self.inc if direction == "up" else self.out
        return [{"label": n[0], "id": n[1], "hops": h, "role": self.node[n].get("role"), "kind": self.node[n].get("kind"),
                 "normal_position": self.node[n].get("normal_position"), "line_no": self.node[n].get("line_no"),
                 "terminal": not onward.get(n)} for n, h in dist.items()]

    def measuring(self, segments: list[str]) -> list[dict]:
        alarms: dict[str, set] = {}
        for r in self.s.rels("GENERATES"):
            alarms.setdefault(r["start_key"]["tag"], set()).add(r["end_key"]["alarm_id"])
        rows = []
        for r in self.s.rels("MEASURES"):
            seg = r["end_key"].get("segment_id")
            if r["end_label"] == "Segment" and seg in segments and self.ok(r["props"]) and self.ok_node(("Segment", seg)):
                tag = r["start_key"]["tag"]
                p = self.node[("Instrument", tag)]
                rows.append({"tag": tag, "segment": seg, "line": self.node[("Segment", seg)].get("line_no"), "type": p.get("type"),
                             "system": p.get("system"), "role": p.get("role"), "alarms": sorted(alarms.get(tag, set()))})
        return rows

    def _members(self) -> list[dict]:
        return [{"loop": r["end_key"]["loop_key"], "tag": r["start_key"]["tag"], "role": r["props"].get("role")}
                for r in self.s.rels("MEMBER_OF") if self.ok(r["props"]) and self.ok_node(("ControlLoop", r["end_key"]["loop_key"]))]

    def loops_of(self, tags: list[str]) -> list[dict]:
        return [{**m, "loop_type": self.node[("ControlLoop", m["loop"])].get("loop_type"), "variable": self.node[("ControlLoop", m["loop"])].get("variable")}
                for m in self._members() if m["tag"] in tags]

    def members_of(self, loops: list[str]) -> list[dict]:
        return [m for m in self._members() if m["loop"] in loops]

    def sifs_of(self, tags: list[str]) -> list[dict]:
        rows = [{"sif": r["end_key"]["sif_id"], "tag": r["start_key"]["tag"], "as": "initiator"} for r in self.s.rels("INITIATES") if r["start_key"]["tag"] in tags]
        rows += [{"sif": r["start_key"]["sif_id"], "tag": r["end_key"]["tag"], "as": "final_element"} for r in self.s.rels("ACTUATES") if r["end_key"]["tag"] in tags]
        return rows

    def index_location(self, tags: list[str]) -> list[dict]:
        return [{"tag": r["start_key"]["tag"], "at": next(iter(r["end_key"].values()))} for t in ("MEASURES", "INSTALLED_ON") for r in self.s.rels(t)
                if r["start_key"]["tag"] in tags and r["props"].get("extracted_by") == "table"]

    def trip_signals(self) -> list[dict]:
        return [{"from": r["start_key"]["tag"], "to": r["end_key"]["tag"], "via": r["props"].get("via", ""), "sheet": r["props"].get("source_doc"),
                 "review": r["props"].get("review")} for r in self.s.rels("SIGNAL_TO") if r["props"].get("purpose") == "trip" and self.ok(r["props"])]

    def ce_pairs(self) -> list[dict]:
        acts: dict[str, set] = {}
        for r in self.s.rels("ACTUATES"):
            acts.setdefault(r["start_key"]["sif_id"], set()).add(r["end_key"]["tag"])
        return [{"sif": sif, "from": i, "to": f} for sif, i in sorted({(r["end_key"]["sif_id"], r["start_key"]["tag"]) for r in self.s.rels("INITIATES")})
                for f in sorted(acts.get(sif, set()))]


def _backend(src, include_pending: bool):
    return _Neo(src, include_pending) if hasattr(src, "session") else _Mem(src, include_pending)


def exercise_all_primitives(src, include_pending: bool) -> None:
    """Call every backend primitive once. For the test that checks no Cypher text escapes the T7 gate."""
    b = _backend(src, include_pending)
    b.left_out(), b.kind_of("X"), b.taps("X"), b.is_in_line("Instrument", "X"), b.is_in_line("InlineItem", "X")
    for direction in ("down", "up", "both"):
        for stop in (STOP_AT_EQUIPMENT, STOP_AT_BLOCKING_VALVE):
            b.reach([("Segment", "X")], direction, stop)
    b.measuring(["X"]), b.loops_of(["X"]), b.members_of(["X"]), b.sifs_of(["X"]), b.index_location(["X"]), b.trip_signals(), b.ce_pairs()


# ---- the templates, written once ---------------------------------------------------------------
def _head(cq: str, b, **first) -> dict:
    return {"cq": cq, **first, "basis": BASIS_ALL if b.all else BASIS_TRUSTED, "vision_facts_left_out": b.left_out()}


def _by_hops(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["hops"], r["label"], str(r["id"])))


def _is_valve(r: dict) -> bool:
    return (r["label"] == "Instrument" and r.get("role") in VALVE_ROLES) or (r["label"] == "InlineItem" and "valve" in str(r.get("kind") or ""))


def _side(rows: list[dict], me: str) -> dict:
    rows = [r for r in _by_hops(rows) if r["id"] != me]
    return {"valves": [{"id": r["id"], "label": r["label"], "kind": r["role"] if r["label"] == "Instrument" else r["kind"],
                        "normal_position": r.get("normal_position") or "", "hops": r["hops"]} for r in rows if _is_valve(r)],
            "ends_at": sorted(r["id"] for r in rows if r["label"] == "Equipment"),
            "open_ends": sorted(r["id"] for r in rows if r["terminal"] and r["label"] != "Equipment")}


def isolation(src, tag: str, include_pending: bool = False) -> dict:
    """CQ14: which valves sit between this instrument's tap and the next equipment, each way?"""
    b, tag = _backend(src, include_pending), tag.upper()
    out = _head("CQ14", b, tag=tag)
    if not [k for k in b.kind_of(tag) if k["label"] == "Instrument"]:
        return {**out, "error": "not in graph"}
    taps = sorted(b.taps(tag))
    in_line = b.is_in_line("Instrument", tag)
    starts = [("Segment", s) for s in taps] + ([("Instrument", tag)] if in_line else [])
    out.update({"taps": taps, "in_line": in_line,
                "upstream": _side(b.reach(starts, "up", STOP_AT_EQUIPMENT), tag), "downstream": _side(b.reach(starts, "down", STOP_AT_EQUIPMENT), tag)})
    if not starts:
        out["note"] = ("not placed on a segment by the facts used: no isolation can be read from the graph. "
                       + ("Vision facts for it may be awaiting review." if not b.all else "Vision did not tap it onto a line."))
    return out


def same_pressure(src, tag: str, include_pending: bool = False) -> dict:
    """CQ15: other instruments sensing a segment reachable from this sensor without crossing an actuated or closed valve."""
    b, tag = _backend(src, include_pending), tag.upper()
    out = _head("CQ15", b, tag=tag, heading=CQ15_HEADING)
    me = [k for k in b.kind_of(tag) if k["label"] == "Instrument"]
    if not me:
        return {**out, "error": "not in graph"}
    taps = sorted(b.taps(tag))
    starts = [("Segment", s) for s in taps] + ([("Instrument", tag)] if b.is_in_line("Instrument", tag) else [])
    reached = b.reach(starts, "both", STOP_AT_BLOCKING_VALVE)
    hops = {s: 0 for s in taps}
    hops.update({r["id"]: r["hops"] for r in reached if r["label"] == "Segment"})
    first = str(me[0].get("type") or "")[:1]
    cands = [{"device": m["tag"], "type": m["type"], "system": m["system"], "role": m["role"], "segment": m["segment"], "line": m["line"],
              "hops": hops[m["segment"]], "same_variable": bool(first) and str(m["type"] or "")[:1] == first, "alarms": sorted(m["alarms"])}
             for m in b.measuring(sorted(hops)) if m["tag"] != tag]
    out.update({"taps": taps, "segments_reached": len(hops),
                "blocked_at": sorted(r["id"] for r in reached if r["id"] != tag and _blocks(r["label"], r, STOP_AT_BLOCKING_VALVE)),
                "candidates": sorted(cands, key=lambda c: (c["hops"], c["device"], c["segment"])),
                "note": "A shortlist for engineering judgement. COMPENSATES_FOR is curated by hand and is never written from here."})
    return out


def blast_radius(src, ident: str, include_pending: bool = False) -> dict:
    """CQ16: everything downstream of a valve or segment up to the next equipment, and every loop and SIF that touches it."""
    b, ident = _backend(src, include_pending), ident.upper()
    out = _head("CQ16", b, id=ident)
    kinds = b.kind_of(ident)
    if not kinds:
        return {**out, "error": "not in graph"}
    label = kinds[0]["label"]
    down = [r for r in _by_hops(b.reach([(label, ident)], "down", STOP_AT_EQUIPMENT)) if r["id"] != ident]
    segments = sorted({r["id"] for r in down if r["label"] == "Segment"} | ({ident} if label == "Segment" else set()))
    affected = sorted({r["id"] for r in down if r["label"] == "Instrument"} | {m["tag"] for m in b.measuring(segments)}
                      | ({ident} if label == "Instrument" else set()))
    loops: dict[str, dict] = {}
    for m in b.loops_of(affected):
        loops.setdefault(m["loop"], {"loop": m["loop"], "loop_type": m["loop_type"], "variable": m["variable"], "touched_by": set()})["touched_by"].add(m["tag"])
    sifs: dict[str, dict] = {}
    for s in b.sifs_of(affected):
        e = sifs.setdefault(s["sif"], {"sif": s["sif"], "initiators": set(), "final_elements": set()})
        e["initiators" if s["as"] == "initiator" else "final_elements"].add(s["tag"])
    out.update({"label": label, "downstream": [{"label": r["label"], "id": r["id"], "hops": r["hops"]} for r in down],
                "ends_at": sorted(r["id"] for r in down if r["label"] == "Equipment"),
                "open_ends": sorted(r["id"] for r in down if r["terminal"] and r["label"] != "Equipment"),
                "instruments_affected": affected,
                "loops": [{**v, "touched_by": sorted(v["touched_by"])} for _, v in sorted(loops.items())],
                "sifs": [{"sif": k, "initiators": sorted(v["initiators"]), "final_elements": sorted(v["final_elements"])} for k, v in sorted(sifs.items())]})
    return out


def loop_membership(src, tag: str, include_pending: bool = False) -> dict:
    """CQ17: for a final element - its loop, its sensor, and the segment the sensor measures."""
    b, tag = _backend(src, include_pending), tag.upper()
    out = _head("CQ17", b, tag=tag)
    if not [k for k in b.kind_of(tag) if k["label"] == "Instrument"]:
        return {**out, "error": "not in graph"}
    mine = {m["loop"]: m for m in b.loops_of([tag])}
    members = b.members_of(sorted(mine))
    sensors = sorted({m["tag"] for m in members if m["role"] == "sensor"})
    where: dict[str, set] = {}
    for loc in b.index_location(sensors):
        where.setdefault(loc["tag"], set()).add(loc["at"])
    loops = []
    for key in sorted(mine):
        mem = sorted(({"tag": m["tag"], "role": m["role"]} for m in members if m["loop"] == key), key=lambda m: m["tag"])
        loops.append({"loop": key, "loop_type": mine[key]["loop_type"], "variable": mine[key]["variable"], "members": mem,
                      "sensors": [{"tag": m["tag"], "segments": sorted(b.taps(m["tag"])), "index_location": sorted(where.get(m["tag"], set()))}
                                  for m in mem if m["role"] == "sensor"]})
    out["loops"] = loops
    return out


def drawing_vs_ce(src, include_pending: bool = True) -> dict:
    """CQ18: drawn trip signals with no C&E cause and effect, and C&E cause and effect pairs with no drawn trip."""
    b = _backend(src, include_pending)
    out = _head("CQ18", b)
    drawn = sorted(b.trip_signals(), key=lambda t: (t["from"], t["to"], t["via"]))
    pairs = sorted(b.ce_pairs(), key=lambda p: (p["sif"], p["from"], p["to"]))
    in_ce = {(p["from"], p["to"]) for p in pairs}
    seen = {(t["from"], t["to"]) for t in drawn}
    out.update({"drawn": len(drawn), "ce_pairs": len(pairs),
                "drawn_not_in_ce": [t for t in drawn if (t["from"], t["to"]) not in in_ce],
                "ce_not_drawn": [p for p in pairs if (p["from"], p["to"]) not in seen]})
    return out


TEMPLATES = {"isolation": isolation, "same_pressure": same_pressure, "blast_radius": blast_radius, "loop_membership": loop_membership,
             "drawing_vs_ce": drawing_vs_ce}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", choices=sorted(TEMPLATES))
    ap.add_argument("id", nargs="?", help="tag, segment id or in-line item id (not for drawing_vs_ce)")
    ap.add_argument("--include-pending", action="store_true", help="exploration only: also use vision facts that are not accepted")
    ap.add_argument("--backend", choices=["neo4j", "memory"], default="neo4j")
    ap.add_argument("--pidkg", default="", help="memory backend: the pid-to-kg graph.json to load over the U-100 registers")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.template != "drawing_vs_ce" and not a.id:
        ap.error(f"{a.template} needs an id")
    close = None
    if a.backend == "neo4j":
        from .db import get_driver
        src = get_driver()
        close = src.close
    else:
        from pathlib import Path
        from . import load_pidkg as LP
        from . import review as RV
        from .pipeline import build_store
        root = Path(__file__).resolve().parent.parent
        d = root / "data"
        src, _ = build_store(unit="U-100", index=d / "U100-INST-INDEX-Rev-B.xlsx", ce=d / "U100-CE-CHART-Rev-A.xlsx",
                             topology=d / "pid_audit_U100_topology.csv", pdf=d / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057", load_run="memory")
        if a.pidkg:
            register, _ = RV.read_register(root / "reports" / "review_register_U-100.xlsx")
            LP.apply(src, LP.reconcile(json.loads(Path(a.pidkg).read_text(encoding="utf-8")), LP.index_tags(src), src, unit="U-100",
                                       load_run="memory", review=RV.decisions(register)))
    try:
        fn = TEMPLATES[a.template]
        kw = {"include_pending": True} if a.include_pending else {}
        res = fn(src, **kw) if a.template == "drawing_vs_ce" else fn(src, a.id, **kw)
    finally:
        if close:
            close()
    if a.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        print(f"{res['cq']}  {a.template} {a.id or ''}".rstrip())
        print(f"  {res['basis']}" + (f"  ({res['vision_facts_left_out']} vision facts left out)" if res.get("vision_facts_left_out") else ""))
        for k, v in res.items():
            if k not in ("cq", "basis", "vision_facts_left_out"):
                print(f"  {k}: {json.dumps(v, default=str, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
