"""Cross-document checks over the operations documents: codes C1-C16.

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

    python -m pid_graph.ops_checks [--unit U-200]   # build the unit from data/ in memory and print the findings
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

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
}
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
MAX_H_RE = re.compile(r"max\s*(\d+(?:\.\d+)?)\s*h", re.I)
RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)\s*$", re.I)
VOTE_RE = re.compile(r"(\d)\s*oo\s*(\d)", re.I)
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

    def add(code, label, ident, detail, sources, refs="", tags=()):
        ex.append({"code": code, "title": TITLES[code], "label": label, "id": ident, "detail": detail,
                   "sources": sources, "refs": refs, "tags": sorted(set(tags) | {ident})})

    # C1 is reported by the document-register loader (unresolved names); the demo passes them in.
    instruments = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "Instrument"}
    alarms = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "Alarm"}
    sifs = {i: n["props"] for (lab, i), n in g.nodes.items() if lab == "SIF"}

    for tag, p in sorted(instruments.items()):
        if p.get("configured") == "yes" and p.get("stub"):
            what = "maintenance override switch" if p.get("block_type_cfg") == "MOS" else f"{p.get('system_cfg') or 'configured'} point"
            add("C2", "Instrument", tag, f"{tag} is a configured {what} ({p.get('io_channel_cfg') or p.get('controller_cfg') or 'no channel'}) "
                "with no instrument index row.", "configuration vs instrument index", p.get("source_ref", ""))
        if p.get("range_cfg") and p.get("range"):
            a, b = _norm(p["range"]).replace(" to ", "-"), _norm(p["range_cfg"])
            if a != b:
                add("C7", "Instrument", tag, f"Index range {p['range']} {p.get('units', '')}; configured {p['range_cfg']} {p.get('units_cfg', '')}.",
                    "instrument index vs configuration", p.get("source_ref", ""))

    for aid, p in sorted(alarms.items()):
        tag, src = p.get("alarm_tag", aid), g.source_of(aid)
        has_cfg, has_madb = bool(p.get("setpoint_cfg") or p.get("priority_cfg")), bool(p.get("madb_ref"))
        if has_cfg and not has_madb:
            extra = " It is configured as a trip notification: a trip is not an alarm." if "TRIP" in str(p.get("alarm_type_cfg", "")).upper() else ""
            add("C3", "Alarm", tag, f"{tag} on {src} is configured ({p.get('setpoint_cfg') or p.get('alarm_type_cfg')}, {p.get('priority_cfg')}) "
                f"but has no MADB record.{extra}", "configuration vs MADB", p.get("cfg_ref", ""), [src])
        if has_madb and not has_cfg:
            add("C4", "Alarm", tag, f"{tag} on {src} is rationalised ({p.get('setpoint_madb')}, {p.get('priority_madb')}, "
                f"{p.get('implementation_status') or 'status not stated'}) but not configured.", "MADB vs configuration", p.get("madb_ref", ""), [src])
        for what, keys in (("setpoint", ("setpoint", "setpoint_madb", "setpoint_cfg")), ("priority", ("priority", "priority_madb", "priority_cfg"))):
            stated = {k: p[k] for k in keys if p.get(k)}
            if len({_norm(v) for v in stated.values()}) > 1:
                names = {keys[0]: "alarm register", keys[1]: "MADB", keys[2]: "configuration"}
                add("C5", "Alarm", tag, f"{tag} {what}: " + "; ".join(f"{names[k]} {v}" for k, v in stated.items()) + ".",
                    " vs ".join(names[k] for k in stated), p.get("cfg_ref", ""), [src])
        if _norm(p.get("enabled_cfg")) in ("no", "n", "false", "0") and aid not in oos_active and tag not in oos_active:
            add("C6", "Alarm", tag, f"{tag} is disabled in the configuration; the out-of-service register has no active entry for it. "
                f"MADB status: {p.get('implementation_status') or 'no record'}.", "configuration vs out-of-service register", p.get("cfg_ref", ""), [src])
        ip = instruments.get(src, {})
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
        if p.get("silv_ref"):
            for t in sorted(sets.get("SIL verification", set())):
                ip = instruments.get(t)
                if ip is None or ip.get("configured") != "yes":
                    add("C11", "SIF", sif, f"The SIL verification credits {t} in the {p.get('sensor_voting_silv')} sensor group; {t} is "
                        f"{'not in the graph (not installed)' if ip is None else 'not configured in the SIS'}. "
                        f"Achieved figures (PFDavg {p.get('pfd_avg_silv')}, RRF {p.get('rrf_achieved_silv')}) rest on it.",
                        "SIL verification vs configuration / index", p.get("silv_ref", ""), [t])
            for which, srs_key in (("sensors", "proof_test_interval"), ("fe", "proof_test_interval")):
                silv = p.get(f"pti_{which}_silv")
                if silv and p.get(srs_key) and _norm(silv) != _norm(p[srs_key]):
                    add("C11", "SIF", sif, f"The SIL verification takes a proof-test interval of {silv} for the "
                        f"{'final elements' if which == 'fe' else 'sensors'}; the SRS specifies {p[srs_key]}.",
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
    store, reports = build_demo_store(unit=a.unit)
    res = run(store, aliases=sheet_aliases(cfg["files"].get("index")))
    for f in res["findings"]:
        print(f"{f['code']:4} {f['id']:16} {f['detail']}")
    print(json.dumps(res["by_code"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
