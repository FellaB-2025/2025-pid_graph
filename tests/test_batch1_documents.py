"""Batch 1 of the U-100 test documents: SIL verification, MADB, DCS/SIS configuration export, MOC register.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The documents are fabricated by scripts/make_dummy_batch1.py with planted discrepancies. These tests check
that the committed files are what the generator writes, that every planted item is really in the files
(each evidence cell is read back), that every tag is either in the instrument index or deliberately not, and
that the documents agree with the existing U-100 registers wherever nothing was planted.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"

from pid_graph.loaders.tables import DOCREG_ALIASES, detect_document, read_table  # noqa: E402


def _script():
    spec = importlib.util.spec_from_file_location("make_dummy_batch1", ROOT / "scripts" / "make_dummy_batch1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _script()
KEY = json.loads((DATA / GEN.KEY).read_text(encoding="utf-8"))


def _table(path: Path, sheet: str) -> list[dict]:
    """Rows under the header on row 4, as dicts."""
    rows = list(load_workbook(path, read_only=True)[sheet].iter_rows(values_only=True))
    header = rows[3]
    return [dict(zip(header, r)) for r in rows[4:] if any(v is not None for v in r)]


def _all_cells(path: Path) -> list[dict]:
    return [r for name in load_workbook(path, read_only=True).sheetnames for r in _table(path, name)]


def _index() -> dict[str, dict]:
    return {r["Tag No."]: r for r in _table(DATA / "U100-INST-INDEX-Rev-B.xlsx", "Instrument Index")}


def test_the_committed_files_are_what_the_generator_writes(tmp_path):
    GEN.write_all(tmp_path)
    for name in KEY["documents"]:
        for sheet in load_workbook(DATA / name, read_only=True).sheetnames:
            assert _table(DATA / name, sheet) == _table(tmp_path / name, sheet), (name, sheet)
    assert json.loads((tmp_path / GEN.KEY).read_text(encoding="utf-8")) == KEY


@pytest.mark.parametrize("name,doc", [(GEN.SILV, "U100-SILV-001"), (GEN.MADB, "U100-MADB-001"),
                                      (GEN.CFG, "U100-CFG-EXPORT"), (GEN.MOCR, "U100-MOC-REG")])
def test_each_document_states_its_number_and_revision(name, doc):
    assert detect_document(DATA / name)[:2] == (doc, "A")


def test_every_new_document_is_in_the_document_register():
    registered = {(r["doc_no"], r["rev"]) for r in read_table(DATA / "U100-DOC-REGISTER.csv", None, DOCREG_ALIASES)}
    for name in KEY["documents"]:
        assert detect_document(DATA / name)[:2] in registered, name


def test_every_planted_item_is_in_the_files():
    for item in KEY["items"]:
        for ev in item.get("evidence", []):
            rows = [r for r in _table(DATA / ev["file"], ev["sheet"]) if list(r.values())[0] == ev["row"]]
            assert rows, (item["id"], ev)
            assert rows[0][ev["column"]] == ev["value"], (item["id"], ev, rows[0][ev["column"]])
        for ab in item.get("absent", []):
            rows = _table(DATA / ab["file"], ab["sheet"])
            if "row" in ab:
                assert all(list(r.values())[0] != ab["row"] for r in rows), (item["id"], ab)
            else:
                assert all(r[ab["column"]] != ab["value"] for r in rows), (item["id"], ab)
        assert item.get("evidence") or item.get("absent"), item["id"]


def test_the_answer_key_is_well_formed():
    ids = [i["id"] for i in KEY["items"]]
    assert len(ids) == len(set(ids))
    questions = {f"Q{n}" for n in range(1, 9)}
    for item in KEY["items"]:
        assert item["questions"] and set(item["questions"]) <= questions, item["id"]
        assert item["documents"] and item["tags"] and item["finding"], item["id"]
    # every question in the inventory has at least one planted item to find
    assert {q for i in KEY["items"] for q in i["questions"]} == questions


def test_every_tag_is_in_the_index_or_deliberately_not():
    index = _index()
    alarm_tags = {r["Alarm Tag"] for r in _table(DATA / GEN.MADB, "Alarms")} | \
                 {r["Alarm Tag"] for r in _table(DATA / GEN.CFG, "Alarms")}
    named = set()
    for r in _table(DATA / GEN.CFG, "Points"):
        named.add(r["Point Tag"])
    for r in _table(DATA / GEN.CFG, "Overrides"):
        named |= {r["Override Tag"], r["Element"]}
    for f, sheet, col in ((GEN.CFG, "Alarms", "Source Tag"), (GEN.MADB, "Alarms", "Source Tag")):
        named |= {r[col] for r in _table(DATA / f, sheet)}
    for f, sheet, col in ((GEN.CFG, "SIS Trips", "Initiators"), (GEN.CFG, "SIS Trips", "Final Elements"),
                          (GEN.SILV, "Subsystems", "Tags")):
        named |= {t.strip() for r in _table(DATA / f, sheet) for t in r[col].split(",")}
    named -= {"SIS-LS-100"} | alarm_tags
    loops = {r["Loop No."] for r in _table(DATA / "U100-INST-INDEX-Rev-B.xlsx", "Loop Register")}
    stray = named - set(index) - loops - set(KEY["not_in_index"])
    assert not stray, stray
    # and the exceptions really are exceptions, each one named in a planted item or a MOC
    assert not set(KEY["not_in_index"]) & set(index)
    unused = set(KEY["not_in_index"]) - named
    assert not unused, unused


def test_configured_points_agree_with_the_index_except_where_planted():
    index = _index()
    planted_ranges = {"PT-1005"}                                   # B1-09
    for p in _table(DATA / GEN.CFG, "Points"):
        idx = index.get(p["Point Tag"])
        if not idx or p["Point Tag"] in planted_ranges or not idx["Range"]:
            continue
        assert idx["Range"].replace(" to ", "-") == f"{p['Range Low']}-{p['Range High']}", p["Point Tag"]
        assert idx["Units"] == p["Units"], p["Point Tag"]
        assert (idx["System"] == "SIS") == (p["System"] == "SIS"), p["Point Tag"]


def test_every_alarm_in_the_index_alarm_register_is_in_the_madb_and_agrees():
    madb = {r["Alarm Tag"]: r for r in _table(DATA / GEN.MADB, "Alarms")}
    for a in _table(DATA / "U100-INST-INDEX-Rev-B.xlsx", "Alarm Register"):
        m = madb[a["Alarm Tag"]]
        assert m["Source Tag"] == a["Source Tag"]
        assert f"{m['Setpoint']} {m['Units']}" == a["Setpoint"]
        assert m["Priority"] == a["Priority"]


def test_configured_alarms_agree_with_the_madb_except_where_planted():
    madb = {r["Alarm Tag"]: r for r in _table(DATA / GEN.MADB, "Alarms")}
    planted = {"PAH-1001": "Limit", "LAH-1006": "Priority"}       # B1-06, B1-07
    for c in _table(DATA / GEN.CFG, "Alarms"):
        m = madb.get(c["Alarm Tag"])
        if not m:
            continue                                             # B1-14 / B1-16 are the only ones (tested above)
        assert c["Source Tag"] == m["Source Tag"], c["Alarm Tag"]
        if c["Limit"] is not None and planted.get(c["Alarm Tag"]) != "Limit":
            assert str(c["Limit"]) == m["Setpoint"], c["Alarm Tag"]
        if planted.get(c["Alarm Tag"]) != "Priority":
            assert c["Priority"] == m["Priority"], c["Alarm Tag"]


def test_sis_trips_agree_with_the_ce_chart_on_setpoints_and_final_elements():
    ce = DATA / "U100-CE-CHART-Rev-A.xlsx"
    text = " ".join(str(v) for ws in load_workbook(ce, read_only=True).worksheets
                    for row in ws.iter_rows(values_only=True) for v in row if v is not None)
    for t in _table(DATA / GEN.CFG, "SIS Trips"):
        assert t["SIF No."] in text
        for fe in t["Final Elements"].split(", "):
            assert fe in text


def test_the_moc_register_matches_the_moc_records():
    mocs = {r["MOC No."]: r for r in _table(DATA / GEN.MOCR, "Register")}
    for path in sorted((DATA / "moc").glob("MOC-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        row = mocs[rec["moc_id"]]
        assert row["Title"] == rec["title"] and row["Raised"] == rec["date"]
        tags = set(row["Tags Affected"].split("; "))
        assert rec["sif"] in tags and set(rec["new_initiators"]) <= tags


def test_every_document_a_moc_names_is_registered_or_a_drawing():
    registered = {r["doc_no"] for r in read_table(DATA / "U100-DOC-REGISTER.csv", None, DOCREG_ALIASES)}
    registered |= {"U100-ALM-REG", "U100-LOOP-REG"}                       # sheets of the instrument index
    for m in _table(DATA / GEN.MOCR, "Register"):
        for col in ("Documents to Revise", "Documents Revised"):
            for d in filter(None, (m[col] or "").split("; ")):
                assert d in registered or d.startswith("PID-100-"), (m["MOC No."], d)


def test_the_sil_figures_follow_from_the_subsystem_data():
    subs = _table(DATA / GEN.SILV, "Subsystems")
    for s in _table(DATA / GEN.SILV, "SIF Summary"):
        parts = [r["PFDavg"] for r in subs if r["SIF No."] == s["SIF No."]]
        assert s["PFDavg"] == pytest.approx(sum(parts), rel=1e-2)
        assert s["RRF Achieved"] == pytest.approx(1 / s["PFDavg"], rel=1e-2)
        assert s["SIL Achieved"] == GEN.sil(s["PFDavg"])
    # the planted B1-02 consequence: as installed, SIF-100-02 falls short of the LOPA's RRF 100
    assert 25 <= 1 / GEN.as_installed_sif_100_02() < 100


def test_no_trip_is_rationalised_as_an_alarm_in_the_madb():
    """A trip notification is not an alarm (PAHH-1001 is planted in the configuration, B1-16)."""
    assert all("HH" not in r["Alarm Tag"] and "LL" not in r["Alarm Tag"] for r in _table(DATA / GEN.MADB, "Alarms"))
