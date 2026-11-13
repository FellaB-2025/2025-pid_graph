"""Cross-document checks over the operations documents: codes C1-C26.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The design documents are reconciled by pid_graph.reconcile (X1-X36, frozen at v1.3). These checks compare
what the design says with what is rationalised (MADB), configured and running (configuration export),
calculated (SIL verification) and changed (MOC register), and with the live out-of-service register.
Each check is a fixed rule over the graph, written down in TITLES and RULES below; every finding names
the documents whose claims disagree. Same shape as the exception register (code, title, label, id,
detail, sources, refs) plus `tags`, the identifiers the finding concerns.

Impact rules for C15 (what a change reaches), used by pid_graph.demo as well:
  I1 if the MOC names alarms, the alarms are what change and the other names are context (the alarm's
     source, the SIF it serves); otherwise every element the MOC names is affected;
  I2 an affected instrument's alarms are affected (a re-range moves every alarm on it);
  I3 an affected alarm reaches the documents that credit it (LOPA), rely on it as a compensating measure
     (curated register) or name it in a bypass condition (SRS);
  I4 an affected alarm whose source initiates a SIF reaches that SIF's SRS (the margin to the trip);
  I5 an affected element reaches every document it is shown on or that states a fact about it.
Configuration exports, MOC records and registers of documents are not "documents to revise".

C17-C26 and the unit-aware comparisons in C5, C7, C11 were added after the blind test on U-200
(docs/BLIND_TEST.md, sections 6 and 9). Each is a general rule; none names a unit, a tag or a document.
Values are compared through pid_graph.quantities: 350 mbarg and 0.35 barg are one value; an alarm limit the
configuration gives in per cent of span is converted through the index range before it is compared.

    python -m pid_graph.ops_checks [--unit U-200]   # build the unit from data/ in memory and print the findings
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import quantities as Q
from .records import TrustedView

TITLES = {
    "C1": "Document register names something not in the graph",
    "C2": "Configured point not in the instrument index",
    "C3": "Alarm configured but not rationalised in the MADB",
    "C4": "Alarm rationalised in the MADB but not configured",
    "C5": "Alarm setpoint or priority disagrees between alarm register, MADB and configuration",
    "C6": "Alarm disabled in the configuration with no out-of-service entry",
    "C7": "Configured range disagrees with the instrument index",
    "C8": "Alarm limit at or beyond the end of the instrument's range",
    "C9": "LOPA-credited alarm not recorded as an IPL in the MADB",
    "C10": "SIF architecture disagrees between C&E, SRS, SIL verification and configuration",
    "C11": "SIL verification assumption not met",
    "C12": "Bypass provision disagrees with the SRS",
    "C13": "Maintenance override active with no out-of-service entry",
    "C14": "MOC implemented or closed with documents not revised",
    "C15": "MOC impact list misses documents the graph links to the change",
    "C16": "Alarm on an instrument the index lists as indication only",
    "C17": "SIF trip setpoint as configured disagrees with the C&E or the SRS",
    "C18": "SIL verification target out of date, or achieved risk reduction below the current target",
    "C19": "Operator response time for a credited alarm is longer than the process safety time",
    "C20": "System disagrees between index and configuration, or a SIF device is not on the safety logic solver",
    "C21": "Alarm source disagrees between alarm register, MADB and configuration",
    "C22": "Alarm removed by rationalisation but still configured and enabled",
    "C23": "SIF not covered by a procedure that covers the other SIFs",
    "C24": "Out-of-service entry is past its expiry or does not match the configured state",
    "C25": "Element out of service while its compensating measure or protection credit is also out",
    "C26": "Alarm configured on the wrong side of the trip it stands in front of",
}
# A finding's level is its code's (demo.STOP / demo.WARN) unless the rule gives one: see add(level=...).
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
MAX_H_RE = re.compile(r"max\s*(\d+(?:\.\d+)?)\s*h", re.I)
RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)\s*$", re.I)
VOTE_RE = re.compile(r"(\d)\s*oo\s*(\d)", re.I)
TAG_RE = re.compile(r"\b[A-Z]{1,5}-\d{3,5}[A-Z]?\b")
DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(months?|years?|yr|hours?|hrs?|h)\b", re.I)
CITED_REV_RE = re.compile(r"(\S+)\s+rev\.?\s*(\w+)", re.I)
REMOVED_RE = re.compile(r"\bremov|\bdelet|\bdecommission", re.I)
YES, NO = ("yes", "y", "true", "1"), ("no", "n", "false", "0")
SYSTEM = {"bpcs": "DCS", "dcs": "DCS", "pcs": "DCS", "sis": "SIS", "esd": "SIS"}
NOT_TO_REVISE = ("CFG", "MOC", "REG")
# Sheets of the instrument index that MOCs name as documents of their own.


def sheet_aliases(index_path) -> dict[str, str]:
    """A workbook's sheets can carry document numbers of their own (the alarm register and the loop register inside
    the instrument index). A MOC that names one means the workbook: sheet document number -> workbook document number."""
    from .loaders.tables import detect_document, sheet_names
    if not index_path:
        return {}
    sheets = sheet_names(index_path)
    main = detect_document(index_path, "Instrument Index" if "Instrument Index" in sheets else None)[0]
    out = {}
    for s in sheets:
        d = detect_document(index_path, s)[0]
        if d != main:
            out[d] = main
    return out


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()


def _vote(v) -> str:
    m = VOTE_RE.search(str(v or ""))
    return f"{m.group(1)}oo{m.group(2)}" if m else ""


def _dt(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime((s or "").strip(), fmt)
        except ValueError:
            pass
    return None


def _range(text) -> tuple[float, float] | None:
    m = RANGE_RE.match(str(text or ""))
    return (float(m.group(1)), float(m.group(2))) if m else None


def per_cent_block(ip: dict) -> bool:
    """The index ranges the instrument in engineering units and the configured block is scaled 0-100 % of that span."""
    return (str(ip.get("units_cfg", "")).strip() == "%" and str(ip.get("units", "")).strip() not in ("", "%")
            and _range(ip.get("range_cfg")) == (0.0, 100.0) and _range(ip.get("range")) is not None)


def in_index_units(limit: str, ip: dict) -> str:
    """A limit in per cent of span, restated in the index's units; anything else is returned as it is."""
    q = Q.parse(limit)
    if not (q and q[1] == "%" and per_cent_block(ip)):
        return limit
    lo, hi = _range(ip["range"])
    return f"{lo + q[0] / 100 * (hi - lo):g} {ip['units']}"


def proof_test_intervals(cell: str) -> dict[str, str]:
    """An SRS proof-test cell -> {'sensors': '12 months', 'fe': '24 months'}. One interval with no qualifier
    applies to both; 'Sensors 12 months, final elements 24 months' is two statements."""
    out, default = {}, ""
    for part in re.split(r"[;,]", str(cell or "")):
        m = DURATION_RE.search(part)
        if not m:
            continue
        d = f"{m.group(1)} {m.group(2)}"
        if re.search(r"sensor|initiator|transmitter|input", part, re.I):
            out["sensors"] = d
        elif re.search(r"final|valve|output|actuator", part, re.I):
            out["fe"] = d
        else:
            default = default or d
    return {k: out.get(k) or default for k in ("sensors", "fe") if out.get(k) or default}


def removed(p: dict) -> bool:
    """The alarm database records the alarm as removed (its lifecycle status; the outcome if no status is given)."""
    status = str(p.get("implementation_status") or "")
    return bool(REMOVED_RE.search(status or str(p.get("outcome_madb") or "")))


def trip_notification(p: dict) -> bool:
    return "TRIP" in str(p.get("alarm_type_cfg", "")).upper()


def _sense(p: dict) -> str:
    """'low' or 'high' from the alarm's function letters (PAL, LALL -> low; TAH, PAHH -> high)."""
    f = str(p.get("alarm_type") or "").upper()
    return "low" if f.endswith("L") else "high" if f.endswith("H") else ""


class Graph:
    """Read helpers over a store (or TrustedView) shared by the checks and the demo templates."""

    def __init__(self, store, aliases: dict | None = None):
        self.s = store
        self.aliases = aliases or {}
        self.nodes = {(n["label"], tuple(n["key"].values())[0] if n["label"] != "Document" else n["key"]["doc_no"]): n
                      for n in store.nodes()}
        self.rels = store.rels()
        self.docs = {n["key"]["doc_no"]: n for n in store.nodes("Document")}
        self.alarm_by_tag = {n["props"].get("alarm_tag"): n["key"]["alarm_id"] for n in store.nodes("Alarm") if n["props"].get("alarm_tag")}

    def p(self, label: str, ident: str) -> dict:
        n = self.nodes.get((label, ident))
        return n["props"] if n else {}

    def out(self, rel: str, label: str, ident: str) -> list[dict]:
        return [r for r in self.rels if r["type"] == rel and r["start_label"] == label and _id(r, "start") == ident]

    def inc(self, rel: str, label: str, ident: str) -> list[dict]:
        return [r for r in self.rels if r["type"] == rel and r["end_label"] == label and _id(r, "end") == ident]

    def touching(self, label: str, ident: str) -> list[dict]:
        return [r for r in self.rels if (r["start_label"] == label and _id(r, "start") == ident)
                or (r["end_label"] == label and _id(r, "end") == ident)]

    def documents_of(self, label: str, ident: str) -> dict[str, list[str]]:
        """doc_no -> how the document relates to the element: shown on it, or states a fact about it."""
        out: dict[str, list[str]] = {}
        for r in self.touching(label, ident):
            if r["type"] == "SHOWN_ON":
                d = r["end_key"]["doc_no"]
                out.setdefault(d, []).append(r["props"].get("basis") or "shown on")
            else:
                d = r["props"].get("source_doc", "")
                if d in self.docs:
                    out.setdefault(d, []).append(f"states {r['type']}")
        return {d: sorted(set(v)) for d, v in out.items()}

    def source_of(self, alarm_id: str) -> str:
        r = self.inc("GENERATES", "Alarm", alarm_id)
        return _id(r[0], "start") if r else ""

    def sources_of(self, alarm_id: str) -> dict[str, str]:
        """Which instrument each kind of document says generates the alarm: doc_type -> tag."""
        return {self.doc_type(r["props"].get("source_doc", "")): _id(r, "start") for r in self.inc("GENERATES", "Alarm", alarm_id)}

    def final_elements(self, sif: str, doc_type: str) -> set[str]:
        return {_id(r, "end") for r in self.out("ACTUATES", "SIF", sif) if self.doc_type(r["props"].get("source_doc", "")) == doc_type}

    def places(self, tag: str) -> set[str]:
        return {_id(r, "end") for rel in ("INSTALLED_ON", "MEASURES") for r in self.out(rel, "Instrument", tag)}

    def alarms_of(self, tag: str) -> list[str]:
        return sorted({_id(r, "end") for r in self.out("GENERATES", "Instrument", tag)})

    def initiators(self, sif: str, doc_type: str | None = None) -> dict[str, dict]:
        out = {}
        for r in self.inc("INITIATES", "SIF", sif):
            if doc_type is None or self.docs.get(r["props"].get("source_doc"), {}).get("props", {}).get("doc_type") == doc_type:
                out[_id(r, "start")] = r["props"]
        return out

    def srs_naming(self, alarm_tag: str) -> list[str]:
        """SIFs whose SRS bypass conditions name the alarm by its tag."""
        return sorted(k for (lab, k), n in self.nodes.items() if lab == "SIF" and alarm_tag
                      and re.search(rf"\b{re.escape(alarm_tag)}\b", n["props"].get("bypass_conditions", "")))

    def doc_type(self, doc_no: str) -> str:
        return self.docs.get(doc_no, {}).get("props", {}).get("doc_type", "")

    def export_time(self) -> str:
        return next((d["props"].get("export_time", "") for d in self.docs.values() if d["props"].get("doc_type") == "CFG"), "")


def _id(r: dict, end: str) -> str:
    k = r[f"{end}_key"]
    return k["doc_no"] if "doc_no" in k else next(iter(k.values()))


def moc_impact(g: Graph, moc: str) -> dict:
    """Rules I1-I5: the elements a MOC reaches and the documents they reach, each with the reason."""
    m = g.docs[moc]["props"]
    named = [(r["start_label"], _id(r, "start")) for r in g.inc("SHOWN_ON", "Document", moc)]
    alarms_named = {i for lab, i in named if lab == "Alarm"}
    elements: dict[tuple, str] = {}
    for lab, i in named:
        if alarms_named and lab != "Alarm":
            continue                                                       # I1: context for the alarm that changes
        elements[(lab, i)] = "named in the MOC"
    for lab, i in list(elements):
        if lab == "Instrument":
            for a in g.alarms_of(i):
                elements.setdefault(("Alarm", a), f"alarm on {i} (I2)")
    docs: dict[str, list[str]] = {}

    def reach(d: str, why: str):
        if g.doc_type(d) not in NOT_TO_REVISE and d != moc:
            docs.setdefault(d, []).append(why)
    for (lab, i), _ in elements.items():
        for d, how in g.documents_of(lab, i).items():
            reach(d, f"{g.p(lab, i).get('alarm_tag', i) if lab == 'Alarm' else i}: {', '.join(how)} (I5)")
        if lab == "Alarm":
            tag = g.p("Alarm", i).get("alarm_tag", i)
            for r in g.inc("CREDITS", "Alarm", i):
                reach(r["props"]["source_doc"], f"{tag} credited in {_id(r, 'start')} (I3)")
            for r in g.out("COMPENSATES_FOR", "Alarm", i):
                reach(r["props"]["source_doc"], f"{tag} compensates for {_id(r, 'end')} (I3)")
            for sif in g.srs_naming(tag):
                for d in g.documents_of("SIF", sif):
                    if g.doc_type(d) == "SRS":
                        reach(d, f"{tag} named in the {sif} bypass conditions (I3)")
            src = g.source_of(i)
            for r in g.out("INITIATES", "Instrument", src):
                srs = next((d for d in g.documents_of("SIF", _id(r, "end")) if g.doc_type(d) == "SRS"), None)
                if srs:
                    reach(srs, f"{tag} is on {src}, which initiates {_id(r, 'end')}: check the margin to the trip (I4)")
    listed = {g.aliases.get(d, d) for d in m.get("documents_to_revise", [])}
    return {"moc": moc, "title": m.get("title", ""), "status": m.get("status", ""), "stage": m.get("stage", ""),
            "elements": [{"label": lab, "id": i, "why": w} for (lab, i), w in elements.items()],
            "documents": {d: sorted(set(v)) for d, v in sorted(docs.items())},
            "listed": sorted(listed), "missed": sorted(set(docs) - listed),
            "outstanding": sorted(set(m.get("documents_to_revise", [])) - set(m.get("documents_revised", [])))}


def run(store, oos_rows: list[dict] | None = None, trusted: bool = True, aliases: dict | None = None) -> dict:
    g = Graph(TrustedView(store) if trusted else store, aliases)
    oos_active = {r["element"] for r in (oos_rows or []) if r.get("status") == "active"}
    ex: list[dict] = []

    def add(code, label, ident, detail, sources, refs="", tags=(), level=None):
        ex.append({"code": code, "title": TITLES[code], "label": label, "id": ident, "detail": detail,
                   "sources": sources, "refs": refs, "tags": sorted(set(tags) | {ident}), **({"level": level} if level else {})})

    # C1 is reported by the document-register loader (unresolved names); the demo passes them in.
    instruments = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "Instrument"}
    alarms = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "Alarm"}
    sifs = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "SIF"}

    for tag, p in sorted(instruments.items()):
        if p.get("configured") == "yes" and p.get("stub"):
            what = "maintenance override switch" if p.get("block_type_cfg") == "MOS" else f"{p.get('system_cfg') or 'configured'} point"
            add("C2", "Instrument", tag, f"{tag} is a configured {what} ({p.get('io_channel_cfg') or p.get('controller_cfg') or 'no channel'}) "
                "with no instrument index row.", "configuration vs instrument index", p.get("source_ref", ""))
        if p.get("range_cfg") and p.get("range") and not per_cent_block(p):       # 0-100 % of the index span is a scaling
            a, b = _range(p["range"]), _range(p["range_cfg"])
            ui, uc = p.get("units", ""), p.get("units_cfg", "")
            if (not all(Q.same(f"{x:g} {ui}", f"{y:g} {uc}", numbers_only=True) for x, y in zip(a, b)) if a and b
                    else _norm(p["range"]).replace(" to ", "-") != _norm(p["range_cfg"])):
                add("C7", "Instrument", tag, f"Index range {p['range']} {p.get('units', '')}; configured {p['range_cfg']} {p.get('units_cfg', '')}.",
                    "instrument index vs configuration", p.get("source_ref", ""))

    for aid, p in sorted(alarms.items()):
        tag, src = p.get("alarm_tag", aid), g.source_of(aid)
        has_cfg, has_madb = bool(p.get("setpoint_cfg") or p.get("priority_cfg")), bool(p.get("madb_ref"))
        ip = instruments.get(src, {})
        enabled = _norm(p.get("enabled_cfg")) not in NO
        if has_cfg and not has_madb:
            trip = trip_notification(p)
            extra = (" It is configured as a trip notification: a trip is not an alarm, so this is for information. Whether trip "
                     "notifications are rationalised is for the alarm philosophy to say.") if trip else ""
            add("C3", "Alarm", tag, f"{tag} on {src} is configured ({p.get('setpoint_cfg') or p.get('alarm_type_cfg')}, {p.get('priority_cfg')}) "
                f"but has no MADB record.{extra}", "configuration vs MADB", p.get("cfg_ref", ""), [src], level="info" if trip else None)
        if has_madb and has_cfg and enabled and removed(p):
            add("C22", "Alarm", tag, f"The MADB records {tag} as '{p.get('implementation_status') or p.get('outcome_madb')}' "
                f"(outcome: {p.get('outcome_madb') or 'not stated'}); it is still configured on {g.sources_of(aid).get('CFG', src)} "
                f"at {p.get('setpoint_cfg')} and enabled.", "MADB vs configuration", p.get("cfg_ref", ""), [src])
        if has_madb and not has_cfg and not removed(p):
            add("C4", "Alarm", tag, f"{tag} on {src} is rationalised ({p.get('setpoint_madb')}, {p.get('priority_madb')}, "
                f"{p.get('implementation_status') or 'status not stated'}) but not configured.", "MADB vs configuration", p.get("madb_ref", ""), [src])
        for what, keys in (("setpoint", ("setpoint", "setpoint_madb", "setpoint_cfg")), ("priority", ("priority", "priority_madb", "priority_cfg"))):
            stated = {k: p[k] for k in keys if p.get(k)}
            if what == "setpoint":
                differ = len(stated) > 1 and not Q.all_same(in_index_units(v, ip) for v in stated.values())
            else:
                differ = len({_norm(v) for v in stated.values()}) > 1
            if differ:
                names = {keys[0]: "alarm register", keys[1]: "MADB", keys[2]: "configuration"}
                add("C5", "Alarm", tag, f"{tag} {what}: " + "; ".join(
                    f"{names[k]} {v}" + (f" (= {in_index_units(v, ip)} of the {ip.get('range')} {ip.get('units')} span)" if in_index_units(v, ip) != v else "")
                    for k, v in stated.items()) + ".",
                    " vs ".join(names[k] for k in stated), p.get("cfg_ref", ""), [src])
        if not enabled and aid not in oos_active and tag not in oos_active:
            add("C6", "Alarm", tag, f"{tag} is disabled in the configuration; the out-of-service register has no active entry for it. "
                f"MADB status: {p.get('implementation_status') or 'no record'}.", "configuration vs out-of-service register", p.get("cfg_ref", ""), [src])
        rng = ip.get("range_cfg") or ip.get("range") or ""
        units = ip.get("units_cfg") or ip.get("units")
        lim = p.get("setpoint_cfg") or p.get("setpoint_madb") or p.get("setpoint")
        m = RANGE_RE.match(str(rng))
        if lim and m and units and units in lim:
            lo, hi, v = float(m.group(1)), float(m.group(2)), float(NUM_RE.findall(lim)[0])
            if v >= hi or v <= lo:
                add("C8", "Alarm", tag, f"{tag} at {lim} on {src}, whose range is {rng} {units}: the alarm sits at the end of the span "
                    "and cannot be relied on to annunciate.", "configuration vs MADB / alarm register", p.get("cfg_ref", ""), [src])
        if "indication only" in _norm(ip.get("remarks")):
            add("C16", "Alarm", tag, f"{tag} is on {src}, which the instrument index lists as indication only.",
                "instrument index vs MADB / configuration", p.get("madb_ref") or p.get("cfg_ref", ""), [src])
        for r in g.inc("CREDITS", "Alarm", aid):
            if _norm(p.get("ipl_credit")) not in ("yes", "y") or _norm(p.get("alarm_class")) not in ("safety", "ipl", "safety / ipl"):
                add("C9", "Alarm", tag, f"{_id(r, 'start')} credits {tag} as an IPL (PFD {r['props'].get('pfd', '?')}); the MADB records "
                    f"IPL credit '{p.get('ipl_credit') or 'none'}' and class '{p.get('alarm_class') or 'none'}'.", "LOPA vs MADB",
                    r["props"].get("source_ref", ""), [src])

    for sif, p in sorted(sifs.items()):
        ce, cfg = g.initiators(sif, "CE"), g.initiators(sif, "CFG")
        views = {"C&E": ({_vote(v.get("voting")) for v in ce.values()}, set(ce)),
                 "configuration": ({_vote(v.get("voting")) for v in cfg.values()}, set(cfg)),
                 "SIL verification": ({_vote(p.get("sensor_voting_silv"))}, {t.strip() for t in p.get("sensor_tags_silv", "").split(",") if t.strip()}),
                 "SRS": ({_vote(p.get("sensor_architecture"))}, None)}
        views = {k: v for k, v in views.items() if v[0] - {""}}
        votes = {k: "/".join(sorted(v[0] - {""})) for k, v in views.items()}
        sets = {k: v[1] for k, v in views.items() if v[1]}
        if len(set(votes.values())) > 1 or len({frozenset(s) for s in sets.values()}) > 1:
            add("C10", "SIF", sif, "; ".join(f"{k}: {votes[k]}" + (f" on {', '.join(sorted(sets[k]))}" if k in sets else "") for k in views) + ".",
                " vs ".join(views), p.get("cfg_ref", "") or p.get("silv_ref", ""), set().union(*sets.values()) if sets else ())
        # C10, final elements: the same comparison as the sensors, across the same four documents
        fe = {"C&E": g.final_elements(sif, "CE"), "configuration": g.final_elements(sif, "CFG"),
              "SIL verification": {t.strip() for t in p.get("fe_tags_silv", "").split(",") if t.strip()},
              "SRS": set(TAG_RE.findall(p.get("fe_architecture", "")))}
        fe = {k: v for k, v in fe.items() if v}
        fe_votes = {k: v for k, v in (("SIL verification", _vote(p.get("fe_voting_silv"))), ("SRS", _vote(p.get("fe_architecture")))) if v}
        if len({frozenset(v) for v in fe.values()}) > 1 or len(set(fe_votes.values())) > 1:
            add("C10", "SIF", sif, "Final elements - " + "; ".join(
                f"{k}: {(fe_votes[k] + ' on ') if k in fe_votes else ''}{', '.join(sorted(fe[k])) if k in fe else 'not listed'}"
                for k in ("C&E", "SRS", "SIL verification", "configuration") if k in fe or k in fe_votes) + ".",
                " vs ".join(k for k in ("C&E", "SRS", "SIL verification", "configuration") if k in fe or k in fe_votes),
                p.get("cfg_ref", "") or p.get("silv_ref", ""), set().union(*fe.values()) if fe else ())
        # C17: the trip setpoint as configured, against the C&E and the SRS (SRS against C&E alone is X16)
        sp = {"C&E": sorted({v.get("setpoint") for v in ce.values() if v.get("setpoint")}),
              "SRS": [p["setpoint_srs"]] if p.get("setpoint_srs") else [],
              "configuration": sorted({v.get("setpoint") for v in cfg.values() if v.get("setpoint")})}
        if sp["configuration"] and any(not Q.same(c, o) for c in sp["configuration"] for k in ("C&E", "SRS") for o in sp[k]):
            add("C17", "SIF", sif, f"{sif} trips at " + "; ".join(f"{k}: {' / '.join(v)}" for k, v in sp.items() if v)
                + ". The configured value is what the plant does.", " vs ".join(k for k, v in sp.items() if v),
                p.get("cfg_ref", "") or p.get("srs_ref", ""), set(cfg) | set(ce))
        # C18: the calculation's own target and source, against the requirement as it stands now
        if p.get("silv_ref"):
            said = []
            cited = CITED_REV_RE.search(p.get("target_source_silv", ""))
            if cited and cited.group(1) in g.docs:
                revs = {n["key"]["rev"] for n in g.s.nodes("Document") if n["key"]["doc_no"] == cited.group(1)} - {"UNKNOWN"}
                if revs and cited.group(2) not in revs:
                    said.append(f"it cites {cited.group(1)} Rev {cited.group(2)}; the current revision is {', '.join(sorted(revs))}")
            num = lambda v: float(NUM_RE.findall(str(v))[0]) if NUM_RE.findall(str(v or "")) else None      # noqa: E731
            now_req = {"SRS": num(p.get("rrf_target"))}
            for r in g.inc("CREDITS", "SIF", sif):
                now_req[f"LOPA {_id(r, 'start')}"] = num(r["props"].get("required_rrf"))
            now_req = {k: v for k, v in now_req.items() if v is not None}
            took, got = num(p.get("rrf_target_silv")), num(p.get("rrf_achieved_silv"))
            if took is not None and now_req.get("SRS") is not None and took != now_req["SRS"]:      # the SRS is the source it cites
                said.append(f"it took a risk reduction target of {took:g}; the requirement now is "
                            + ", ".join(f"{v:g} ({k})" for k, v in now_req.items()))
            if got is not None and now_req and got < max(now_req.values()):
                said.append(f"it achieves {got:g}, below the {max(now_req.values()):g} now required, although its result reads "
                            f"'{p.get('result_silv') or 'not stated'}'")
            if said:
                add("C18", "SIF", sif, f"SIL verification of {sif}: " + "; ".join(said) + ".", "SIL verification vs SRS / LOPA", p.get("silv_ref", ""))
        if p.get("silv_ref"):
            for t in sorted(sets.get("SIL verification", set())):
                ip = instruments.get(t)
                if ip is None or ip.get("configured") != "yes":
                    add("C11", "SIF", sif, f"The SIL verification credits {t} in the {p.get('sensor_voting_silv')} sensor group; {t} is "
                        f"{'not in the graph (not installed)' if ip is None else 'not configured in the SIS'}. "
                        f"Achieved figures (PFDavg {p.get('pfd_avg_silv')}, RRF {p.get('rrf_achieved_silv')}) rest on it.",
                        "SIL verification vs configuration / index", p.get("silv_ref", ""), [t])
            srs_pti = proof_test_intervals(p.get("proof_test_interval", ""))
            for which in ("sensors", "fe"):
                silv, srs = p.get(f"pti_{which}_silv"), srs_pti.get(which) or p.get("proof_test_interval")
                if silv and srs and not Q.same(silv, srs):
                    add("C11", "SIF", sif, f"The SIL verification takes a proof-test interval of {silv} for the "
                        f"{'final elements' if which == 'fe' else 'sensors'}; the SRS specifies {p['proof_test_interval']}.",
                        "SIL verification vs SRS", p.get("silv_ref", ""), [t.strip() for t in p.get(f"{'fe' if which == 'fe' else 'sensor'}_tags_silv", "").split(",")])
            assumed = _vote(p.get("degraded_sensor_voting_silv"))
            for t, ip in sorted(instruments.items()):
                if ip.get("override_sif") == sif and ip.get("override_switch") and not ip.get("block_type_cfg") == "MOS":
                    got = _vote(ip.get("override_degraded_voting"))
                    if assumed and got and got != assumed:
                        add("C11", "SIF", sif, f"The SIL verification assumes {sif} degrades to {assumed} when one sensor is overridden; "
                            f"{ip['override_switch']} on {t} is configured to degrade it to {got}.", "SIL verification vs configuration",
                            ip.get("override_ref", ""), [t, ip["override_switch"]])
        srs_max = MAX_H_RE.search(p.get("bypass_conditions", ""))
        if srs_max:
            inits = set(cfg) or set(ce)
            covered = {t for t in inits if instruments.get(t, {}).get("override_switch")}
            if inits - covered:
                add("C12", "SIF", sif, f"The SRS permits a bypass of {sif} ({p['bypass_conditions']}); no maintenance override is configured on "
                    f"{', '.join(sorted(inits - covered))}. A bypass would have to be made by forcing.", "SRS vs configuration",
                    p.get("srs_ref", ""), inits - covered)
            for t in sorted(covered):
                ip = instruments[t]
                mh = NUM_RE.findall(str(ip.get("override_max_h", "")))
                if mh and float(mh[0]) > float(srs_max.group(1)):
                    add("C12", "Instrument", ip["override_switch"], f"{ip['override_switch']} on {t} times out after {mh[0]} h "
                        f"({ip.get('override_timeout_action') or 'action not stated'}); the SRS limits a bypass of {sif} to {srs_max.group(1)} h.",
                        "configuration vs SRS", ip.get("override_ref", ""), [t, sif])

    now = _dt(g.export_time())
    for t, ip in sorted(instruments.items()):
        if _norm(ip.get("override_active")) in ("yes", "y", "true") and ip.get("block_type_cfg") != "MOS":
            sw, sif = ip.get("override_switch", ""), ip.get("override_sif", "")
            if t in oos_active or sw in oos_active:
                continue
            since = _dt(ip.get("override_active_since", ""))
            hours = round((now - since).total_seconds() / 3600, 1) if now and since else None
            srs_max = MAX_H_RE.search(sifs.get(sif, {}).get("bypass_conditions", ""))
            over = f" - over the SRS limit of {srs_max.group(1)} h" if hours is not None and srs_max and hours > float(srs_max.group(1)) else ""
            add("C13", "Instrument", sw, f"{sw} has overridden {t} ({sif}, degraded to {ip.get('override_degraded_voting')}) since "
                f"{ip.get('override_active_since') or 'an unknown time'}" + (f": {hours} h at the export ({g.export_time()}){over}" if hours is not None else "")
                + ". The out-of-service register has no active entry for it.", "configuration vs out-of-service register",
                ip.get("override_ref", ""), [t, sif])

    def atag(aid: str) -> str:
        return alarms.get(aid, {}).get("alarm_tag", aid)

    # C19: a credited alarm gives the operator longer than the process has
    for aid, p in sorted(alarms.items()):
        for r in g.inc("CREDITS", "Alarm", aid):
            sc = _id(r, "start")
            for c in g.out("CREDITS", "Scenario", sc):
                s = _id(c, "end")
                pst = sifs.get(s, {}).get("process_safety_time") if c["end_label"] == "SIF" else ""
                if p.get("time_to_respond") and pst and Q.compare(p["time_to_respond"], pst) == 1:
                    add("C19", "Alarm", atag(aid), f"{sc} credits operator response to {atag(aid)} (PFD {r['props'].get('pfd', '?')}). The MADB allows "
                        f"the operator {p['time_to_respond']}; the SRS gives the process safety time of {s}, the SIF for the same scenario, as {pst}.",
                        "MADB vs SRS / LOPA", p.get("madb_ref", ""), [g.source_of(aid), s, sc])

    # C20: which system a device is on, and whether a SIF's devices are on its logic solver
    devices: dict[str, set] = {}
    for r in g.rels:
        if r["type"] in ("INITIATES", "ACTUATES"):
            devices.setdefault(_id(r, "start" if r["type"] == "INITIATES" else "end"), set()).add(_id(r, "end" if r["type"] == "INITIATES" else "start"))
    for tag, p in sorted(instruments.items()):
        if p.get("configured") != "yes" or p.get("block_type_cfg") == "MOS" or not p.get("system_cfg"):
            continue
        idx, cfg_sys, its = SYSTEM.get(_norm(p.get("system"))), SYSTEM.get(_norm(p.get("system_cfg"))), sorted(devices.get(tag, ()))
        solvers = {_norm(sifs.get(s, {}).get(k)) for s in its for k in ("logic_solver", "logic_solver_srs", "logic_solver_cfg")} - {""}
        off_solver = bool(its) and (cfg_sys != "SIS" or (bool(solvers) and bool(p.get("controller_cfg")) and _norm(p["controller_cfg"]) not in solvers))
        if (idx and cfg_sys and idx != cfg_sys) or off_solver:
            add("C20", "Instrument", tag, f"{tag}: the index says {p.get('system') or 'nothing'}; it is configured in the {p.get('system_cfg')} on "
                f"{p.get('controller_cfg') or 'an unnamed controller'} ({p.get('io_channel_cfg') or 'no channel'})."
                + (f" It is a device of {', '.join(its)}, whose logic solver is {', '.join(sorted(s.upper() for s in solvers)) or 'not stated'}: "
                   "the trip does not have the integrity the SIL verification assumes." if off_solver else ""),
                "instrument index vs configuration", p.get("source_ref", ""), its, level="stop" if off_solver else None)

    # C21: where each document says an alarm comes from
    for aid, p in sorted(alarms.items()):
        said = {}
        for r in g.inc("GENERATES", "Alarm", aid):
            d = r["props"].get("source_doc", "")
            said[{"MADB": "MADB", "CFG": "configuration"}.get(g.doc_type(d), "alarm register")] = _id(r, "start")
        if len(set(said.values())) > 1:
            own = sorted({_id(r, "end") for r in g.out("COMPENSATES_FOR", "Alarm", aid) if set(said.values()) & set(g.initiators(_id(r, "end")))})
            add("C21", "Alarm", atag(aid), f"{atag(aid)} is generated by " + "; ".join(f"{t} ({k})" for k, t in sorted(said.items())) + "."
                + (f" It is the curated compensating measure for {', '.join(own)}, and one of those sources is an initiator of that SIF: "
                   "it is not independent of the trip it stands in for." if own else ""),
                " vs ".join(sorted(said)), p.get("cfg_ref") or p.get("madb_ref", ""), list(said.values()) + own, level="stop" if own else None)

    # C23: a procedure that covers some SIFs and not others
    covers: dict[str, set] = {}
    for r in g.rels:
        if r["type"] == "SHOWN_ON" and r["start_label"] == "SIF" and r["props"].get("basis") == "document register: covers":
            covers.setdefault(_id(r, "end"), set()).add(_id(r, "start"))
    real_sifs = {s for s, p in sifs.items() if not p.get("stub")}
    for doc_no, cov in sorted(covers.items()):
        kind = g.doc_type(doc_no)
        if kind not in ("PROC", "PTP") or len(cov) < 2:
            continue
        for s in sorted(real_sifs - cov):
            if not any(s in c for d2, c in covers.items() if d2 != doc_no and g.doc_type(d2) == kind):
                add("C23", "SIF", s, f"{doc_no} ({g.docs[doc_no]['props'].get('title', '')}) covers {', '.join(sorted(cov))} but not {s}, "
                    f"and the register lists no other document of its kind that does.", "document register",
                    g.docs[doc_no]["props"].get("register_ref", ""), [doc_no])

    # C24: the out-of-service register against the clock and the configured state
    out_inst: dict[str, str] = {t: f"overridden by {ip.get('override_switch')} since {ip.get('override_active_since') or 'an unknown time'}"
                                for t, ip in instruments.items() if _norm(ip.get("override_active")) in YES and ip.get("block_type_cfg") != "MOS"}
    out_alarm: dict[str, str] = {a: "disabled in the configuration" for a, p in alarms.items() if _norm(p.get("enabled_cfg")) in NO}
    for row in oos_rows or []:
        if row.get("status") != "active":
            continue
        el, entry = row.get("element", ""), row.get("id") or "an entry"
        aid = el if el in alarms else g.alarm_by_tag.get(el)
        ip = instruments.get(el, {})
        if aid:
            out_alarm.setdefault(aid, f"{ {'shelve': 'shelved', 'disable': 'disabled', 'suppress': 'suppressed'}.get(row.get('kind'), 'out of service')} "
                                      f"({entry}" + (f", since {row['start']}" if row.get("start") else "") + ")")
        elif ip:
            out_inst.setdefault(ip.get("overrides") or el, f"out of service in the register ({entry}" + (f", since {row['start']}" if row.get("start") else "") + ")")
        said = []
        exp = _dt(row.get("expiry", ""))
        if now and exp and now > exp:
            said.append(f"it expired on {row['expiry']}, {round((now - exp).total_seconds() / 3600, 1)} h before the configuration export ({g.export_time()})")
        if ip and (ip.get("override_switch") or ip.get("block_type_cfg") == "MOS") and _norm(ip.get("override_active")) in NO:
            said.append(f"{ip.get('override_switch') or el} is off in the configuration")
        if said:
            add("C24", "Alarm" if aid else "Instrument", atag(aid) if aid else el, f"The out-of-service register shows {atag(aid) if aid else el} as active "
                f"({entry}, {row.get('kind') or 'kind not stated'}), but " + " and ".join(said) + ".", "out-of-service register vs configuration",
                row.get("ref", ""), [x for x in (ip.get("override_switch"), ip.get("override_sif")) if x])

    # C25: as found - something out of service whose compensating measure or protection credit is out too
    for t, how in sorted(out_inst.items()):
        for sif in sorted({_id(r, "end") for r in g.out("INITIATES", "Instrument", t)}):
            cms = [_id(r, "start") for r in g.inc("COMPENSATES_FOR", "SIF", sif)]
            named = [g.alarm_by_tag[x] for x in sorted(g.alarm_by_tag) if x and re.search(rf"\b{re.escape(x)}\b", sifs[sif].get("bypass_conditions", ""))]
            bad = {}
            for a in cms + named:
                why = out_alarm.get(a) or (f"on {g.source_of(a)}, which is itself out of service" if g.source_of(a) in out_inst else "")
                if why:
                    bad.setdefault(a, []).append(("compensating measure" if a in cms else "SRS bypass condition") + f": {why}")
            if bad:
                deg = instruments[t].get("override_degraded_voting")
                add("C25", "Instrument", t, f"{t} is {how}" + (f", leaving {sif} on {deg}" if deg else f", degrading {sif}") + ". "
                    + "; ".join(f"{atag(a)} ({v[0]})" for a, v in sorted(bad.items())) + "."
                    + (f" No compensating measure for {sif} remains." if cms and all(a in bad for a in cms) else ""),
                    "configuration / out-of-service register vs curated register / SRS", instruments[t].get("override_ref", ""),
                    [sif] + [atag(a) for a in bad])
    for aid, how in sorted(out_alarm.items()):
        tag = atag(aid)
        roles = [f"{_id(r, 'start')} credits it as a protection layer (PFD {r['props'].get('pfd', '?')})" for r in g.inc("CREDITS", "Alarm", aid)]
        roles += [f"it is the curated compensating measure (rank {r['props'].get('rank', '?')}) for {_id(r, 'end')}" for r in g.out("COMPENSATES_FOR", "Alarm", aid)]
        roles += [f"the SRS makes it a condition of bypassing {s}" for s in g.srs_naming(tag)]
        if roles:
            add("C25", "Alarm", tag, f"{tag} is {how}, while " + "; ".join(roles) + ".",
                "configuration / out-of-service register vs LOPA / curated register / SRS", alarms[aid].get("cfg_ref") or alarms[aid].get("madb_ref", ""),
                [g.source_of(aid)] + [_id(r, "end") for r in g.out("COMPENSATES_FOR", "Alarm", aid)] + [_id(r, "start") for r in g.inc("CREDITS", "Alarm", aid)])

    # C26: an alarm on the same variable as a trip, of the same sense, must come before the trip
    for sif, p in sorted(sifs.items()):
        cfg = g.initiators(sif, "CFG")
        inits = cfg or g.initiators(sif, "CE")
        direction = next((_norm(v.get("direction")) for v in cfg.values() if v.get("direction")), "")
        trip = next((v.get("setpoint") for v in inits.values() if v.get("setpoint")), "")
        if direction not in ("low", "high") or not trip:
            continue
        where = set().union(*(g.places(t) for t in inits))
        comp = {_id(r, "start") for r in g.inc("COMPENSATES_FOR", "SIF", sif)}
        for aid, ap in sorted(alarms.items()):
            src = g.source_of(aid)
            same_variable = src in inits or (src[:1] == sorted(inits)[0][:1] and bool(g.places(src) & where))
            if trip_notification(ap) or _sense({"alarm_type": ap.get("alarm_type") or aid.rsplit(".", 1)[-1]}) != direction or not same_variable:
                continue
            stated = next(((k, ap[k]) for k in ("setpoint_cfg", "setpoint_madb", "setpoint") if ap.get(k)), None)
            c = Q.compare(in_index_units(stated[1], instruments.get(src, {})), trip) if stated else None
            if c is not None and ((direction == "low" and c <= 0) or (direction == "high" and c >= 0)):
                add("C26", "Alarm", atag(aid), f"{atag(aid)} on {src} is set at {stated[1]} "
                    f"({ {'setpoint_cfg': 'configuration', 'setpoint_madb': 'MADB', 'setpoint': 'alarm register'}[stated[0]]}); {sif} trips on "
                    f"{direction} at {trip} ({', '.join(sorted(inits))}). The alarm would not come before the trip."
                    + (f" It is the curated compensating measure for {sif}." if aid in comp else ""),
                    "configuration vs C&E / SRS", ap.get("cfg_ref") or ap.get("madb_ref", ""), [src, sif])

    for doc_no, d in sorted(g.docs.items()):
        p = d["props"]
        if p.get("doc_type") != "MOC" or "documents_to_revise" not in p:
            continue
        if p.get("stage") in ("implemented", "closed"):
            todo = [x for x in p.get("documents_to_revise", []) if x not in p.get("documents_revised", [])]
            if todo:
                add("C14", "Document", doc_no, f"{doc_no} ({p.get('title')}) is {p.get('status')}; {len(todo)} of "
                    f"{len(p.get('documents_to_revise', []))} documents not revised: {', '.join(todo)}. Tags: {', '.join(p.get('tags_affected', []))}.",
                    "MOC register", p.get("source_ref", ""), p.get("tags_affected", []))
        if p.get("stage") != "cancelled" and "temporary" not in _norm(p.get("change_type")):
            imp = moc_impact(g, doc_no)
            if imp["missed"]:
                add("C15", "Document", doc_no, f"{doc_no} lists {', '.join(p.get('documents_to_revise', [])) or 'no documents'}. The graph also "
                    f"links the change to: " + "; ".join(f"{m} ({imp['documents'][m][0]})" for m in imp["missed"]) + ". Check each.",
                    "MOC register vs graph", p.get("source_ref", ""),
                    [e["id"] for e in imp["elements"]] + [g.p("Alarm", e["id"]).get("alarm_tag", "") for e in imp["elements"] if e["label"] == "Alarm"])
    by_code: dict[str, int] = {}
    for e in ex:
        by_code[e["code"]] = by_code.get(e["code"], 0) + 1
    return {"findings": sorted(ex, key=lambda e: (int(e["code"][1:]), e["id"])), "by_code": dict(sorted(by_code.items(), key=lambda kv: int(kv[0][1:]))),
            "export_time": g.export_time()}


KIND_TO_CODES = {
    "value_mismatch": ("C11",), "calculation_assumes_uninstalled_equipment": ("C11",), "degraded_mode_mismatch": ("C11",),
    "document_not_revised_after_moc": ("C14", "C10"), "config_differs_from_ce": ("C10", "C2"), "config_differs_from_madb": ("C5",),
    "ipl_flag_differs_from_lopa": ("C9",), "range_change_breaks_alarm": ("C7", "C8"), "rationalised_not_configured": ("C4",),
    "bypass_permitted_no_override": ("C12",), "override_timeout_exceeds_srs": ("C12",), "alarm_disabled_unrecorded": ("C6",),
    "configured_not_rationalised": ("C3",), "function_differs_from_index": ("C16",), "trip_notification_not_rationalised": ("C3",),
    "orphan_configured_point": ("C2",), "configured_not_indexed": ("C2",), "moc_impact_incomplete": ("C15",),
    "voting_mismatch": ("C10",), "bypass_active_unrecorded": ("C13",),
}


def scorecard(findings: list[dict], answer_key: dict) -> dict:
    """Which planted items a finding surfaced: same kind of check, and the finding concerns one of the item's tags."""
    rows = []
    used = set()
    for item in answer_key["items"]:
        codes = KIND_TO_CODES.get(item["kind"], ())
        hits = [i for i, f in enumerate(findings) if f["code"] in codes and set(item["tags"]) & (set(f["tags"]) | {f["id"]})]
        used |= set(hits)
        rows.append({"id": item["id"], "kind": item["kind"], "questions": item["questions"], "found": bool(hits),
                     "by": sorted({f"{findings[i]['code']} {findings[i]['id']}" for i in hits})})
    return {"planted": len(rows), "found": sum(r["found"] for r in rows), "items": rows,
            "other_findings": [f"{f['code']} {f['id']}" for i, f in enumerate(findings) if i not in used]}


def main(argv=None) -> int:
    import argparse
    import json
    from .demo import build_demo_store, unit_config
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", default="U-100")
    a = ap.parse_args(argv)
    cfg = unit_config(a.unit)
    from .oos import load_register
    from pathlib import Path as _P
    store, reports = build_demo_store(unit=a.unit)
    oos_rows = load_register(cfg["oos"]) if cfg["oos"] and _P(cfg["oos"]).exists() else []
    res = run(store, oos_rows, aliases=sheet_aliases(cfg["files"].get("index")))
    for f in res["findings"]:
        print(f"{f['code']:4} {f['id']:16} {f['detail']}")
    print(json.dumps(res["by_code"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
