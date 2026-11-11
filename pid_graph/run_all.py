"""Phase 1 end to end for one process unit.

    python -m pid_graph --unit U-100 --backend memory
    python -m pid_graph --unit U-100 --backend neo4j

Steps: load index -> load topology -> (neo4j: schema, wipe unit, write, read back)
       -> reconcile + exception register -> gold-set eval -> reports/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ontology as O
from .pipeline import build_store, new_load_run
from .reconcile import reconcile, write_register

ROOT = Path(__file__).resolve().parent.parent


def banner(n: int, text: str) -> None:
    print(f"\n{'=' * 78}\nSTEP {n}  {text}\n{'=' * 78}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--index", default=str(ROOT / "data" / "U100-INST-INDEX-Rev-B.xlsx"))
    ap.add_argument("--index-sheet", default="Instrument Index")
    ap.add_argument("--alarm-sheet", default="Alarm Register")
    ap.add_argument("--topology", default=str(ROOT / "data" / "pid_audit_U100_topology.csv"))
    ap.add_argument("--ce", default=str(ROOT / "data" / "U100-CE-CHART-Rev-A.xlsx"), help="C&E chart -> SIF nodes (Phase 2); '' to skip")
    ap.add_argument("--ce-sheet", default=None)
    ap.add_argument("--curated", default=str(ROOT / "data" / "curated" / "compensating_measures_U-100.csv"),
                    help="curated compensating-measures register; only approved rows load; '' to skip")
    ap.add_argument("--srs", default=str(ROOT / "data" / "U100-SRS-001-Rev-B.xlsx"), help="SRS register (v1.2); '' to skip")
    ap.add_argument("--lopa", default=str(ROOT / "data" / "U100-LOPA-001-Rev-A.xlsx"), help="LOPA register (v1.2); '' to skip")
    ap.add_argument("--pdf", default=None, help="Aconex per-unit P&ID PDF; title blocks give drawing revisions")
    ap.add_argument("--transmittal", default=None, help="Aconex transmittal number, stamped into load_run")
    ap.add_argument("--pidkg", default="", help="pid-to-kg graph.json (v1.3 vision layer); off by default, and off means the v1.2 graph")
    ap.add_argument("--gold", default=str(ROOT / "eval" / "gold_PID-100-001.json"))
    ap.add_argument("--backend", choices=["memory", "neo4j"], default="memory")
    ap.add_argument("--load-run", default=None, help="run id stamped on every node/edge (default: timestamp)")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    load_run = a.load_run or new_load_run(a.transmittal or "run")
    revs = None
    store = None
    if a.pdf:
        banner(0, f"Read P&ID title blocks from {Path(a.pdf).name} (transmittal {a.transmittal or '-'})")
        from .loaders.titleblock import diff_against_store, read_title_blocks, register_drawings
        from .records import MemoryStore
        records = read_title_blocks(a.pdf)
        for r in records:
            print(f"  page {r['page']:>3}: {r['doc_no'] or '-':<14} rev {r['rev'] or '-':<3} sheet {r['sheet'] or '-'}/{r['of'] or '-'}  "
                  f"text layer {'yes' if r['has_text_layer'] else 'NO'}  {r['title'][:50]}")
        if a.backend == "neo4j":
            from .db import DATABASE, get_driver
            from .neo4j_store import Neo4jStore
            from .loaders.titleblock import rev_map as _rm
            d0 = get_driver()
            try:
                diff = diff_against_store(_rm(records)[0], Neo4jStore(d0, DATABASE))
            finally:
                d0.close()
            print(f"  vs graph: new {[x['doc_no'] for x in diff['new']]}, revised {[(x['doc_no'], x['from'], x['to']) for x in diff['revised']]}, "
                  f"unchanged {[x['doc_no'] for x in diff['unchanged']]}")
            print(f"  re-extract: {diff['re_extract']}")
            reports_diff = diff
        else:
            reports_diff = None

    banner(1, f"Load instrument index -> Instrument nodes  (unit {a.unit}, load_run {load_run})")
    store, reports = build_store(unit=a.unit, index=a.index, topology=None, load_run=load_run, pdf=a.pdf,
                                 transmittal=a.transmittal, index_sheet=a.index_sheet, alarm_sheet=a.alarm_sheet or None)
    if a.pdf:
        tb = reports["titleblock"]
        revs = tb["rev_map"]
        reports["titleblock"]["diff_vs_graph"] = reports_diff
        print(f"  title blocks: {tb['pages']} pages, {tb['drawings']} drawings {tb['rev_map']}, problems {len(tb['problems'])}")
        for p in tb["problems"]:
            print(f"    PROBLEM page {p['page']}: {p['problem']}")
    ir = reports["index"]
    print(f"  {ir['file']} -> document {ir['document']['doc_no']} rev {ir['document']['rev']} (from {ir['document']['detected_from']})")
    print(f"  rows {ir['rows']}, instruments {ir['instruments']}, alarms {ir['alarms']}, skipped {len(ir['skipped'])}")
    for s in ir["skipped"]:
        print(f"    SKIP {s['ref']}: {s['value']!r} - {s['reason']}")
    for n in ir["notes"]:
        print(f"    NOTE {n}")
    print(f"  store: {store.counts()}")

    if a.ce:
        banner(2, "Load cause & effect chart -> SIF, INITIATES, ACTUATES, PROTECTS")
        from .loaders.ce_loader import load_ce
        cr = load_ce(store, a.ce, unit=a.unit, load_run=load_run, sheet=a.ce_sheet)
        reports["ce"] = cr
        print(f"  {cr['file']} -> document {cr['document']['doc_no']} rev {cr['document']['rev']} (from {cr['document']['detected_from']})")
        print(f"  rows {cr['rows']}: SIFs {cr['sifs']}, INITIATES {cr['initiates']}, ACTUATES {cr['actuates']}, PROTECTS {cr['protects']}")
        print(f"  C&E-only instruments (stubs): {[x['tag'] for x in cr['ce_only_instruments']]}")
        print(f"  RAISES {cr['raises']}, CASCADES_TO {cr['cascades']}; alarm effects not in register (stubs): {[x['alarm_tag'] for x in cr['ce_only_alarms']]}")
        for s in cr["skipped"]:
            print(f"    SKIP {s['ref']}: {s['reason']}")
        for n in cr["notes"]:
            print(f"    NOTE {n}")
        print(f"  store: {store.counts()}")

    if a.srs and Path(a.srs).exists():
        banner(2, "Load SRS register -> requirements on SIF nodes (v1.2)")
        from .loaders.srs_loader import load_srs
        sr = load_srs(store, a.srs, unit=a.unit, load_run=load_run)
        reports["srs"] = sr
        print(f"  {sr['file']} -> document {sr['document']['doc_no']} rev {sr['document']['rev']}: {sr['sifs']} SIF(s), "
              f"SRS-only SIFs {[x['sif_id'] for x in sr['srs_only_sifs']]}, PROTECTS {sr['protects']}")
        for n in sr["notes"]:
            print(f"    NOTE {n}")
    if a.lopa and Path(a.lopa).exists():
        banner(2, "Load LOPA register -> Scenario, THREATENS, CREDITS (v1.2)")
        from .loaders.lopa_loader import load_lopa
        lr = load_lopa(store, a.lopa, unit=a.unit, load_run=load_run)
        reports["lopa"] = lr
        print(f"  {lr['file']} -> document {lr['document']['doc_no']} rev {lr['document']['rev']}: scenarios {lr['scenarios']}, "
              f"CREDITS {lr['credits']}, THREATENS {lr['threatens']}")
        print(f"  credited but not in registers (stubs): {[(x['kind'], x['id']) for x in lr['lopa_only']]}")
        print(f"  not representable: {[(x['id'], x['reason']) for x in lr['unrepresentable']]}")
        for s in lr["skipped"]:
            print(f"    SKIP {s['ref']}: {s['reason']}")
    if a.curated and Path(a.curated).exists():
        banner(2, "Load curated compensating measures -> COMPENSATES_FOR (approved rows only)")
        from .loaders.curated_loader import load_curated
        ur = load_curated(store, a.curated, unit=a.unit, load_run=load_run)
        reports["curated"] = ur
        print(f"  {ur['file']} rev {ur['document']['rev']}: rows {ur['rows']}, loaded {ur['loaded']}, "
              f"proposed {len(ur['proposed'])}, gaps {len(ur['gaps'])}, skipped {len(ur['skipped'])}")
        for p in ur["proposed"]:
            print(f"    PROPOSED {p['sif_id']:<11} <- {p['alarm_id']:<14} rank {p['rank']} {p['basis']}  (not loaded until approved)")
        for g in ur["gaps"]:
            print(f"    GAP      {g['sif_id']:<11} {g['rationale'][:90]}...")
        for s in ur["skipped"]:
            print(f"    SKIP {s['ref']}: {s['reason']}")

    banner(3, "Load pid_audit topology -> INSTALLED_ON / FEEDS / SHOWN_ON")
    from .loaders.pid_loader import load_topology
    tr = load_topology(store, a.topology, unit=a.unit, load_run=load_run, rev_map=revs)
    reports["topology"] = tr
    print(f"  {tr['file']}: {tr['rows']} rows over sheets {tr['sheets']}")
    print(f"  P&ID-only instruments (stubs): {[x['tag'] for x in tr['pid_only_instruments']]}")
    print(f"  off-page stubs: {[x['tag'] for x in tr['offpage_stubs']]}")
    print(f"  low confidence: {[(x['from'], x['to'], x['confidence']) for x in tr['low_confidence']]}")
    for s in tr["skipped"]:
        print(f"    SKIP {s['ref']}: {s['reason']}")
    for u in tr["unplaced"]:
        print(f"    UNPLACED {u['ref']}: {u['from']} -> {u['to']}: {u['reason']}")
    pidkg = None
    if a.pidkg:
        banner(3, "Load pid-to-kg vision extraction -> Segment, InlineItem, ControlLoop (v1.3; every fact review=pending)")
        from . import review as RV
        from .load_pidkg import apply as pidkg_apply, index_tags, print_report, reconcile as pidkg_reconcile
        # The review register is an input: read the engineer's decisions first, then write it back.
        reg_path = out / f"review_register_{a.unit}.xlsx"
        register, problems = RV.read_register(reg_path)
        pidkg = pidkg_reconcile(json.loads(Path(a.pidkg).read_text(encoding="utf-8")), index_tags(store), store,
                                unit=a.unit, load_run=load_run, review=RV.decisions(register))
        print_report(pidkg)
        pidkg_apply(store, pidkg)
        reports["pidkg"] = pidkg["summary"]
        RV.write_register(pidkg, reg_path, unit=a.unit, previous=register)
        rs = RV.summarise(RV.merged_rows(pidkg, register), a.unit)
        reports["review"] = {"register": str(reg_path), **{k: rs[k] for k in ("facts", "pending", "accepted", "rejected", "pending_priority")},
                             "problems": problems}
        print(f"  review register: {rs['facts']} facts - pending {rs['pending']} ({rs['pending_priority']} priority), "
              f"accepted {rs['accepted']}, rejected {rs['rejected']} -> {reg_path}")
        for p in problems:
            print(f"    REVIEW PROBLEM {p}")
        if a.pdf:
            mk = RV.markup(a.pdf, pidkg, out / f"review_markup_{a.unit}.pdf", register=register)
            reports["review"]["markup"] = str(mk)
            print(f"  review markup -> {mk}")
    counts = store.counts()
    reports["counts"] = counts
    print(f"  store: {counts['nodes']} nodes {counts['by_label']}")
    print(f"         {counts['rels']} rels  {counts['by_rel']}")
    print(f"  property conflicts: {len(store.conflicts)}")
    (out / f"graph_{a.unit}.json").write_text(json.dumps(store.to_dict(), indent=1, default=str), encoding="utf-8")

    read_store = store
    driver = None
    if a.backend == "neo4j":
        banner(4, "Neo4j: constraints, wipe unit, MERGE, read back")
        from .db import DATABASE, get_driver
        from .neo4j_store import Neo4jStore
        driver = get_driver()
        neo = Neo4jStore(driver, DATABASE)
        for stmt in neo.ensure_schema():
            print(f"  {stmt}")
        print(f"  wiped {neo.wipe_unit(a.unit)} nodes of unit {a.unit}")
        w = neo.write(store)
        print(f"  written: {w}")
        db_counts = neo.counts()
        print(f"  database now: {db_counts}")
        reports["neo4j"] = {"written": w, "counts": db_counts}
        read_store = neo
        oos_path = ROOT / "data" / "oos" / f"out_of_service_{a.unit}.csv"
        if oos_path.exists():
            from .oos import apply as oos_apply, load_register
            res = oos_apply(driver, load_register(oos_path), a.unit, oos_path.name)
            print(f"  out-of-service register re-applied: {len(res['applied'])} active, {len(res['missing'])} unmatched")
        banner(5, "Reconcile (reading back from Neo4j)")
    else:
        banner(4, "Neo4j skipped (--backend memory); staged graph written to reports/")
        banner(5, "Reconcile (in-memory store)")

    rec = reconcile(read_store, unit=a.unit, ce_report=reports.get("ce"), titleblock_report=reports.get("titleblock"),
                    curated_report=reports.get("curated"), lopa_report=reports.get("lopa"))
    if a.pdf and reports.get("titleblock", {}).get("diff_vs_graph"):
        rec["summary"]["drawings_revised_since_last_load"] = [x["doc_no"] for x in reports["titleblock"]["diff_vs_graph"]["revised"]]
    if a.backend == "neo4j" and store.conflicts:
        # Conflicts are detected at merge time in memory; carry them into the register.
        from .records import MemoryStore
        tmp = MemoryStore()
        tmp.conflicts = store.conflicts
        rec["exceptions"] += [e for e in reconcile(tmp, unit=a.unit)["exceptions"] if e["code"] == "X6"]
        rec["summary"]["exceptions"] = len(rec["exceptions"])
    if pidkg:
        # Vision exceptions (X21-X29) join the same register; they are produced by the loader, not re-derived here.
        rec["exceptions"] += pidkg["exceptions"]
        rec["summary"]["exceptions"] = len(rec["exceptions"])
        for e in pidkg["exceptions"]:
            rec["summary"]["exceptions_by_code"][e["code"]] = rec["summary"]["exceptions_by_code"].get(e["code"], 0) + 1
    reg = write_register(rec, out / f"exception_register_{a.unit}.xlsx")
    for k, v in rec["summary"].items():
        print(f"  {k:32} {v}")
    print(f"  -> {reg}")
    for e in rec["exceptions"]:
        print(f"    {e['code']} {e['label']:<12} {e['id']:<22} {e['detail']}")

    banner(6, "Gold-set evaluation")
    sys.path.insert(0, str(ROOT))
    from eval.score import print_scores, score
    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    ev = score(read_store, gold)
    print_scores(ev)
    reports["reconcile"] = rec["summary"]
    reports["eval"] = {k: v for k, v in ev.items()}
    (out / f"load_report_{a.unit}.json").write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    (out / f"eval_{ev['sheet']}.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
    print(f"\n  reports -> {out}")
    if driver is not None:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
