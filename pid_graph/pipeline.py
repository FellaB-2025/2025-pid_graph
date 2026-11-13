"""Build the staged graph for one unit from its documents. Shared by run_all and eval."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .loaders.ce_loader import load_ce
from .loaders.config_loader import load_config
from .loaders.curated_loader import load_curated
from .loaders.docreg_loader import load_docreg
from .loaders.index_loader import load_index
from .loaders.lopa_loader import load_lopa
from .loaders.madb_loader import load_madb
from .loaders.moc_loader import load_moc
from .loaders.pid_loader import load_topology
from .loaders.silv_loader import load_silv
from .loaders.srs_loader import load_srs
from .records import MemoryStore


def new_load_run(prefix: str = "run") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def build_store(*, unit: str, index: str | Path, topology: str | Path | None, load_run: str,
                ce: str | Path | None = None, ce_sheet: str | None = None, pdf: str | Path | None = None,
                transmittal: str | None = None, curated: str | Path | None = None,
                srs: str | Path | None = None, lopa: str | Path | None = None,
                index_sheet: str = "Instrument Index", alarm_sheet: str | None = "Alarm Register",
                madb: str | Path | None = None, config: str | Path | None = None, silv: str | Path | None = None,
                moc: str | Path | None = None, docreg: str | Path | None = None) -> tuple[MemoryStore, dict]:
    """Load order: P&ID title blocks -> index (master list) -> C&E -> SRS -> LOPA -> curated -> P&ID topology,
    then the operations documents, all off by default (D-V13-12): MADB -> configuration -> SIL verification ->
    MOC register -> document register (last, so it can link to everything the others created)."""
    store = MemoryStore()
    reports = {"load_run": load_run, "unit": unit}
    revs = None
    if pdf:
        from .loaders.titleblock import read_title_blocks, register_drawings
        records = read_title_blocks(pdf)
        reports["titleblock"] = register_drawings(store, records, unit=unit, load_run=load_run, transmittal=transmittal)
        revs = reports["titleblock"]["rev_map"]
    reports["index"] = load_index(store, index, unit=unit, load_run=load_run, sheet=index_sheet, alarm_sheet=alarm_sheet,
                                  rev_map=revs)
    if ce:
        reports["ce"] = load_ce(store, ce, unit=unit, load_run=load_run, sheet=ce_sheet)
    if srs:
        reports["srs"] = load_srs(store, srs, unit=unit, load_run=load_run)
    if lopa:
        reports["lopa"] = load_lopa(store, lopa, unit=unit, load_run=load_run)
    if curated:
        reports["curated"] = load_curated(store, curated, unit=unit, load_run=load_run)
    if topology:
        reports["topology"] = load_topology(store, topology, unit=unit, load_run=load_run, rev_map=revs)
    for name, path, fn in (("madb", madb, load_madb), ("config", config, load_config), ("silv", silv, load_silv),
                           ("moc", moc, load_moc), ("docreg", docreg, load_docreg)):
        if path:
            reports[name] = fn(store, path, unit=unit, load_run=load_run)
    reports["counts"] = store.counts()
    return store, reports
