"""Scenario demonstrator: pick a situation (bypass, shelving, MOC, SIF out of service, trip, where-used,
document revised, everything impaired now) and watch the graph answer it, step by step, with the documents
behind every step.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Every result is a fixed template over the trusted view of the graph (T7), run for every element it applies
to, so a presenter can pick any tag, alarm, SIF, MOC or document, not only the showcase ones. Findings come
from the rules engines (pid_graph.reconcile X-codes, pid_graph.ops_checks C-codes), attached to a scenario
when they concern an element the scenario walked through. Nothing is written by a model; nothing is
hard-coded for U-100 except the showcase list (SHOWCASE) and the default file names. Another unit is a folder
data/<unit in lower case without the dash>/ with a unit.json naming its files (see unit_config).

    python -m pid_graph.demo [--unit U-200]          -> reports/demo_<unit>.html (memory backend, data/)
    python -m pid_graph.demo --artifact PATH         also write the page without its <html> wrapper, for publishing
    python -m pid_graph.demo --json PATH             the scenario results as JSON
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import ops_checks as OC
from .ops_checks import Graph, MAX_H_RE, _dt, _id, _norm, _vote, moc_impact
from .pipeline import build_store
from .records import TrustedView
from .situation import build_model

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_FILES = dict(index=DATA / "U100-INST-INDEX-Rev-B.xlsx", topology=DATA / "pid_audit_U100_topology.csv",
                     ce=DATA / "U100-CE-CHART-Rev-A.xlsx", pdf=DATA / "U100-PIDS-TX-0057.pdf", transmittal="TX-0057",
                     curated=DATA / "curated" / "compensating_measures_U-100.csv", srs=DATA / "U100-SRS-001-Rev-B.xlsx",
                     lopa=DATA / "U100-LOPA-001-Rev-A.xlsx", madb=DATA / "U100-MADB-001-Rev-A.xlsx",
                     config=DATA / "U100-CFG-EXPORT-Rev-A.xlsx", silv=DATA / "U100-SILV-001-Rev-A.xlsx",
                     moc=DATA / "U100-MOC-REG-Rev-A.xlsx", docreg=DATA / "U100-DOC-REGISTER.csv")
OPS_DOCS = ("madb", "config", "silv", "moc", "docreg")
OOS = DATA / "oos" / "out_of_service_U-100.csv"
ANSWER_KEY = DATA / "U100-BATCH1-ANSWER-KEY.json"

# The order a presenter would take them in; each is (kind, element).
SHOWCASE = [("bypass", "PT-1001B"), ("shelve", "LT-1006.LAH"), ("moc", "MOC-2026-016"), ("closeout", "MOC-2026-014"),
            ("sif_out", "SIF-100-03"), ("trip", "SIF-100-02"), ("where_used", "PT-1005"), ("doc_revised", "U100-SRS-001"),
            ("now", "U-100")]
KINDS = {
    "bypass": ("Bypass a trip initiator", "Q3", "This element is bypassed: what protection is lost, what remains, what compensates?"),
    "shelve": ("Shelve or disable an alarm", "Q5", "If this alarm is shelved, what else depends on it?"),
    "moc": ("MOC impact", "Q2", "What does this change reach, and did the MOC list it all?"),
    "closeout": ("MOC close-out", "Q2/Q6", "Is this change reflected in every document it touches?"),
    "sif_out": ("SIF out of service", "Q4", "If this safety function is taken out of service, what is lost and is it allowed?"),
    "trip": ("Trip investigation", "Q8", "This SIF tripped: what should have happened, according to which document?"),
    "where_used": ("Where used", "Q1", "Every document and relationship this element appears in."),
    "doc_revised": ("Document revised", "Q6", "This document is being revised: what depends on it?"),
    "now": ("Everything impaired now", "Q7", "What is out of service, overridden or not as designed at the time of the configuration export?"),
}
STOP = {"C4", "C6", "C8", "C10", "C11", "C12", "C13"}
WARN = {"C3", "C5", "C7", "C9", "C14", "C15", "C16", "X9", "X10", "X11", "X14", "X15", "X16", "X17", "X18", "X20"}


def unit_config(unit: str = "U-100") -> dict:
    """Where a unit's documents are. U-100 is built in. Any other unit is data/<slug>/unit.json:
    {"unit": "U-200", "files": {"index": "...", "ce": "...", "srs": "...", "lopa": "...", "curated": "...", "madb": "...",
     "config": "...", "silv": "...", "moc": "...", "docreg": "...", "topology": null, "pdf": null}, "oos": "..."}
    with paths relative to that folder. An answer key is never read here: a blind unit's score comes from
    its adjudication file ("blind", optional), written by whoever compared the sealed findings with the key."""
    if unit == "U-100":
        return {"unit": unit, "files": dict(DEFAULT_FILES), "oos": OOS, "answer_key": ANSWER_KEY, "showcase": SHOWCASE, "blind": None}
    folder = DATA / unit.lower().replace("-", "")
    cfg = json.loads((folder / "unit.json").read_text(encoding="utf-8"))
    files = {k: (folder / v if v and k != "transmittal" else v) for k, v in cfg["files"].items()}
    files.setdefault("topology", None)
    return {"unit": cfg.get("unit", unit), "files": files, "oos": folder / cfg["oos"] if cfg.get("oos") else None,
            "answer_key": None, "showcase": [], "blind": folder / cfg["blind"] if cfg.get("blind") else None}


def build_demo_store(files: dict | None = None, load_run: str = "demo", unit: str = "U-100"):
    f = {**unit_config(unit)["files"], **(files or {})}
    return build_store(unit=unit, load_run=load_run, **{k: v for k, v in f.items()})


def nid(label: str, ident: str) -> str:
    return f"{label}:{ident}"


def rid(r: dict) -> str:
    return f"{r['type']}|{nid(r['start_label'], _id(r, 'start'))}|{nid(r['end_label'], _id(r, 'end'))}|{r['props'].get('source_doc', '')}"


def level(code: str) -> str:
    return "stop" if code in STOP else "warn" if code in WARN else "info"


class Builder:
    """Collects the steps of one scenario."""

    def __init__(self, g: Graph, kind: str, element: str, title: str):
        name, q, ask = KINDS[kind]
        self.g, self.out = g, {"id": f"{kind}:{element}", "kind": kind, "kind_title": name, "element": element, "title": title,
                               "question": q, "ask": ask, "steps": [], "notes": [], "verdict": None}

    def step(self, title: str, text: str, nodes=(), rels=(), docs=()):
        rels = list(rels)
        nodes = set(nodes) | {nid(r["start_label"], _id(r, "start")) for r in rels} | {nid(r["end_label"], _id(r, "end")) for r in rels}
        docs = set(docs) | {r["props"].get("source_doc", "") for r in rels if r["props"].get("source_doc") in self.g.docs}
        docs |= {_id(r, "end") for r in rels if r["type"] == "SHOWN_ON"}
        docs = {self.g.aliases.get(d, d) for d in docs} & set(self.g.docs)       # a sheet a MOC names is its workbook
        self.out["steps"].append({"title": title, "text": text, "nodes": sorted(nodes), "rels": sorted({rid(r) for r in rels}),
                                  "docs": sorted(d for d in docs if d)})

    def verdict(self, lvl: str, text: str):
        self.out["verdict"] = {"level": lvl, "text": text}

    def done(self, findings: list[dict]) -> dict:
        nodes = {n for s in self.out["steps"] for n in s["nodes"]}
        idents = {n.split(":", 1)[1] for n in nodes}
        idents |= {self.g.p("Alarm", i).get("alarm_tag", i) for i in idents}
        # a C-finding belongs to a scenario that walked the element it is about; an X-finding's id can name two elements
        self.out["findings"] = [f["key"] for f in findings
                                if f["id"] in idents or (f["code"].startswith("X") and idents & set(f["tags"]))]
        self.out["documents"] = sorted({d for s in self.out["steps"] for d in s["docs"]})
        self.out["relationships_followed"] = len({r for s in self.out["steps"] for r in s["rels"]})
        return self.out


def _docs_line(g: Graph, docs) -> str:
    return ", ".join(f"{d} ({g.doc_type(d)})" for d in sorted(docs))


def _alarm_health(g: Graph, aid: str, findings: list[dict]) -> list[str]:
    tag = g.p("Alarm", aid).get("alarm_tag", aid)
    src = g.source_of(aid)
    return [f"{f['code']}: {f['detail']}" for f in findings if f["code"].startswith("C") and (f["id"] == tag or (f["code"] == "C7" and f["id"] == src))]


def _mocs_of(g: Graph, label: str, ident: str) -> list[dict]:
    return [r for r in g.out("SHOWN_ON", label, ident) if g.doc_type(_id(r, "end")) == "MOC" and _id(r, "end").startswith("MOC-")]


def _any(g: Graph, ident: str) -> list[str]:
    """Node ids for an identifier whose label is not known (a finding's tags mix instruments, alarms and SIFs)."""
    return [nid(lab, ident) for lab in ("Instrument", "SIF", "Alarm") if (lab, ident) in g.nodes]


def _one_per_doc(rels: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rels:
        if _id(r, "end") not in seen:
            seen.add(_id(r, "end"))
            out.append(r)
    return out


# ---------------------------------------------------------------- templates
def t_bypass(g: Graph, tag: str, findings: list[dict]) -> dict:
    b = Builder(g, "bypass", tag, f"Bypass {tag}")
    inits = g.out("INITIATES", "Instrument", tag)
    sifs = sorted({_id(r, "end") for r in inits})
    b.step("What it initiates", f"{tag} is an initiator of {', '.join(sifs)}. " + "; ".join(
        f"{r['props']['source_doc']} says {r['props'].get('voting', '?')} at {r['props'].get('setpoint', '?')}" for r in inits) + ".", rels=inits)
    stops, warns = [], []
    for sif in sifs:
        sp = g.p("SIF", sif)
        cfg = g.initiators(sif, "CFG") or g.initiators(sif, "CE")
        rest = sorted(set(cfg) - {tag})
        ip = g.p("Instrument", tag)
        sw = ip.get("override_switch")
        deg = ip.get("override_degraded_voting") or "not configured"
        assumed = _vote(sp.get("degraded_sensor_voting_silv"))
        txt = (f"While {tag} is out, {sif} relies on {', '.join(rest) or 'nothing'}. "
               + (f"The bypass is made with {sw}, configured to degrade the vote to {deg}. " if sw else "No maintenance override is configured for it: a bypass means forcing. ")
               + (f"The SIL verification assumed {assumed} in this case." if assumed else ""))
        if sw and assumed and _vote(deg) and _vote(deg) != assumed:
            stops.append(f"{sif} would run {deg}, not the {assumed} its SIL verification assumed.")
        if not sw:
            stops.append(f"No override switch on {tag}.")
        b.step(f"What remains of {sif}", txt, nodes=[nid("Instrument", t) for t in rest] + ([nid("Instrument", sw)] if sw else []),
               rels=[r for r in g.inc("INITIATES", "SIF", sif) if _id(r, "start") in rest and g.doc_type(r["props"]["source_doc"]) == "CFG"],
               docs=[d for d in g.documents_of("SIF", sif) if g.doc_type(d) == "SILV"])
        prot = g.out("PROTECTS", "SIF", sif)
        credits = g.inc("CREDITS", "SIF", sif)
        req = ", ".join(f"{_id(r, 'start')} needs SIL {r['props'].get('required_sil', '?')} (PFD {r['props'].get('pfd', '?')})" for r in credits)
        b.step(f"What {sif} protects", f"{sif} protects {', '.join(sorted({_id(r, 'end') for r in prot}))}. LOPA: {req or 'no credit recorded'}. "
               f"SIL: C&E {sp.get('sil', '?')}, SRS {sp.get('sil_srs', '?')}, SIL verification achieved {sp.get('sil_achieved_silv', '?')}.",
               rels=prot + credits)
        cond = sp.get("bypass_conditions", "")
        mx = MAX_H_RE.search(cond)
        b.step("What the SRS allows", f"SRS bypass conditions for {sif}: “{cond or 'none stated'}”.",
               nodes=[nid("SIF", sif)], docs=[d for d in g.documents_of("SIF", sif) if g.doc_type(d) in ("SRS", "PROC")])
        cms = g.inc("COMPENSATES_FOR", "SIF", sif)
        lines = []
        for r in sorted(cms, key=lambda r: str(r["props"].get("rank", ""))):
            aid = _id(r, "start")
            src = g.source_of(aid)
            health = _alarm_health(g, aid, findings)
            valid = "INVALID while bypassed: it comes from the bypassed transmitter" if src == tag else "valid in principle"
            lines.append(f"rank {r['props'].get('rank', '?')} {g.p('Alarm', aid).get('alarm_tag', aid)} on {src} "
                         f"(basis {r['props'].get('basis', '?').replace('_', ' ')}; {valid})"
                         + (": " + " | ".join(health) if health else ": no finding against it"))
            if health or src == tag:
                warns.append(f"Compensating measure {g.p('Alarm', aid).get('alarm_tag', aid)} is impaired.")
        mocs = [m for r in cms for m in _mocs_of(g, "Alarm", _id(r, "start")) + _mocs_of(g, "Instrument", g.source_of(_id(r, "start")))]
        b.step("Compensating measures, and their state", ("Curated register: " + "; ".join(lines) + ".") if lines else
               "No curated compensating measure for this SIF (see X14).",
               rels=cms + [x for r in cms for x in g.inc("GENERATES", "Alarm", _id(r, "start"))] + mocs)
        now = OC._dt(g.export_time())
        if _norm(ip.get("override_active")) in ("yes", "y"):
            since = _dt(ip.get("override_active_since", ""))
            hours = round((now - since).total_seconds() / 3600, 1) if now and since else None
            over = mx and hours is not None and hours > float(mx.group(1))
            b.step("Right now", f"At the configuration export ({g.export_time()}) {sw} is ACTIVE on {tag}, since {ip.get('override_active_since')}"
                   + (f" ({hours} h; SRS limit {mx.group(1)} h)" if hours is not None and mx else "") + ". The out-of-service register has no entry for it.",
                   nodes=[nid("Instrument", sw), nid("Instrument", tag)], docs=[d for d in g.docs if g.doc_type(d) == "CFG"])
            stops.append(f"{sw} has been active {hours} h with no out-of-service entry" + (" - over the SRS limit." if over else "."))
    if stops:
        b.verdict("stop", "Do not rely on this bypass as it stands. " + " ".join(stops + warns))
    elif warns:
        b.verdict("warn", "Bypass possible only with the compensating measures restored first. " + " ".join(warns))
    else:
        b.verdict("ok", "Bypass can proceed under the SRS conditions, with the compensating measures confirmed active.")
    return b.done(findings)


def t_shelve(g: Graph, aid: str, findings: list[dict]) -> dict:
    p = g.p("Alarm", aid)
    tag, src = p.get("alarm_tag", aid), g.source_of(aid)
    b = Builder(g, "shelve", aid, f"Shelve {tag}")
    meas = g.out("MEASURES", "Instrument", src)
    b.step("What it watches", f"{tag} ({p.get('description', '') or p.get('alarm_type', '')}) is generated by {src}, which measures "
           f"{', '.join(_id(r, 'end') for r in meas) or 'nothing recorded'}. Alarm register {p.get('setpoint', '-')} {p.get('priority', '')}; "
           f"MADB {p.get('setpoint_madb', '-')} {p.get('priority_madb', '')}; configured {p.get('setpoint_cfg', '-')} {p.get('priority_cfg', '')}"
           f"{' (DISABLED)' if _norm(p.get('enabled_cfg')) == 'no' else ''}.", rels=g.inc("GENERATES", "Alarm", aid) + meas)
    reasons = []
    cr = g.inc("CREDITS", "Alarm", aid)
    if cr:
        reasons.append(f"it is an independent protection layer in {', '.join(_id(r, 'start') for r in cr)}")
    b.step("Is it a protection layer?", ("LOPA credits it: " + "; ".join(f"{_id(r, 'start')} as '{r['props'].get('ipl_type')}', PFD {r['props'].get('pfd')}" for r in cr)
           + f". The MADB says IPL credit '{p.get('ipl_credit') or 'none'}', class '{p.get('alarm_class') or 'none'}'.") if cr else
           "No LOPA scenario credits it.", rels=cr + [x for r in cr for x in g.out("THREATENS", "Scenario", _id(r, "start"))])
    cf = g.out("COMPENSATES_FOR", "Alarm", aid)
    named = g.srs_naming(tag)
    if cf:
        reasons.append(f"it is a curated compensating measure for {', '.join(_id(r, 'end') for r in cf)}")
    if named:
        reasons.append(f"the SRS makes it a condition of bypassing {', '.join(named)}")
    b.step("Does a bypass depend on it?", ("Curated: compensating measure for " + ", ".join(f"{_id(r, 'end')} (rank {r['props'].get('rank')})" for r in cf) + ". " if cf else "Not a curated compensating measure. ")
           + (f"SRS bypass conditions of {', '.join(named)} name it." if named else "No SRS bypass condition names it."),
           rels=cf, nodes=[nid("SIF", s) for s in named], docs=[d for s in named for d in g.documents_of("SIF", s) if g.doc_type(d) == "SRS"])
    shared = g.out("INITIATES", "Instrument", src)
    b.step("Does it share a sensor with a trip?", (f"{src} also initiates {', '.join(sorted({_id(r, 'end') for r in shared}))}: the alarm is a pre-alarm on a trip "
           "sensor, not independent of it." if shared else f"{src} initiates no SIF."), rels=shared)
    locs = {_id(r, "end") for r in meas}
    neighbours = [r for r in g.rels if r["type"] == "MEASURES" and _id(r, "end") in locs and _id(r, "start") != src]
    others = [(x, a) for x in sorted({_id(r, "start") for r in neighbours}) for a in g.alarms_of(x)]
    b.step("What else watches the same place", ("Other alarms there: " + "; ".join(
        f"{g.p('Alarm', a).get('alarm_tag', a)} on {x}" + (" (DISABLED)" if _norm(g.p("Alarm", a).get("enabled_cfg")) == "no" else "")
        for x, a in others) + ".") if others else "No other alarm watches the same place.",
        rels=neighbours + [r for x, _ in others for r in g.out("GENERATES", "Instrument", x)])
    mocs = _one_per_doc(_mocs_of(g, "Alarm", aid) + _mocs_of(g, "Instrument", src))
    if mocs:
        b.step("Change history", "MOCs that touched it: " + "; ".join(f"{_id(r, 'end')} {g.docs[_id(r, 'end')]['props'].get('title')} "
               f"({g.docs[_id(r, 'end')]['props'].get('status')})" for r in mocs) + ".", rels=mocs)
    if reasons:
        b.verdict("stop", f"Do not shelve {tag} without a management decision: " + "; ".join(reasons) + ".")
    else:
        b.verdict("ok", f"{tag} carries no protection credit in the graph; shelving follows the alarm philosophy.")
    return b.done(findings)


def t_moc(g: Graph, moc: str, findings: list[dict], closeout: bool = False) -> dict:
    m = g.docs[moc]["props"]
    imp = moc_impact(g, moc)
    b = Builder(g, "closeout" if closeout else "moc", moc, f"{moc}: {m.get('title')}")
    named = g.inc("SHOWN_ON", "Document", moc)
    b.step("What the MOC says", f"{m.get('change_type')}, {m.get('status')} (raised {m.get('raised')}"
           + (f", implemented {m.get('implemented')}" if m.get("implemented") else "") + f"). Tags: {', '.join(m.get('tags_affected', []))}"
           + (f" ({', '.join(m.get('tags_not_in_graph'))} not in the graph)" if m.get("tags_not_in_graph") else "")
           + f". Documents to revise: {', '.join(m.get('documents_to_revise', [])) or 'none listed'}; revised: {', '.join(m.get('documents_revised', [])) or 'none'}.",
           rels=named, docs=[moc])
    reached = [e for e in imp["elements"] if e["why"] != "named in the MOC"]
    b.step("What the change reaches", "; ".join(f"{e['id']} ({e['why']})" for e in imp["elements"]) + ".",
           nodes=[nid(e["label"], e["id"]) for e in imp["elements"]],
           rels=[r for e in reached for r in g.inc("GENERATES", "Alarm", e["id"])])
    dep = []
    for e in imp["elements"]:
        if e["label"] == "Alarm":
            dep += g.inc("CREDITS", "Alarm", e["id"]) + g.out("COMPENSATES_FOR", "Alarm", e["id"])
        if e["label"] == "SIF":
            dep += g.inc("CREDITS", "SIF", e["id"]) + g.out("PROTECTS", "SIF", e["id"])
    b.step("Documents the graph links to it", "; ".join(f"{d}: {v[0]}" + (f" (+{len(v) - 1} more)" if len(v) > 1 else "") for d, v in imp["documents"].items()) + ".",
           rels=dep, docs=list(imp["documents"]))
    lvl = "ok"
    if imp["missed"]:
        crit = [d for d in imp["missed"] if g.doc_type(d) in ("SRS", "LOPA", "CUR", "SILV", "CE")]
        lvl = "stop" if crit else "warn"
        b.step("What the MOC did not list", f"{len(imp['missed'])} documents the graph reaches are not on the MOC: "
               + _docs_line(g, imp["missed"]) + ".", docs=imp["missed"])
    if closeout or imp["outstanding"]:
        state = []
        for e in imp["elements"]:
            if e["label"] == "SIF":
                sp = g.p("SIF", e["id"])
                ce, cfg = g.initiators(e["id"], "CE"), g.initiators(e["id"], "CFG")
                state.append(f"{e['id']} as configured: {sp.get('voting_cfg', '?')} on {', '.join(sorted(cfg)) or '?'}; C&E: "
                             f"{'/'.join(sorted({v.get('voting', '') for v in ce.values()}))} on {', '.join(sorted(ce))}; SRS: {sp.get('sensor_architecture', '?')}; "
                             f"SIL verification: {sp.get('sensor_voting_silv', '?')} on {sp.get('sensor_tags_silv', '?')}")
            if e["label"] == "Instrument" and g.p("Instrument", e["id"]).get("stub"):
                state.append(f"{e['id']} is configured but not in the instrument index")
        b.step("Close-out: documents still to revise", (f"{len(imp['outstanding'])} of {len(m.get('documents_to_revise', []))} listed documents are not revised: "
               + ", ".join(imp["outstanding"]) + ". " if imp["outstanding"] else "Every listed document is revised. ") + ("; ".join(state) + "." if state else ""),
               docs=imp["outstanding"] + [d for d in g.docs if g.doc_type(d) == "CFG"])
        if imp["outstanding"] and m.get("stage") in ("implemented", "closed"):
            lvl = "stop"
    b.verdict(lvl, {"stop": "The plant and its safety documents disagree because of this change. Revise before relying on any of them.",
                    "warn": "The impact list is incomplete. Add the missed documents to the MOC.",
                    "ok": "The MOC lists every document the graph links to the change."}[lvl])
    return b.done(findings)


def t_sif_out(g: Graph, sif: str, findings: list[dict]) -> dict:
    sp = g.p("SIF", sif)
    b = Builder(g, "sif_out", sif, f"Take {sif} out of service")
    prot, credits = g.out("PROTECTS", "SIF", sif), g.inc("CREDITS", "SIF", sif)
    lines = []
    for c in credits:
        sc = _id(c, "start")
        others = [r for r in g.out("CREDITS", "Scenario", sc) if not (r["end_label"] == "SIF" and _id(r, "end") == sif)]
        lines.append(f"{sc}: required SIL {c['props'].get('required_sil', '?')}; other layers: "
                     + (", ".join(f"{_id(r, 'end')} (PFD {r['props'].get('pfd')})" for r in others) or "NONE - it is the only layer"))
    b.step("What is lost", f"{sif} ({sp.get('description') or sp.get('functional_description', '')}) protects {', '.join(sorted({_id(r, 'end') for r in prot}))}. "
           + "; ".join(lines) + ".", rels=prot + credits + [r for c in credits for r in g.out("CREDITS", "Scenario", _id(c, "start"))])
    acts = g.out("ACTUATES", "SIF", sif)
    shared = {_id(r, "end"): sorted({_id(x, "start") for x in g.inc("ACTUATES", "Instrument", _id(r, "end"))} - {sif}) for r in acts}
    b.step("Initiators and final elements", f"Configured initiators: {', '.join(sorted(g.initiators(sif, 'CFG') or g.initiators(sif, 'CE')))}. Final elements: "
           + "; ".join(f"{fe}" + (f" (also used by {', '.join(o)})" if o else "") for fe, o in shared.items()) + ".",
           rels=acts + g.inc("INITIATES", "SIF", sif))
    cond = sp.get("bypass_conditions", "")
    b.step("What the SRS allows", f"“{cond or 'no bypass conditions stated'}”", nodes=[nid("SIF", sif)],
           docs=[d for d in g.documents_of("SIF", sif) if g.doc_type(d) in ("SRS", "PROC")])
    cms = g.inc("COMPENSATES_FOR", "SIF", sif)
    pending = [f for f in findings if f["code"] == "C4"]
    b.step("Compensating measures", ("Curated: " + ", ".join(g.p("Alarm", _id(r, "start")).get("alarm_tag", "") for r in cms) + ". ") if cms else
           "The curated register records a GAP: no alarm compensates for this SIF. "
           + (" Rationalised but not configured: " + "; ".join(f["detail"] for f in pending) if pending else ""),
           rels=cms, nodes=[nid("Alarm", g.alarm_by_tag.get(f["id"], f["id"])) for f in pending])
    no_override = [f for f in findings if f["code"] == "C12" and f["id"] == sif]
    mocs = _mocs_of(g, "SIF", sif)
    if mocs:
        b.step("Open changes", "; ".join(f"{_id(r, 'end')} {g.docs[_id(r, 'end')]['props'].get('title')} ({g.docs[_id(r, 'end')]['props'].get('status')})" for r in mocs) + ".",
               rels=mocs)
    sole = any("NONE" in ln for ln in lines)
    if (not cms) or no_override or sole:
        b.verdict("stop", f"{sif} cannot be taken out of service in line with the SRS today: "
                  + "; ".join(filter(None, ["no compensating alarm exists" if not cms else "",
                                            "no override switch is configured" if no_override else "",
                                            "it is the only layer in its LOPA scenario" if sole else ""])) + ".")
    else:
        b.verdict("warn", f"Possible only under the SRS conditions with the compensating measures confirmed active.")
    return b.done(findings)


def t_trip(g: Graph, sif: str, findings: list[dict]) -> dict:
    sp = g.p("SIF", sif)
    b = Builder(g, "trip", sif, f"{sif} has tripped")
    ce, cfg = g.initiators(sif, "CE"), g.initiators(sif, "CFG")
    b.step("Which signals should trip it", f"C&E: {', '.join(f'{t} {v.get('voting')} at {v.get('setpoint')}' for t, v in sorted(ce.items()))}. "
           f"As configured: {', '.join(f'{t} {v.get('voting')} at {v.get('setpoint')}' for t, v in sorted(cfg.items())) or 'not in the export'}. "
           f"SRS: {sp.get('sensor_architecture', '?')} at {sp.get('setpoint_srs', '?')}.", rels=g.inc("INITIATES", "SIF", sif))
    pre = [(t, a) for t in sorted(set(ce) | set(cfg)) for a in g.alarms_of(t)]
    locs = {_id(r, "end") for t in set(ce) | set(cfg) for r in g.out("MEASURES", "Instrument", t)}
    near = [(x, a) for x in sorted({_id(r, "start") for r in g.rels if r["type"] == "MEASURES" and _id(r, "end") in locs} - set(ce) - set(cfg))
            for a in g.alarms_of(x)]
    b.step("Which alarms should have come first", ("Pre-alarms: " + "; ".join(
        f"{g.p('Alarm', a).get('alarm_tag')} on {x} at {g.p('Alarm', a).get('setpoint_cfg') or g.p('Alarm', a).get('setpoint')} ({g.p('Alarm', a).get('priority_cfg') or g.p('Alarm', a).get('priority')})"
        for x, a in pre + near) + ".") if pre + near else "No pre-alarm on the trip sensors or at the same place.",
        rels=[r for x, _ in pre + near for r in g.out("GENERATES", "Instrument", x)] + [r for x, _ in near for r in g.out("MEASURES", "Instrument", x)])
    acts = g.out("ACTUATES", "SIF", sif)
    b.step("What should have moved", "; ".join(f"{_id(r, 'end')} {r['props'].get('action', '?')} ({r['props'].get('source_doc')})" for r in acts) + ".", rels=acts)
    raises = g.out("RAISES", "SIF", sif)
    if raises:
        b.step("What it announces", "; ".join(f"{g.p('Alarm', _id(r, 'end')).get('alarm_tag')} ({r['props'].get('source_doc')})" for r in raises) + ".", rels=raises)
    credits = g.inc("CREDITS", "SIF", sif)
    b.step("Why it is there", "; ".join(f"{_id(r, 'start')}: required SIL {r['props'].get('required_sil')}, credited PFD {r['props'].get('pfd')}" for r in credits)
           + f". SIL verification: achieved SIL {sp.get('sil_achieved_silv', '?')} (RRF {sp.get('rrf_achieved_silv', '?')}).",
           rels=credits + [x for r in credits for x in g.out("THREATENS", "Scenario", _id(r, "start"))])
    disagree = [f for f in findings if f["code"] in ("C10", "X10", "X16", "X20") and f["id"] == sif]
    b.verdict("warn" if disagree else "ok", ("The documents disagree on how this SIF should trip: " + " ".join(f["detail"] for f in disagree)) if disagree
              else "The C&E, SRS and configuration agree on how this SIF trips.")
    return b.done(findings)


def t_where_used(g: Graph, label: str, ident: str, findings: list[dict]) -> dict:
    caption = g.p(label, ident).get("alarm_tag", ident) if label == "Alarm" else ident
    b = Builder(g, "where_used", ident, f"Where is {caption} used?")
    docs = g.documents_of(label, ident)
    if label == "Alarm":
        for s in g.srs_naming(caption):
            for d in g.documents_of("SIF", s):
                if g.doc_type(d) == "SRS":
                    docs.setdefault(d, []).append(f"named in the {s} bypass conditions")
    groups = {"Design": ("IDX", "PID", "CE", "LOOP"), "Safety": ("SRS", "LOPA", "SILV", "CUR"),
              "Operations": ("MADB", "CFG", "PROC", "PTP", "PHIL", "SISIO"), "Change": ("MOC",)}
    touching = g.touching(label, ident)
    for name, types in groups.items():
        ds = {d: v for d, v in docs.items() if g.doc_type(d) in types}
        if ds:
            b.step(f"{name} documents", "; ".join(f"{d} ({g.doc_type(d)}): {', '.join(v)}" for d, v in sorted(ds.items())) + ".",
                   rels=[r for r in touching if (r["type"] == "SHOWN_ON" and _id(r, "end") in ds) or
                         (r["type"] != "SHOWN_ON" and r["props"].get("source_doc") in ds)], docs=list(ds))
    if label == "Instrument":
        for a in g.alarms_of(ident):
            ad = g.documents_of("Alarm", a)
            atag = g.p("Alarm", a).get("alarm_tag", a)
            for s in g.srs_naming(atag):
                for d in g.documents_of("SIF", s):
                    if g.doc_type(d) == "SRS":
                        ad.setdefault(d, []).append(f"named in the {s} bypass conditions")
            b.step(f"Its alarm {atag}", "; ".join(f"{d} ({g.doc_type(d)}): {', '.join(v)}" for d, v in sorted(ad.items())) + ".",
                   rels=g.inc("GENERATES", "Alarm", a) + [r for r in g.touching("Alarm", a) if r["type"] != "SHOWN_ON"], docs=list(ad))
    total = set(docs) | {d for s in b.out["steps"] for d in s["docs"]}
    b.verdict("info", f"{caption} appears in {len(total)} documents. Each of them is a place a change to it has to reach.")
    return b.done(findings)


def t_doc_revised(g: Graph, doc: str, findings: list[dict]) -> dict:
    d = g.docs[doc]["props"]
    b = Builder(g, "doc_revised", doc, f"{doc} is being revised")
    covered = [r for r in g.rels if (r["type"] == "SHOWN_ON" and _id(r, "end") == doc)]
    states = [r for r in g.rels if r["type"] != "SHOWN_ON" and r["props"].get("source_doc") == doc]
    elems = sorted({nid(r["start_label"], _id(r, "start")) for r in covered})
    b.step("What it covers", f"{doc} ({d.get('doc_type')}, {d.get('title', '')}) is the source of {len(states)} relationships and shows "
           f"{len(elems)} elements: {', '.join(e.split(':', 1)[1] for e in elems[:30])}{' ...' if len(elems) > 30 else ''}.", rels=covered + states)
    others: dict[str, set] = {}
    for e in elems:
        lab, i = e.split(":", 1)
        for od in g.documents_of(lab, i):
            if od != doc and g.doc_type(od) not in ("CFG", "REG", "MOC"):
                others.setdefault(od, set()).add(i)
    b.step("Documents that share its content", "; ".join(f"{od} ({g.doc_type(od)}): {len(v)} shared" for od, v in sorted(others.items(), key=lambda kv: -len(kv[1]))) + ".",
           docs=list(others))
    mocs = [m for m, n in g.docs.items() if n["props"].get("doc_type") == "MOC" and doc in n["props"].get("documents_to_revise", [])]
    pending = [m for m in mocs if doc not in g.docs[m]["props"].get("documents_revised", []) and g.docs[m]["props"].get("stage") != "cancelled"]
    b.step("Changes waiting on it", ("MOCs that list it and have not had it revised: " + "; ".join(
        f"{m} {g.docs[m]['props'].get('title')} ({g.docs[m]['props'].get('status')})" for m in pending) + ".") if pending else "No open MOC waits on it.",
        docs=pending)
    b.verdict("warn" if pending else "info", (f"Fold {len(pending)} open change(s) into this revision, and re-check the {len(others)} documents that share its content."
                                              if pending else f"Re-check the {len(others)} documents that share its content."))
    return b.done(findings)


def t_now(g: Graph, unit: str, findings: list[dict], oos_rows: list[dict]) -> dict:
    b = Builder(g, "now", unit, f"Everything impaired on {unit} now")
    t = g.export_time()
    ov = [f for f in findings if f["code"] == "C13"]
    b.step("Overrides active", (" ".join(f["detail"] for f in ov)) if ov else "No maintenance override is active.",
           nodes=[n for f in ov for x in f["tags"] for n in _any(g, x)], docs=[d for d in g.docs if g.doc_type(d) == "CFG"])
    dis = [f for f in findings if f["code"] in ("C6", "C4", "C8")]
    b.step("Alarms not doing their job", " ".join(f"{f['code']}: {f['detail']}" for f in dis) or "None.",
           nodes=[nid("Alarm", g.alarm_by_tag.get(f["id"], f["id"])) for f in dis])
    for sif in sorted(k for (lab, k) in g.nodes if lab == "SIF"):
        sp = g.p("SIF", sif)
        issues = [f"{f['code']}: {f['detail']}" for f in findings if f["code"] in ("C10", "C11", "C12", "C13") and (f["id"] == sif or sif in f["tags"])]
        cms = g.inc("COMPENSATES_FOR", "SIF", sif)
        cm_state = [f"{g.p('Alarm', _id(r, 'start')).get('alarm_tag')}: " + (" | ".join(_alarm_health(g, _id(r, "start"), findings)) or "no finding")
                    for r in cms]
        b.step(f"{sif}", (" ".join(issues) or "As designed.") + (" Compensating measures - " + "; ".join(cm_state) + "." if cm_state else " No compensating alarm."),
               rels=cms + g.inc("INITIATES", "SIF", sif))
    open_mocs = [m for m, n in g.docs.items() if n["props"].get("doc_type") == "MOC" and n["props"].get("stage") not in ("closed", "cancelled", None, "")
                 and "documents_to_revise" in n["props"]]
    b.step("Changes in flight", "; ".join(f"{m} {g.docs[m]['props'].get('title')} ({g.docs[m]['props'].get('status')})" for m in sorted(open_mocs)) + ".",
           docs=open_mocs)
    act = [r for r in oos_rows if r.get("status") == "active"]
    b.verdict("stop" if ov or dis else "ok", f"At {t}: {len(ov)} override(s) and {len(dis)} alarm problem(s) the out-of-service register "
              f"({len(act)} active entries) does not show. This picture only exists when every document is in one graph.")
    return b.done(findings)


# ---------------------------------------------------------------- run everything
def design_exceptions(files: dict | None = None, unit: str = "U-100") -> list[dict]:
    """The X-codes exactly as the pipeline reports them: reconcile over a build of the design documents alone.
    (Run over the full graph, reconcile would read the configuration's trip signals as if they were the C&E's.)"""
    from .reconcile import reconcile
    f = {k: v for k, v in {**unit_config(unit)["files"], **(files or {})}.items() if k not in OPS_DOCS}
    store, reports = build_store(unit=unit, load_run="demo-design", **f)
    return reconcile(TrustedView(store), unit=unit, ce_report=reports.get("ce"), curated_report=reports.get("curated"),
                     lopa_report=reports.get("lopa"), titleblock_report=reports.get("titleblock"))["exceptions"]


def run_all_scenarios(store, reports: dict, oos_rows: list[dict] | None = None, x_exceptions: list[dict] | None = None,
                      aliases: dict | None = None, showcase: list | None = None) -> dict:
    oos_rows = oos_rows or []
    trusted = TrustedView(store)
    g = Graph(trusted, aliases)
    ops = OC.run(store, oos_rows, aliases=aliases)
    rec = {"exceptions": x_exceptions if x_exceptions is not None else design_exceptions(unit=reports["unit"])}
    findings = []
    for f in ops["findings"]:
        findings.append({**f, "level": level(f["code"])})
    for u in (reports.get("docreg") or {}).get("unresolved", []):
        findings.append({"code": "C1", "title": OC.TITLES["C1"], "label": "Document", "id": u.get("doc_no", ""), "detail": f"{u.get('doc_no')} covers "
                         f"{u.get('name')}, which is not in the graph.", "sources": "document register", "refs": u.get("ref", ""), "tags": [u.get("name", "")], "level": "info"})
    for e in rec["exceptions"]:
        tags = [x.strip() for x in re.split(r"[ /|]+", e["id"]) if x.strip()]
        findings.append({**e, "tags": tags, "level": level(e["code"])})
    for i, f in enumerate(findings):
        f["key"] = f"F{i + 1:03d}"
    results = []
    for (lab, k) in sorted(g.nodes):
        p = g.p(lab, k)
        if lab == "Instrument" and g.out("INITIATES", lab, k) and not p.get("stub"):
            results.append(t_bypass(g, k, findings))
        if lab == "Alarm" and not p.get("stub"):
            results.append(t_shelve(g, k, findings))
        if lab == "SIF":
            results += [t_sif_out(g, k, findings), t_trip(g, k, findings)]
        if lab in ("Instrument", "Alarm", "SIF"):
            results.append(t_where_used(g, lab, k, findings))
        if lab == "Document" and p.get("doc_type") == "MOC" and "documents_to_revise" in p:
            results.append(t_moc(g, k, findings, closeout=False))
            if p.get("stage") in ("implemented", "closed"):
                results.append(t_moc(g, k, findings, closeout=True))
        if lab == "Document" and p.get("doc_type") not in ("MOC", "REG", "CFG"):
            results.append(t_doc_revised(g, k, findings))
    results.append(t_now(g, reports["unit"], findings, oos_rows))
    by_id = {r["id"]: r for r in results}
    picked = []
    for kind, el in (SHOWCASE if showcase is None else showcase):
        sid = f"{kind}:{g.alarm_by_tag.get(el, el) if kind == 'shelve' else el}"
        if sid in by_id:
            picked.append(sid)
    if not picked:                      # a unit with no prepared order: the most serious scenario of each type
        order = {"stop": 0, "warn": 1, "ok": 2, "info": 3}
        for kind in KINDS:
            of_kind = sorted((r for r in results if r["kind"] == kind), key=lambda r: (order[r["verdict"]["level"]], r["element"]))
            if of_kind:
                picked.append(of_kind[0]["id"])
    showcase = picked
    return {"unit": reports["unit"], "export_time": g.export_time(), "findings": findings, "scenarios": results, "showcase": showcase,
            "ops_by_code": ops["by_code"], "titles": {**OC.TITLES}, "graph": export_graph(trusted),
            "situation": build_model(g, findings, oos_rows)}


def export_graph(store) -> dict:
    nodes = []
    for n in store.nodes():
        lab = n["label"]
        ident = n["key"]["doc_no"] if lab == "Document" else next(iter(n["key"].values()))
        p = n["props"]
        cap = p.get("alarm_tag", ident) if lab == "Alarm" else ident
        keep = {k: v for k, v in p.items() if k not in ("load_run", "unit", "stub_unit") and v not in (None, "", [])}
        nodes.append({"id": nid(lab, ident), "label": lab, "caption": cap, "doc_type": p.get("doc_type", ""), "stub": bool(p.get("stub")), "props": keep})
    rels = [{"id": rid(r), "type": r["type"], "from": nid(r["start_label"], _id(r, "start")), "to": nid(r["end_label"], _id(r, "end")),
             "props": {k: v for k, v in r["props"].items() if k not in ("load_run",) and v not in (None, "")}} for r in store.rels()]
    return {"nodes": nodes, "rels": rels}


def build(files: dict | None = None, unit: str = "U-100") -> dict:
    from .oos import load_register
    cfg = unit_config(unit)
    store, reports = build_demo_store(files, unit=unit)
    oos_rows = load_register(cfg["oos"]) if cfg["oos"] and Path(cfg["oos"]).exists() else []
    aliases = OC.sheet_aliases({**cfg["files"], **(files or {})}.get("index"))
    data = run_all_scenarios(store, reports, oos_rows, design_exceptions(files, unit), aliases, cfg["showcase"])
    data["oos_active"] = [r["element"] for r in oos_rows if r.get("status") == "active"]
    if cfg["blind"] and Path(cfg["blind"]).exists():
        data["blind"] = json.loads(Path(cfg["blind"]).read_text(encoding="utf-8"))
    if cfg["answer_key"] and Path(cfg["answer_key"]).exists():
        key = json.loads(Path(cfg["answer_key"]).read_text(encoding="utf-8"))
        data["scorecard"] = OC.scorecard([f for f in data["findings"] if f["code"].startswith("C")], key)
        data["answer_key"] = {i["id"]: {"finding": i["finding"], "questions": i["questions"], "documents": i["documents"]} for i in key["items"]}
    data["counts"] = store.counts()
    data["documents"] = sorted(({"doc_no": n["key"]["doc_no"], "rev": n["key"]["rev"], "doc_type": n["props"].get("doc_type", ""),
                                 "title": n["props"].get("title", ""), "file": n["props"].get("file", "")}
                                for n in store.nodes("Document")), key=lambda d: (d["doc_type"], d["doc_no"]))
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the scenario demonstrator page for one unit.")
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--out", default="", help="default reports/demo_<unit>.html")
    ap.add_argument("--artifact", default="", help="also write the page body without <html>/<head>, for publishing")
    ap.add_argument("--json", default="", help="also write the scenario results as JSON")
    a = ap.parse_args(argv)
    from .demo_page import render
    data = build(unit=a.unit)
    out = Path(a.out) if a.out else ROOT / "reports" / f"demo_{a.unit}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data, standalone=True), encoding="utf-8")
    print(out)
    if a.artifact:
        Path(a.artifact).write_text(render(data, standalone=False), encoding="utf-8")
        print(a.artifact)
    if a.json:
        Path(a.json).write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
        print(a.json)
    sc = data.get("scorecard")
    print(f"{len(data['scenarios'])} scenarios, {len(data['findings'])} findings"
          + (f"; planted problems found {sc['found']} of {sc['planted']}" if sc else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
