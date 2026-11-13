"""U-200 blind-test document set (batch 2): the committed files are what the generator writes, the sealed
answer key reads back from them cell by cell, and the existing loaders take every row.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

This test is about the DOCUMENTS only. It deliberately does not import pid_graph.ops_checks, pid_graph.demo
or pid_graph.reconcile, and it names no planted item: every expectation is derived from the generator
(scripts/make_dummy_batch2.py) or from the key itself, so reading this file gives nothing away.
DUMMY DATA - not a real facility.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

from pid_graph.loaders.tables import DOCREG_ALIASES, INDEX_ALIASES, MOC_ALIASES, detect_document, read_table
from pid_graph.pipeline import build_store

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "u200"


def _generator():
    spec = importlib.util.spec_from_file_location("make_dummy_batch2", ROOT / "scripts" / "make_dummy_batch2.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod             # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    return mod


GEN = _generator()


# ---- reading the files back, independently of the generator's own tables ----

def _rows(path: Path, sheet: str | None) -> list[list]:
    if path.suffix == ".xlsx":
        return [list(r) for r in load_workbook(path, data_only=True)[sheet].iter_rows(values_only=True)]
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.reader(f)]


def _content(path: Path):
    """Everything in a file that matters: cell values per sheet, CSV rows, or parsed JSON. Never bytes."""
    if path.suffix == ".xlsx":
        wb = load_workbook(path, data_only=True)
        return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return _rows(path, None)


def _same(a, b) -> bool:
    blank = (None, "")
    return (a in blank and b in blank) or a == b


def _header_row(rows: list[list], column: str) -> int:
    for i, r in enumerate(rows):
        if column in r and sum(v not in (None, "") for v in r) >= 2:
            return i
    raise AssertionError(f"no header row holds {column!r}")


def _cells(file: str, sheet: str | None, row, column: str) -> list:
    """The values under `column` in every data row whose first cell is `row`."""
    rows = _rows(DATA / file, sheet)
    h = _header_row(rows, column)
    j = rows[h].index(column)
    return [r[j] if j < len(r) else None for r in rows[h + 1:] if r and r[0] == row]


def _column(file: str, sheet: str | None, column: str | None) -> list:
    rows = _rows(DATA / file, sheet)
    if column is None:                                   # first column, below whichever row is the header
        column = next(t.header[0] for (f, s), t in GEN.build_tables().items() if (f, s) == (file, sheet))
    h = _header_row(rows, column)
    j = rows[h].index(column)
    return [r[j] for r in rows[h + 1:] if len(r) > j]


@pytest.fixture(scope="module")
def key() -> dict:
    return json.loads((DATA / GEN.F_KEY).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def unit() -> dict:
    return json.loads((DATA / GEN.F_UNIT).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def loaded(unit):
    f = {k: (DATA / v if v else None) for k, v in unit["files"].items()}
    return build_store(unit=unit["unit"], load_run="test-batch2", index=f["index"], topology=f["topology"], ce=f["ce"],
                       srs=f["srs"], lopa=f["lopa"], curated=f["curated"], madb=f["madb"], config=f["config"],
                       silv=f["silv"], moc=f["moc"], docreg=f["docreg"])


# ---- the committed set is the generator's output ----

def test_committed_files_are_what_the_generator_writes(tmp_path):
    written = GEN.build(tmp_path)
    assert len(written) == len({p.name for p in written})
    for p in written:
        committed = DATA / p.name
        assert committed.exists(), f"{p.name} is generated but not committed under data/u200/"
        assert _content(committed) == _content(p), f"{p.name}: committed content differs from the generator's"
    extra = {p.name for p in DATA.iterdir() if p.is_file()} - {p.name for p in written} - {GEN.F_BLIND}
    assert not extra, f"files under data/u200/ the generator does not write: {sorted(extra)}"


def test_generator_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for pa, pb in zip(GEN.build(a), GEN.build(b)):
        assert _content(pa) == _content(pb)
        assert pa.read_bytes() == pb.read_bytes(), f"{pa.name}: two runs differ byte for byte"
    for p in a.glob("*.xlsx"):
        props = load_workbook(p).properties
        assert props.created == GEN.STAMP and props.modified == GEN.STAMP, f"{p.name}: workbook timestamp is not fixed"


def test_unit_json_has_the_agreed_shape(unit):
    assert set(unit) == {"unit", "files", "oos", "blind"}
    assert unit["unit"] == "U-200"
    assert set(unit["files"]) == {"index", "ce", "srs", "lopa", "curated", "madb", "config", "silv", "moc", "docreg",
                                  "topology", "pdf"}
    assert unit["files"]["topology"] is None and unit["files"]["pdf"] is None
    for name, rel in unit["files"].items():
        if rel is not None:
            assert (DATA / rel).is_file(), f"unit.json files.{name} -> {rel} does not exist"
    assert (DATA / unit["oos"]).is_file()
    assert unit["blind"] == "U200-BLIND-ADJUDICATION.json"


def test_size_of_the_set():
    """The brief's envelope, counted from the generator's own description of the plant."""
    assert 25 <= len(GEN.INSTRUMENTS) <= 40
    assert 3 <= len(GEN.SIFS) <= 5 and {s["voting"] for s in GEN.SIFS} >= {"1oo1", "1oo2", "2oo3"}
    assert 10 <= len([a for a in GEN.ALARMS if a["status"] != "Removed"]) <= 16
    assert 3 <= len(GEN.SCENARIOS) <= 5
    assert 6 <= len(GEN.MOCS) <= 10 and len({m[3] for m in GEN.MOCS}) >= 4
    assert 12 <= len(GEN.DOCREG) <= 20


# ---- the sealed key ----

def test_key_is_well_formed(key):
    assert key["unit"] == "U-200"
    items = key["items"]
    assert 18 <= len(items) <= 24
    assert [i["id"] for i in items] == [f"B2-{n:02d}" for n in range(1, len(items) + 1)]
    for i in items:
        assert set(i) == {"id", "category", "severity", "tags", "documents", "finding", "evidence", "absent"}
        assert i["severity"] in ("high", "medium", "low")
        assert i["tags"] and i["finding"].strip() and i["category"].strip()
        assert len(set(i["documents"])) >= 2, f"{i['id']}: a discrepancy is between documents"
        assert i["evidence"], f"{i['id']}: no evidence"
        assert len({e["file"] for e in i["evidence"] + i["absent"]}) >= 2, f"{i['id']}: evidence comes from one file only"
    assert {i["severity"] for i in items} == {"high", "medium", "low"}
    assert 5 <= len(key["clean_controls"]) <= 8
    for c in key["clean_controls"]:
        assert c["description"].strip() and c["tags"]


def test_key_is_what_the_generator_builds(key):
    assert key == GEN.build_key(GEN.build_tables())


def test_every_evidence_cell_reads_back_from_the_files(key):
    for item in key["items"]:
        for e in item["evidence"]:
            found = _cells(e["file"], e["sheet"], e["row"], e["column"])
            assert found, f"{item['id']}: {e['file']}:{e['sheet']}: no row {e['row']!r}"
            assert any(_same(v, e["value"]) for v in found), \
                f"{item['id']}: {e['file']}:{e['sheet']}:{e['row']}:{e['column']} holds {found}, key says {e['value']!r}"


def test_every_absent_row_is_absent(key):
    n = 0
    for item in key["items"]:
        for a in item["absent"]:
            assert a["row"] not in _column(a["file"], a["sheet"], a.get("column")), \
                f"{item['id']}: {a['row']!r} is present in {a['file']}:{a['sheet']}"
            n += 1
    assert n, "the key lists no absent rows at all"


# ---- document identity and the register ----

def test_detect_document_reads_every_title_row():
    for (file, sheet), doc in GEN.SHEET_DOCS.items():
        doc_no, rev, how = detect_document(DATA / file, sheet)
        assert (doc_no, rev) == (doc, GEN.REV[doc]), f"{file}:{sheet}: detected {doc_no} Rev {rev} ({how})"
        assert how.startswith("title row"), f"{file}:{sheet}: identity came from {how}, not from the title rows"
    # the workbook file names agree with their title rows
    for (file, sheet), doc in GEN.SHEET_DOCS.items():
        if file.endswith(".xlsx") and doc in file:
            assert file == f"{doc}-Rev-{GEN.REV[doc]}.xlsx"


def test_every_document_is_in_the_document_register():
    register = {r["doc_no"]: r["rev"] for r in read_table(DATA / GEN.F_DOCREG, None, DOCREG_ALIASES)}
    assert len(register) == len(GEN.DOCREG), "duplicate document numbers in the register"
    for doc in set(GEN.SHEET_DOCS.values()):
        assert register.get(doc) == GEN.REV[doc], f"{doc} Rev {GEN.REV[doc]} is not in the register as such"
    # documents other documents point at: the index's drawings and the MOC register's revision lists
    for r in read_table(DATA / GEN.F_INDEX, "Instrument Index", INDEX_ALIASES):
        assert r["pid_sheet"] in register, f"{r['tag']}: drawing {r['pid_sheet']} is not registered"
    for r in read_table(DATA / GEN.F_MOC, None, MOC_ALIASES):
        for doc in [d.strip() for col in ("to_revise", "revised") for d in r.get(col, "").split(";") if d.strip()]:
            assert doc in register, f"{r['moc_no']}: {doc} is not registered"


def test_a_trip_is_never_an_alarm_in_the_master_alarm_database():
    madb = _rows(DATA / GEN.F_MADB, "Alarms")
    h = _header_row(madb, "Alarm Tag")
    tags = {r[0] for r in madb[h + 1:]}
    types = {str(r[madb[h].index("Alarm Type")]).lower() for r in madb[h + 1:]}
    assert not any("trip" in t for t in types)
    cfg = _rows(DATA / GEN.F_CFG, "Alarms")
    hc = _header_row(cfg, "Alarm Tag")
    notifications = {r[0] for r in cfg[hc + 1:] if "TRIP" in str(r[cfg[hc].index("Alarm Type")]).upper()}
    assert notifications and not notifications & tags


# ---- the existing loaders take the whole set ----

def _key_tags(key) -> set[str]:
    return {t for i in key["items"] for t in i["tags"]} | {t for c in key["clean_controls"] for t in c["tags"]}


def test_loaders_detect_every_document(loaded, unit):
    _, reports = loaded
    for name in ("index", "ce", "srs", "lopa", "madb", "config", "silv", "moc", "docreg"):
        doc = reports[name]["document"]
        assert doc["rev"] == GEN.REV[doc["doc_no"]], f"{name}: {doc}"
        assert doc["detected_from"].startswith("title row"), f"{name}: {doc}"
    assert reports["config"]["export_time"] == GEN.EXPORT_TIME


def test_loaders_take_every_row(loaded):
    store, r = loaded
    assert not store.conflicts
    live = [a for a in GEN.ALARMS]
    assert (r["index"]["rows"], r["index"]["instruments"]) == (len(GEN.INSTRUMENTS),) * 2
    assert r["index"]["alarms"] == len([a for a in live if a["in_register"]])
    assert r["ce"]["sifs"] == len(GEN.SIFS) and r["ce"]["initiates"] == sum(len(s["sensors"]) for s in GEN.SIFS)
    assert r["ce"]["protects"] == len(GEN.SIFS) and not r["ce"]["ce_only_instruments"] and not r["ce"]["ce_only_sifs"]
    assert r["srs"]["sifs"] == len(GEN.SIFS) and not r["srs"]["srs_only_sifs"]
    assert r["lopa"]["scenarios"] == r["lopa"]["threatens"] == len(GEN.SCENARIOS) and not r["lopa"]["unrepresentable"]
    credited = sum(1 for c in GEN.SCENARIOS for *_, pfd in c["ipls"] if pfd is not None)
    assert r["lopa"]["credits"] == credited          # the Required SIF and its IPL row are one relationship per document
    assert r["curated"]["rows"] == len(GEN.CURATED)
    assert r["curated"]["loaded"] == len([c for c in GEN.CURATED if c[6] == "approved"]) and not r["curated"]["proposed"]
    assert r["madb"]["rows"] == r["madb"]["alarms"] == len(live)
    assert r["config"]["alarms"] == len([a for a in live if a["in_cfg"]]) + 1
    assert r["config"]["initiates"] == r["ce"]["initiates"] and r["config"]["overrides"] == r["ce"]["initiates"]
    assert set(r["config"]["loops_skipped"]) == {lp[0] for lp in GEN.LOOPS}
    assert r["silv"]["sifs"] == len(GEN.SIFS)
    assert r["moc"]["mocs"] == len(GEN.MOCS)
    assert r["docreg"]["documents"] == len(GEN.DOCREG) and not r["docreg"]["unknown_types"]


def test_whatever_the_loaders_could_not_place_is_accounted_for_in_the_key(loaded, key):
    """A row that does not load cleanly must trace to a key item or a clean control, never to a layout mistake."""
    _, r = loaded
    tags = _key_tags(key)
    switches = {row[0] for row in GEN.build_tables()[(GEN.F_CFG, "Overrides")].rows}   # stubs by design of the loader
    leftovers = (
        [e["id"] for e in r["lopa"]["lopa_only"]] + r["madb"]["new_alarms"] + r["config"]["new_alarms"]
        + [t for t in r["config"]["cfg_only_points"] if t not in switches]
        + [e["tag"] for e in r["silv"]["unknown_tags"]] + [e["tag"] for e in r["moc"]["tags_not_in_graph"]]
        + [e["name"] for e in r["docreg"]["unresolved"]] + [e["sif_id"] for e in r["curated"]["gaps"]]
        + [e["tag"] for e in r["ce"]["ce_only_instruments"]])
    for name in leftovers:
        assert name in tags, f"{name} did not load cleanly and no key item or clean control names it"
    for name in ("index", "ce", "srs", "lopa", "curated", "madb", "config", "silv", "moc"):
        for entry in r[name]["skipped"]:
            text = json.dumps(entry)
            assert any(t in text for t in tags), f"{name}: unexpected skipped row {entry}"
