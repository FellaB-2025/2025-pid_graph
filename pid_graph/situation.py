"""Build-your-own situation: several things out of service at once, and what that does to each SIF,
each LOPA scenario and each protected item.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Two parts:
  build_model(g, findings, oos_rows)  reads the graph once into a small, plain model: per SIF its initiators,
                                      voting, configured overrides, final elements, compensating alarms and SRS
                                      conditions; per alarm whether it is available and what is in question
                                      about it; per LOPA scenario its credited layers.
  evaluate(model, out)                a pure function of the model and the set of elements taken out. No graph,
                                      no I/O, no text: states and codes only.
The page needs to answer any combination the presenter ticks, so the same function exists in JavaScript
(SITUATION_JS below). tests/test_situation.py runs both on every single element, every pair and several hundred
larger combinations and requires identical results: Python is the reference, the page is checked against it.

Rules (each is a statement about what the documents define, not a calculation of risk):
  S1 An initiator out with a configured override: the SIF runs the override's degraded voting (configuration).
  S2 An initiator out with no override configured: the vote is not defined - the bypass would be a force.
  S3 More than one initiator of a SIF out: not defined by the configuration or the SIL verification.
  S4 Every initiator out, or the SIF itself out: the SIF cannot trip.
  S5 Final elements follow the SRS architecture (NooM): fewer than N left = the safe state cannot be reached;
     otherwise degraded. No architecture stated = every final element is needed.
  S6 A compensating alarm counts only if it is not shelved, its transmitter is not out, it is configured and
     enabled, and no open finding puts its setting or its transmitter's range in question.
  S7 A SIF that is not normal needs at least one compensating alarm that counts, and every alarm its SRS
     bypass conditions name must count.
  S8 A LOPA layer is lost if its SIF cannot trip (or is undefined), its alarm does not count, or its device is
     out; "in question" if the SIF is degraded or the alarm has an open finding. Nothing is recalculated.

    python -m pid_graph.situation PT-1001B LT-1006.LAH        # U-100, those two out
    python -m pid_graph.situation --unit U-200 --as-found
"""
from __future__ import annotations

import argparse
import json
import re

from .ops_checks import MAX_H_RE, VOTE_RE, Graph, _id, _norm, _vote

IMPAIRING = ("C5", "C7", "C8")          # open findings that put an alarm's setting or its transmitter's range in question
LEVELS = ("ok", "warn", "stop")


def _noom(text) -> dict | None:
    m = VOTE_RE.search(str(text or ""))
    return {"n": int(m.group(1)), "m": int(m.group(2)), "text": f"{m.group(1)}oo{m.group(2)}"} if m else None


def build_model(g: Graph, findings: list[dict], oos_rows: list[dict] | None = None) -> dict:
    alarms_cfg = any(n["props"].get("cfg_ref") for (lab, _), n in g.nodes.items() if lab == "Alarm")
    alarms = {}
    for (lab, aid), n in sorted(g.nodes.items()):
        if lab != "Alarm":
            continue
        p = n["props"]
        cap, src = p.get("alarm_tag", aid), g.source_of(aid)
        unavailable = []
        if p.get("stub"):
            unavailable.append("not_in_any_register")
        if alarms_cfg and p.get("madb_ref") and not p.get("cfg_ref"):
            unavailable.append("not_configured")
        if _norm(p.get("enabled_cfg")) in ("no", "n", "false", "0"):
            unavailable.append("disabled")
        impaired = [{"code": f["code"], "detail": f["detail"]} for f in findings
                    if f["code"] in IMPAIRING and (f["id"] == cap or (f["code"] == "C7" and f["id"] == src))]
        alarms[aid] = {"caption": cap, "source": src, "unavailable": unavailable, "impaired": impaired}

    sifs = []
    for (lab, sid), n in sorted(g.nodes.items()):
        if lab != "SIF":
            continue
        p = n["props"]
        cfg, ce = g.initiators(sid, "CFG"), g.initiators(sid, "CE")
        inits, src = (cfg, "configuration") if cfg else (ce, "C&E")
        voting = _noom(p.get("voting_cfg") if cfg else p.get("voting")) or {"n": len(inits), "m": len(inits), "text": ""}
        initiators = []
        for tag in sorted(inits):
            ip = g.p("Instrument", tag)
            ov = None
            if ip.get("override_switch"):
                mh = re.findall(r"\d+(?:\.\d+)?", str(ip.get("override_max_h", "")))
                ov = {"switch": ip["override_switch"], "degraded": _vote(ip.get("override_degraded_voting")),
                      "max_h": float(mh[0]) if mh else None}
            initiators.append({"tag": tag, "override": ov})
        acts = {}
        for r in g.out("ACTUATES", "SIF", sid):
            acts.setdefault(_id(r, "end"), r["props"].get("action", ""))
        cms = sorted(({"alarm": _id(r, "start"), "rank": str(r["props"].get("rank", "")), "basis": r["props"].get("basis", "")}
                      for r in g.inc("COMPENSATES_FOR", "SIF", sid)), key=lambda c: (c["rank"], c["alarm"]))
        cond = p.get("bypass_conditions", "")
        mx = MAX_H_RE.search(cond)
        named = sorted(a for a, al in alarms.items() if re.search(rf"\b{re.escape(al['caption'])}\b", cond))
        sifs.append({"id": sid, "description": p.get("description") or p.get("functional_description", ""),
                     "voting": {**voting, "source": src}, "initiators": initiators,
                     "silv_degraded": _vote(p.get("degraded_sensor_voting_silv")), "fe": _noom(p.get("fe_architecture")),
                     "final_elements": [{"tag": t, "action": a} for t, a in sorted(acts.items())], "cms": cms,
                     "srs_named": named, "bypass_conditions": cond, "max_h": float(mx.group(1)) if mx else None,
                     "protects": sorted({_id(r, "end") for r in g.out("PROTECTS", "SIF", sid)})})

    scenarios = []
    for (lab, sc), n in sorted(g.nodes.items()):
        if lab != "Scenario":
            continue
        layers = []
        for r in sorted(g.out("CREDITS", "Scenario", sc), key=lambda r: (r["end_label"], _id(r, "end"))):
            lid = _id(r, "end")
            cap = alarms[lid]["caption"] if r["end_label"] == "Alarm" and lid in alarms else lid
            layers.append({"label": r["end_label"], "id": lid, "caption": cap, "pfd": r["props"].get("pfd"),
                           "ipl_type": r["props"].get("ipl_type", "")})
        scenarios.append({"id": sc, "consequence": n["props"].get("consequence", ""), "layers": layers,
                          "threatens": sorted({_id(r, "end") for r in g.out("THREATENS", "Scenario", sc)})})

    elements, seen = [], set()

    def add(eid, label, caption, group, note=""):
        if eid not in seen:
            seen.add(eid)
            elements.append({"id": eid, "label": label, "caption": caption, "group": group, "note": note})
    for s in sifs:
        for i in s["initiators"]:
            add(i["tag"], "Instrument", i["tag"], "Trip initiators", s["id"])
    for s in sifs:
        for f in s["final_elements"]:
            add(f["tag"], "Instrument", f["tag"], "Final elements", ", ".join(x["id"] for x in sifs if any(y["tag"] == f["tag"] for y in x["final_elements"])))
    for aid, al in alarms.items():
        add(aid, "Alarm", al["caption"], "Alarms", al["source"])
    for s in sifs:
        add(s["id"], "SIF", s["id"], "Whole safety function", s["description"])
    for sc in scenarios:
        for layer in sc["layers"]:
            if layer["label"] == "Instrument":
                add(layer["id"], "Instrument", layer["id"], "Other credited devices", layer["ipl_type"])

    as_found = set()
    for (lab, tag), n in g.nodes.items():
        p = n["props"]
        if lab == "Instrument" and _norm(p.get("override_active")) in ("yes", "y", "true") and p.get("block_type_cfg") != "MOS":
            as_found.add(tag)
    by_caption = {al["caption"]: aid for aid, al in alarms.items()}
    recorded = set()
    for r in oos_rows or []:
        if r.get("status") != "active":
            continue
        el = r.get("element", "")
        el = by_caption.get(el, g.p("Instrument", el).get("overrides", el))     # an alarm tag, or a switch -> what it overrides
        if el in seen:
            recorded.add(el)
    return {"alarms": alarms, "sifs": sifs, "scenarios": scenarios, "elements": elements, "export_time": g.export_time(),
            "presets": {"as_found": sorted(as_found | recorded), "recorded": sorted(recorded)}}


# ---------------------------------------------------------------- the reference implementation
def alarm_state(model: dict, alarm: str, out: set) -> str:
    al = model["alarms"].get(alarm)
    if al is None:
        return "unknown"
    if alarm in out:
        return "shelved"
    if al["source"] in out:
        return "source_out"
    if al["unavailable"]:
        return "unavailable"
    if al["impaired"]:
        return "impaired"
    return "ok"


def evaluate(model: dict, out_list) -> dict:
    out = set(out_list)
    worst = lambda levels: LEVELS[max([LEVELS.index(x) for x in levels] or [0])]     # noqa: E731
    sifs = []
    for s in model["sifs"]:
        tags = [i["tag"] for i in s["initiators"]]
        gone = [t for t in tags if t in out]
        left = [t for t in tags if t not in out]
        sensor = {"state": "normal", "effective": s["voting"]["text"], "out": gone, "remaining": left}
        violations = []
        if gone:
            ov = next(i["override"] for i in s["initiators"] if i["tag"] == gone[0])
            if not left:
                sensor.update(state="lost", effective="")                                          # S4
            elif len(gone) > 1:
                sensor.update(state="undefined", effective="")                                     # S3
                violations.append({"code": "multiple_channels", "items": gone})
            elif ov is None:
                sensor.update(state="undefined", effective="")                                     # S2
                violations.append({"code": "no_override", "items": gone})
            else:
                sensor.update(state="degraded", effective=ov["degraded"])                          # S1
                if s["silv_degraded"] and ov["degraded"] and s["silv_degraded"] != ov["degraded"]:
                    violations.append({"code": "silv_mismatch", "items": [s["silv_degraded"], ov["degraded"]]})
        fes = [f["tag"] for f in s["final_elements"]]
        fgone = [t for t in fes if t in out]
        fleft = [t for t in fes if t not in out]
        fe = {"state": "normal", "effective": s["fe"]["text"] if s["fe"] else "", "out": fgone, "remaining": fleft}
        if fgone:                                                                                  # S5
            need = s["fe"]["n"] if s["fe"] else len(fes)
            if len(fleft) < need:
                fe.update(state="lost", effective="")
            else:
                fe.update(state="degraded", effective=f"{need}oo{len(fleft)}")
        if s["id"] in out:
            status = "out"
        elif sensor["state"] == "lost" or fe["state"] == "lost":
            status = "lost"
        elif sensor["state"] == "undefined":
            status = "undefined"
        elif sensor["state"] == "degraded" or fe["state"] == "degraded":
            status = "degraded"
        else:
            status = "normal"
        cms = [{"alarm": c["alarm"], "caption": model["alarms"].get(c["alarm"], {}).get("caption", c["alarm"]),
                "rank": c["rank"], "state": alarm_state(model, c["alarm"], out)} for c in s["cms"]]
        if status != "normal":                                                                     # S7
            bad = [a for a in s["srs_named"] if alarm_state(model, a, out) != "ok"]
            if bad:
                violations.append({"code": "srs_alarm_unavailable", "items": bad})
            if not any(c["state"] == "ok" for c in cms):
                violations.append({"code": "no_valid_cm", "items": []})
        level = "ok" if status == "normal" else "warn" if status == "degraded" and not violations else "stop"
        sifs.append({"id": s["id"], "status": status, "sensor": sensor, "fe": fe, "cms": cms, "violations": violations, "level": level})
    status_of = {s["id"]: s["status"] for s in sifs}
    scenarios = []
    for sc in model["scenarios"]:                                                                  # S8
        layers = []
        for layer in sc["layers"]:
            if layer["label"] == "SIF":
                st = status_of.get(layer["id"], "normal")
                state = "ok" if st == "normal" else "degraded" if st == "degraded" else "lost"
            elif layer["label"] == "Alarm":
                st = alarm_state(model, layer["id"], out)
                state = "ok" if st == "ok" else "degraded" if st == "impaired" else "lost"
            else:
                state = "lost" if layer["id"] in out else "ok"
            layers.append({"id": layer["id"], "caption": layer["caption"], "label": layer["label"], "pfd": layer["pfd"], "state": state})
        level = "stop" if any(x["state"] == "lost" for x in layers) else "warn" if any(x["state"] == "degraded" for x in layers) else "ok"
        scenarios.append({"id": sc["id"], "layers": layers, "ok": sum(x["state"] == "ok" for x in layers), "total": len(layers), "level": level})
    equipment = []
    for tag in sorted({t for s in model["sifs"] for t in s["protects"]}):
        mine = [{"id": s["id"], "status": status_of[s["id"]]} for s in model["sifs"] if tag in s["protects"]]
        equipment.append({"tag": tag, "sifs": mine, "level": worst([x["level"] for x in sifs if any(m["id"] == x["id"] for m in mine)])})
    return {"out": sorted(out), "sifs": sifs, "scenarios": scenarios, "equipment": equipment,
            "level": worst([s["level"] for s in sifs] + [s["level"] for s in scenarios])}


# The same function for the page. Keep the two in step: tests/test_situation.py compares them.
SITUATION_JS = r"""
function alarmState(M, a, out){
  const al = M.alarms[a];
  if (!al) return 'unknown';
  if (out.has(a)) return 'shelved';
  if (out.has(al.source)) return 'source_out';
  if (al.unavailable.length) return 'unavailable';
  if (al.impaired.length) return 'impaired';
  return 'ok';
}
function evaluateSituation(M, outList){
  const LEVELS = ['ok', 'warn', 'stop'];
  const out = new Set(outList);
  const worst = ls => LEVELS[Math.max(0, ...ls.map(x => LEVELS.indexOf(x)))];
  const sifs = M.sifs.map(s => {
    const tags = s.initiators.map(i => i.tag), gone = tags.filter(t => out.has(t)), left = tags.filter(t => !out.has(t));
    const sensor = {state: 'normal', effective: s.voting.text, out: gone, remaining: left};
    const violations = [];
    if (gone.length){
      const ov = s.initiators.find(i => i.tag === gone[0]).override;
      if (!left.length){ sensor.state = 'lost'; sensor.effective = ''; }
      else if (gone.length > 1){ sensor.state = 'undefined'; sensor.effective = ''; violations.push({code: 'multiple_channels', items: gone}); }
      else if (ov === null){ sensor.state = 'undefined'; sensor.effective = ''; violations.push({code: 'no_override', items: gone}); }
      else { sensor.state = 'degraded'; sensor.effective = ov.degraded;
        if (s.silv_degraded && ov.degraded && s.silv_degraded !== ov.degraded) violations.push({code: 'silv_mismatch', items: [s.silv_degraded, ov.degraded]}); }
    }
    const fes = s.final_elements.map(f => f.tag), fgone = fes.filter(t => out.has(t)), fleft = fes.filter(t => !out.has(t));
    const fe = {state: 'normal', effective: s.fe ? s.fe.text : '', out: fgone, remaining: fleft};
    if (fgone.length){
      const need = s.fe ? s.fe.n : fes.length;
      if (fleft.length < need){ fe.state = 'lost'; fe.effective = ''; }
      else { fe.state = 'degraded'; fe.effective = need + 'oo' + fleft.length; }
    }
    let status = 'normal';
    if (out.has(s.id)) status = 'out';
    else if (sensor.state === 'lost' || fe.state === 'lost') status = 'lost';
    else if (sensor.state === 'undefined') status = 'undefined';
    else if (sensor.state === 'degraded' || fe.state === 'degraded') status = 'degraded';
    const cms = s.cms.map(c => ({alarm: c.alarm, caption: (M.alarms[c.alarm] || {}).caption || c.alarm, rank: c.rank, state: alarmState(M, c.alarm, out)}));
    if (status !== 'normal'){
      const bad = s.srs_named.filter(a => alarmState(M, a, out) !== 'ok');
      if (bad.length) violations.push({code: 'srs_alarm_unavailable', items: bad});
      if (!cms.some(c => c.state === 'ok')) violations.push({code: 'no_valid_cm', items: []});
    }
    const level = status === 'normal' ? 'ok' : (status === 'degraded' && !violations.length) ? 'warn' : 'stop';
    return {id: s.id, status, sensor, fe, cms, violations, level};
  });
  const statusOf = {}; sifs.forEach(s => statusOf[s.id] = s.status);
  const scenarios = M.scenarios.map(sc => {
    const layers = sc.layers.map(l => {
      let state;
      if (l.label === 'SIF'){ const st = statusOf[l.id] || 'normal'; state = st === 'normal' ? 'ok' : st === 'degraded' ? 'degraded' : 'lost'; }
      else if (l.label === 'Alarm'){ const st = alarmState(M, l.id, out); state = st === 'ok' ? 'ok' : st === 'impaired' ? 'degraded' : 'lost'; }
      else state = out.has(l.id) ? 'lost' : 'ok';
      return {id: l.id, caption: l.caption, label: l.label, pfd: l.pfd, state};
    });
    const level = layers.some(x => x.state === 'lost') ? 'stop' : layers.some(x => x.state === 'degraded') ? 'warn' : 'ok';
    return {id: sc.id, layers, ok: layers.filter(x => x.state === 'ok').length, total: layers.length, level};
  });
  const tags = [...new Set(M.sifs.flatMap(s => s.protects))].sort();
  const equipment = tags.map(tag => {
    const mine = M.sifs.filter(s => s.protects.includes(tag)).map(s => ({id: s.id, status: statusOf[s.id]}));
    return {tag, sifs: mine, level: worst(sifs.filter(x => mine.some(m => m.id === x.id)).map(x => x.level))};
  });
  return {out: [...out].sort(), sifs, scenarios, equipment, level: worst(sifs.map(s => s.level).concat(scenarios.map(s => s.level)))};
}
"""

WORDS = {"normal": "normal", "degraded": "DEGRADED", "lost": "CANNOT TRIP", "out": "OUT OF SERVICE", "undefined": "NOT DEFINED"}


def describe(model: dict, res: dict) -> str:
    """Plain-text summary for the command line."""
    lines = [f"Out of service: {', '.join(res['out']) or 'nothing'}    overall: {res['level'].upper()}"]
    for s in res["sifs"]:
        lines.append(f"  {s['id']}: {WORDS[s['status']]}" + (f" (sensors {s['sensor']['effective']})" if s["sensor"]["state"] == "degraded" else "")
                     + (f"; final elements {s['fe']['state']}" if s["fe"]["state"] != "normal" else ""))
        for v in s["violations"]:
            lines.append(f"      - {v['code']}" + (f": {', '.join(v['items'])}" if v["items"] else ""))
        if s["status"] != "normal":
            lines.append("      compensating: " + (", ".join(f"{c['caption']} [{c['state']}]" for c in s["cms"]) or "none curated"))
    for sc in res["scenarios"]:
        lines.append(f"  {sc['id']}: {sc['ok']} of {sc['total']} layers available - "
                     + ", ".join(f"{x['caption']} [{x['state']}]" for x in sc["layers"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="What happens with these elements out of service together?")
    ap.add_argument("elements", nargs="*", help="tags, alarm ids (PT-1005.PAH) or alarm tags (PAH-1005), SIF ids")
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--as-found", action="store_true", help="start from what the configuration export shows as overridden")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from .demo import build
    model = build(unit=a.unit)["situation"]
    by_caption = {al["caption"]: aid for aid, al in model["alarms"].items()}
    known = {e["id"] for e in model["elements"]}
    out = set(model["presets"]["as_found"]) if a.as_found else set()
    for e in a.elements:
        e = by_caption.get(e.upper(), e.upper())
        if e not in known:
            print(f"not something that can be taken out of service here: {e}")
            return 2
        out.add(e)
    res = evaluate(model, out)
    print(json.dumps(res, indent=1) if a.json else describe(model, res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
