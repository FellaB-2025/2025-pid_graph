"""Phase 3: live out-of-service register, combined protection status, handover and trip pack."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph.oos import active_rows, add_entry, load_register  # noqa: E402

DEMO = """id,element,kind,status,start,expiry,authorised_by,requester,reason,compensating_measures_confirmed,notes
OOS-2026-041,XV-1001,bypass,active,2026-09-08 18:30,2026-09-09 02:30,Ops Superintendent (dummy),Shift Supervisor (dummy),Solenoid replacement,y,DUMMY
OOS-2026-042,LT-1006.LAH,shelve,active,2026-09-08 21:10,2026-09-09 09:00,Panel Operator (dummy),Panel Operator (dummy),Tuning,n,DUMMY
OOS-2026-038,PT-1001B,mos,closed,2026-09-07 08:00,2026-09-07 16:00,Ops Superintendent (dummy),Instrument Technician (dummy),Calibration,y,DUMMY
"""


def _demo_register(tmp_path):
    reg = tmp_path / "out_of_service_U-100.csv"
    reg.write_text(DEMO, encoding="utf-8")
    return reg


def test_add_entry_assigns_next_id(tmp_path):
    reg = _demo_register(tmp_path)
    row = add_entry(reg, "pt-1001a", "mos", hours=4, authorised_by="AB")
    assert row["id"] == "OOS-2026-043" and row["element"] == "PT-1001A" and row["status"] == "active"
    assert len(load_register(reg)) == 4


def test_register_parses_and_filters_active(tmp_path):
    REG = _demo_register(tmp_path)
    rows = load_register(REG)
    assert [r["id"] for r in rows] == ["OOS-2026-041", "OOS-2026-042", "OOS-2026-038"]
    act = active_rows(rows)
    assert {r["element"] for r in act} == {"XV-1001", "LT-1006.LAH"}
    assert [r["kind"] for r in act] == ["bypass", "shelve"]
    assert act[0]["cm_confirmed"] is True and act[1]["cm_confirmed"] is False


def _driver_or_skip():
    try:
        from pid_graph.db import get_driver
        d = get_driver()
        d.verify_connectivity()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j not available: {exc}")


def test_combined_protection_status_against_neo4j(tmp_path):
    """Stages the demo register in the graph for the test, then clears it again."""
    from pid_graph.oos import apply, protection_status
    REG = _demo_register(tmp_path)
    live = ROOT / "data" / "oos" / "out_of_service_U-100.csv"
    d = _driver_or_skip()
    try:
        res = apply(d, load_register(REG), "U-100", REG.name)
        assert len(res["applied"]) == 2 and res["missing"] == []
        st = protection_status(d, now=datetime(2026, 9, 8, 23, 0))
        by = {s["sif"]: s for s in st["sifs"]}
        assert by["SIF-100-01"]["status"] == "DEGRADED" and {m["alarm"] for m in by["SIF-100-01"]["measures_valid"]} == {"PT-1005.PAH", "PT-1001A.PAH"}
        assert by["SIF-100-02"]["status"] == "DEGRADED" and by["SIF-100-02"]["measures_valid"] == []
        assert any("LT-1006.LAH is shelved" in f for f in by["SIF-100-02"]["flags"])      # the compensating measure was removed
        assert by["SIF-100-03"]["status"] == "DEFEATED"
        assert {n["id"] for n in st["expiring_24h"]} == {"XV-1001", "LT-1006.LAH"}
        # re-applying is idempotent
        res2 = apply(d, load_register(REG), "U-100", REG.name)
        assert res2["cleared"] == 2 and len(res2["applied"]) == 2
    finally:
        # leave the graph in the state of the real register (whatever the user has in it)
        apply(d, load_register(live) if live.exists() else [], "U-100", live.name)
        d.close()
