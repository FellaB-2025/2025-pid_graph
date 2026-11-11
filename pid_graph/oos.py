"""Live out-of-service register: bypasses, maintenance overrides (MOS), shelved alarms,
interlock bypasses that are active right now.

Operational state, not a design document, so it is applied to the graph as properties
on the affected Instrument / Alarm nodes (oos_id, oos_kind, oos_start, oos_expiry,
oos_authorised_by, oos_reason, oos_cm_confirmed, oos_source) without a full rebuild:

    python -m pid_graph.oos apply            # clear old oos_* properties for the unit, set the active ones
    python -m pid_graph.oos list             # what is out of service now, and what expires soon
    python -m pid_graph.oos status           # per-SIF protection status given everything that is out

Register: data/oos/out_of_service_<unit>.csv with columns
  id, element, kind (bypass|mos|shelve|interlock_bypass), status (active|closed), start, expiry,
  authorised_by, requester, reason, compensating_measures_confirmed (y/n), notes
Dates are ISO 'YYYY-MM-DD HH:MM'. Only status=active rows are applied.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .db import DATABASE, get_driver
from .tags import canonical_tag

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("bypass", "mos", "shelve", "interlock_bypass")
VOTING_RE = re.compile(r"(\d+)\s*oo\s*(\d+)", re.I)
OOS_PROPS = ("oos_id", "oos_kind", "oos_start", "oos_expiry", "oos_authorised_by", "oos_requester", "oos_reason",
             "oos_cm_confirmed", "oos_notes", "oos_source")


def _parse_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def load_register(path: str | Path) -> list[dict]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for i, r in enumerate(rows, start=2):
        el = (r.get("element") or "").strip().upper()
        if "." in el:                                   # alarm id: <tag>.<type>
            tag, typ = el.split(".", 1)
            el = f"{canonical_tag(tag) or tag}.{typ}"
        else:
            el = canonical_tag(el) or el
        out.append({"id": (r.get("id") or "").strip(), "element": el, "kind": (r.get("kind") or "").strip().lower(),
                    "status": (r.get("status") or "").strip().lower(), "start": (r.get("start") or "").strip(),
                    "expiry": (r.get("expiry") or "").strip(), "authorised_by": (r.get("authorised_by") or "").strip(),
                    "requester": (r.get("requester") or "").strip(), "reason": (r.get("reason") or "").strip(),
                    "cm_confirmed": (r.get("compensating_measures_confirmed") or "").strip().lower() in ("y", "yes", "true", "1"),
                    "notes": (r.get("notes") or "").strip(), "ref": f"{path.name}:{i}"})
    return out


def active_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["status"] == "active" and r["kind"] in KINDS]


FIELDS = ["id", "element", "kind", "status", "start", "expiry", "authorised_by", "requester", "reason",
          "compensating_measures_confirmed", "notes"]


def _read_raw(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return FIELDS, []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or FIELDS), list(reader)


def _write_raw(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def next_id(rows: list[dict]) -> str:
    year = datetime.now().year
    nums = [int(m.group(1)) for r in rows for m in [re.match(rf"OOS-{year}-(\d+)$", (r.get("id") or "").strip().upper())] if m]
    return f"OOS-{year}-{(max(nums) + 1) if nums else 1:03d}"


def add_entry(path: str | Path, element: str, kind: str, *, hours: float = 8, authorised_by: str = "", requester: str = "",
              reason: str = "", cm_confirmed: bool = False, notes: str = "", start: datetime | None = None) -> dict:
    """Append an active entry. The element must be a tag (XV-1001) or alarm id (PT-1005.PAH)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    path = Path(path)
    fields, rows = _read_raw(path)
    start = start or datetime.now()
    row = {"id": next_id(rows), "element": element.strip().upper(), "kind": kind, "status": "active",
           "start": start.strftime("%Y-%m-%d %H:%M"), "expiry": (start + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M"),
           "authorised_by": authorised_by, "requester": requester, "reason": reason,
           "compensating_measures_confirmed": "y" if cm_confirmed else "n", "notes": notes}
    rows.append({f: row.get(f, "") for f in fields})
    _write_raw(path, fields, rows)
    return row


def remove_entries(path: str | Path, ids: list[str] | None = None, *, everything: bool = False) -> list[str]:
    """Delete rows outright (no history) - for staging demonstrations. Use close_entries for real restorations."""
    path = Path(path)
    fields, rows = _read_raw(path)
    if everything:
        removed = [r["id"] for r in rows]
        _write_raw(path, fields, [])
        return removed
    wanted = {i.strip().upper() for i in (ids or [])}
    keep = [r for r in rows if (r.get("id") or "").strip().upper() not in wanted]
    removed = [r["id"] for r in rows if (r.get("id") or "").strip().upper() in wanted]
    _write_raw(path, fields, keep)
    return removed


def close_entries(path: str | Path, ids: list[str], by: str = "") -> list[dict]:
    """Mark register rows closed (status=closed, restoration time appended to notes). Rows are kept as history."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    wanted = {i.strip().upper() for i in ids}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    closed = []
    for r in rows:
        if (r.get("id") or "").strip().upper() in wanted and (r.get("status") or "").strip().lower() == "active":
            r["status"] = "closed"
            note = f"Restored {stamp}" + (f" by {by}" if by else "")
            r["notes"] = ((r.get("notes") or "").strip() + " " + note).strip()
            closed.append({"id": r["id"].strip().upper(), "kind": r.get("kind", ""), "element": r.get("element", ""), "closed_at": stamp})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return closed


def apply(driver, rows: list[dict], unit: str, source: str) -> dict:
    """Clear every oos_* property on the unit's nodes, then set them for active rows. Idempotent."""
    with driver.session(database=DATABASE) as s:
        cleared = s.run("MATCH (n) WHERE n.unit = $unit AND n.oos_id IS NOT NULL "
                        "REMOVE " + ", ".join(f"n.{p}" for p in OOS_PROPS) + " RETURN count(n) AS c", unit=unit).single()["c"]
        applied, missing = [], []
        for r in active_rows(rows):
            res = s.run("MATCH (n) WHERE (n:Instrument AND n.tag = $el) OR (n:Alarm AND n.alarm_id = $el) "
                        "SET n.oos_id = $id, n.oos_kind = $kind, n.oos_start = $start, n.oos_expiry = $expiry, "
                        "n.oos_authorised_by = $auth, n.oos_requester = $req, n.oos_reason = $reason, "
                        "n.oos_cm_confirmed = $cm, n.oos_notes = $notes, n.oos_source = $src "
                        "RETURN labels(n)[0] AS label", el=r["element"], id=r["id"], kind=r["kind"], start=r["start"],
                        expiry=r["expiry"], auth=r["authorised_by"], req=r["requester"], reason=r["reason"],
                        cm=r["cm_confirmed"], notes=r["notes"], src=f"{source}:{r['ref']}").single()
            (applied if res else missing).append({**r, "label": res["label"] if res else None})
    return {"cleared": cleared, "applied": applied, "missing": missing}


# ---- protection status given everything that is out (the combined question) ----------------

def protection_status(driver, now: datetime | None = None) -> dict:
    """Per SIF: UNAFFECTED / DEGRADED / DEFEATED given every active bypass, MOS and shelved alarm."""
    now = now or datetime.now()
    with driver.session(database=DATABASE) as s:
        out_nodes = [r.data() for r in s.run(
            "MATCH (n) WHERE n.oos_id IS NOT NULL RETURN labels(n)[0] AS label, coalesce(n.tag, n.alarm_id) AS id, "
            "n.oos_id AS oos_id, n.oos_kind AS kind, n.oos_start AS start, n.oos_expiry AS expiry, n.oos_authorised_by AS authorised_by, "
            "n.oos_requester AS requester, n.oos_reason AS reason, n.oos_cm_confirmed AS cm_confirmed, n.oos_notes AS notes ORDER BY n.oos_expiry")]
        sifs = [r.data() for r in s.run(
            "MATCH (sf:SIF) WHERE NOT coalesce(sf.stub, false) "
            "OPTIONAL MATCH (i:Instrument)-[ini:INITIATES]->(sf) "
            "WITH sf, collect(DISTINCT {tag: i.tag, voting: ini.voting, out: i.oos_id IS NOT NULL, kind: i.oos_kind}) AS inits "
            "OPTIONAL MATCH (sf)-[a:ACTUATES]->(fe:Instrument) "
            "WITH sf, inits, collect(DISTINCT {tag: fe.tag, action: a.action, out: fe.oos_id IS NOT NULL, kind: fe.oos_kind}) AS fes "
            "OPTIONAL MATCH (c:Alarm)-[cf:COMPENSATES_FOR]->(sf) OPTIONAL MATCH (c)<-[:GENERATES]-(src:Instrument) "
            "WITH sf, inits, fes, collect(DISTINCT {alarm: c.alarm_id, rank: cf.rank, basis: cf.basis, conditions: cf.conditions, "
            "shelved: c.oos_id IS NOT NULL, shelve_id: c.oos_id, source_tag: src.tag, source_out: src.oos_id IS NOT NULL}) AS cms "
            "OPTIONAL MATCH (sf)-[:PROTECTS]->(p) "
            "RETURN sf.sif_id AS sif, sf.sil AS sil, sf.description AS description, "
            "[x IN inits WHERE x.tag IS NOT NULL] AS initiators, [x IN fes WHERE x.tag IS NOT NULL] AS final_elements, "
            "[x IN cms WHERE x.alarm IS NOT NULL] AS measures, collect(DISTINCT coalesce(p.tag, p.line_no)) AS protects ORDER BY sif")]
    for n in out_nodes:
        exp = _parse_dt(n["expiry"])
        n["expired"] = bool(exp and exp < now)
        n["expires_within_h"] = round((exp - now).total_seconds() / 3600, 1) if exp else None
    for sf in sifs:
        touched = any(i["out"] for i in sf["initiators"]) or any(f["out"] for f in sf["final_elements"])
        init_ok = True
        detail = []
        for vote in sorted({i["voting"] or "" for i in sf["initiators"]}):
            group = [i for i in sf["initiators"] if (i["voting"] or "") == vote]
            need = int(VOTING_RE.search(vote).group(1)) if vote and VOTING_RE.search(vote) else 1
            remaining = [i["tag"] for i in group if not i["out"]]
            if any(i["out"] for i in group):
                detail.append(f"initiators {vote or '1oo1'}: {len(remaining)} of {len(group)} in service ({', '.join(remaining) or 'NONE'}), needs {need}")
            if len(remaining) < need:
                init_ok = False
        remaining_fe = [f["tag"] for f in sf["final_elements"] if not f["out"]]
        final_ok = bool(remaining_fe) or not sf["final_elements"]
        if any(f["out"] for f in sf["final_elements"]):
            detail.append(f"final elements: {len(remaining_fe)} of {len(sf['final_elements'])} in service ({', '.join(remaining_fe) or 'NONE'})")
        sf["status"] = "UNAFFECTED" if not touched else ("DEFEATED" if not (init_ok and final_ok) else "DEGRADED")
        sf["detail"] = "; ".join(detail)
        valid = [m for m in sf["measures"] if not m["shelved"] and not m["source_out"]]
        lost = [m for m in sf["measures"] if m["shelved"] or m["source_out"]]
        sf["measures_valid"] = valid
        sf["measures_lost"] = lost
        sf["flags"] = []
        if sf["status"] != "UNAFFECTED" and not valid:
            sf["flags"].append("NO VALID COMPENSATING MEASURE while degraded/defeated")
        for m in lost:
            if sf["status"] != "UNAFFECTED":
                sf["flags"].append(f"compensating measure {m['alarm']} is {'shelved (' + m['shelve_id'] + ')' if m['shelved'] else 'from an element that is itself out'} while the SIF is {sf['status']}")
    return {"as_of": now.strftime("%Y-%m-%d %H:%M"), "out_of_service": out_nodes, "sifs": sifs,
            "expiring_24h": [n for n in out_nodes if n["expires_within_h"] is not None and n["expires_within_h"] <= 24],
            "expired": [n for n in out_nodes if n["expired"]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["apply", "list", "status", "close", "add", "remove"])
    ap.add_argument("ids", nargs="*", help="close/remove: register ids (OOS-2026-041); add: the element (XV-1001 or PT-1005.PAH)")
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--register", default=None)
    ap.add_argument("--by", default="", help="close: who restored it; add: who authorised it")
    ap.add_argument("--kind", choices=list(KINDS), default="bypass", help="add: bypass | mos | shelve | interlock_bypass")
    ap.add_argument("--hours", type=float, default=8, help="add: authorised duration from now")
    ap.add_argument("--requester", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--cm-confirmed", action="store_true", help="add: compensating measures confirmed in place")
    ap.add_argument("--all", action="store_true", help="remove: delete every entry")
    ap.add_argument("--no-apply", action="store_true", help="add/remove/close: edit the file only, do not touch the graph")
    a = ap.parse_args(argv)
    reg = Path(a.register) if a.register else ROOT / "data" / "oos" / f"out_of_service_{a.unit}.csv"

    def reapply():
        if a.no_apply:
            return
        d = get_driver()
        try:
            res = apply(d, load_register(reg), a.unit, reg.name)
            print(f"  register applied to the graph: {len(res['applied'])} active" + (f", UNMATCHED {[m['element'] for m in res['missing']]} (not in graph - check the tag)" if res["missing"] else ""))
            print("  regenerate the explorer to see it: python -m pid_graph.explorer")
        finally:
            d.close()

    if a.cmd == "add":
        if len(a.ids) != 1:
            ap.error("add needs exactly one element, e.g. add XV-1001 --kind bypass --hours 8")
        row = add_entry(reg, a.ids[0], a.kind, hours=a.hours, authorised_by=a.by, requester=a.requester, reason=a.reason, cm_confirmed=a.cm_confirmed)
        print(f"  added {row['id']}: {row['kind']} {row['element']} {row['start']} -> {row['expiry']}")
        reapply()
        return 0
    if a.cmd == "remove":
        if not a.ids and not a.all:
            ap.error("remove needs register ids or --all")
        removed = remove_entries(reg, a.ids, everything=a.all)
        print(f"  removed {removed or 'nothing'}")
        reapply()
        return 0
    if a.cmd == "close":
        if not a.ids:
            ap.error("close needs at least one register id")
        closed = close_entries(reg, a.ids, by=a.by)
        for c in closed:
            print(f"  closed {c['id']} ({c['kind']} {c['element']}) at {c['closed_at']}{(' by ' + a.by) if a.by else ''}")
        missing = [i for i in a.ids if i.upper() not in {c["id"] for c in closed}]
        for m in missing:
            print(f"  NOT FOUND or not active: {m}")
        reapply()
        return 0 if not missing else 1
    driver = get_driver()
    try:
        if a.cmd == "apply":
            rows = load_register(reg)
            res = apply(driver, rows, a.unit, reg.name)
            print(f"cleared {res['cleared']} node(s); applied {len(res['applied'])} active entr{'y' if len(res['applied']) == 1 else 'ies'}")
            for r in res["applied"]:
                print(f"  {r['id']:<13} {r['kind']:<8} {r['element']:<14} ({r['label']}) until {r['expiry']}  auth {r['authorised_by']}")
            for r in res["missing"]:
                print(f"  MISSING {r['id']} {r['element']}: not in graph - check the tag")
        else:
            st = protection_status(driver)
            print(f"as of {st['as_of']}")
            if a.cmd == "list":
                for n in st["out_of_service"]:
                    warn = " EXPIRED" if n["expired"] else (f" expires in {n['expires_within_h']} h" if n["expires_within_h"] is not None and n["expires_within_h"] <= 24 else "")
                    print(f"  {n['oos_id']:<13} {n['kind']:<8} {n['id']:<14} {n['start']} -> {n['expiry']}{warn}  cm confirmed: {'yes' if n['cm_confirmed'] else 'NO'}")
            else:
                for sf in st["sifs"]:
                    print(f"  {sf['sif']:<11} {sf['status']:<10} {sf['detail']}")
                    for m in sf["measures_valid"]:
                        print(f"      valid measure: {m['alarm']} (rank {m['rank']})")
                    for fl in sf["flags"]:
                        print(f"      FLAG: {fl}")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
