"""The fixes made after the blind test on U-200 (docs/BLIND_TEST.md sections 6, 9 and 10).

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

U-200 is a regression test now, not a blind result (section 9, rule 3): the checks below were written after its
answer key was opened. The sealed findings and the adjudication stay as they were; one test here holds them still.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import demo, ops_checks as OC, quantities as Q  # noqa: E402

# planted item -> the check that must state it, and the element the finding is about
EXPECTED = {
    "B2-01": ("C17", "SIF-200-04"), "B2-02": ("C10", "SIF-200-02"), "B2-03": ("C10", "SIF-200-03"), "B2-04": ("C18", "SIF-200-01"),
    "B2-05": ("C14", "MOC-2026-034"), "B2-06": ("C13", "MOS-2030A"), "B2-07": ("C6", "LAH-2031"), "B2-08": ("C25", "LT-2030A"),
    "B2-09": ("C12", "MOS-2020A"), "B2-10": ("C7", "PT-2010B"), "B2-11": ("C2", "TT-2026"), "B2-12": ("C4", "PDAH-2003"),
    "B2-13": ("C9", "PAH-2014"), "B2-14": ("C26", "PAL-2014"), "B2-15": ("C5", "PAH-2041"), "B2-16": ("C5", "AAL-2024"),
    "B2-17": ("C9", "TAH-2022"), "B2-18": ("C25", "TAH-2022"), "B2-19": ("C19", "FAL-2002"), "B2-20": ("C20", "PT-2011"),
    "B2-21": ("C21", "TAH-2021"), "B2-22": ("C22", "TAL-2021"), "B2-23": ("C23", "SIF-200-05"), "B2-24": ("C24", "TT-2020C"),
}


@pytest.fixture(scope="module")
def u200():
    return demo.build(unit="U-200")


@pytest.fixture(scope="module")
def u100():
    return demo.build()


def _has(data, code, ident):
    return [f for f in data["findings"] if f["code"] == code and f["id"] == ident]


def _scenario(data, sid):
    return next(s for s in data["scenarios"] if s["id"] == sid)


# ---------------------------------------------------------------- values with units
def test_the_same_value_in_different_units_is_the_same_value():
    assert Q.same("350 mbarg", "0.35 barg") and Q.same("0.35barg", "0.35 barg") and Q.same("12 months", "1 year")
    assert Q.same("600 mm", "0.6 m") and Q.same("90 s", "1.5 min")
    assert not Q.same("345 degC", "355 degC") and not Q.same("0.3 barg", "0.6 barg")


def test_gauge_and_unstated_pressure_are_never_converted_into_each_other():
    assert not Q.same("6 bar", "6 barg")
    assert Q.same("6 bar", "6 barg", numbers_only=True)             # a range end, where the index often drops the g
    assert Q.compare("6 bar", "5 barg") is None


def test_values_can_be_ordered_only_on_one_scale():
    assert Q.compare("15 min", "90 s") == 1 and Q.compare("10 min", "20 min") == -1 and Q.compare("10 min", "600 s") == 0
    assert Q.compare("520 degC", "345 mm") is None and Q.compare("high", "low") is None


def test_a_limit_in_per_cent_of_span_is_read_through_the_index_range():
    block = {"range": "0-3000", "units": "mm", "range_cfg": "0-100", "units_cfg": "%"}
    assert OC.per_cent_block(block) and OC.in_index_units("20 %", block) == "600 mm" and OC.in_index_units("80 %", block) == "2400 mm"
    analyser = {"range": "0-10", "units": "%", "range_cfg": "0-10", "units_cfg": "%"}        # measured in per cent: not a scaling
    assert not OC.per_cent_block(analyser) and OC.in_index_units("1.5 %", analyser) == "1.5 %"
    assert OC.in_index_units("2.5 barg", block) == "2.5 barg"


def test_a_compound_proof_test_cell_is_two_statements():
    assert OC.proof_test_intervals("Sensors 12 months, final elements 24 months") == {"sensors": "12 months", "fe": "24 months"}
    assert OC.proof_test_intervals("12 months") == {"sensors": "12 months", "fe": "12 months"}
    assert OC.proof_test_intervals("Valves 2 years; 12 months otherwise") == {"sensors": "12 months", "fe": "2 years"}
    assert OC.proof_test_intervals("") == {}


# ---------------------------------------------------------------- U-200 as a regression test
def test_the_sealed_blind_record_is_still_the_record():
    sealed = json.loads((ROOT / "eval" / "blind" / "U200-BLIND-RUN-FINDINGS.json").read_text(encoding="utf-8"))
    scored = json.loads((ROOT / "data" / "u200" / "U200-BLIND-ADJUDICATION.json").read_text(encoding="utf-8"))
    assert sealed["freeze"] == "blind-freeze-1" and len(sealed["findings"]) == 85
    assert scored["freeze"] == "blind-freeze-1" and "Found 12 of 24, partial 3, missed 9" in scored["scorer_notes"]


def test_every_item_planted_in_u200_is_now_stated_by_a_finding(u200):
    key = json.loads((ROOT / "data" / "u200" / "U200-BATCH2-ANSWER-KEY.json").read_text(encoding="utf-8"))
    assert {i["id"] for i in key["items"]} == set(EXPECTED)
    missing = [k for k, (code, ident) in EXPECTED.items() if not _has(u200, code, ident)]
    assert missing == []
    assert "Final elements" in " ".join(f["detail"] for f in _has(u200, "C10", "SIF-200-03"))
    assert "0.35 barg" in _has(u200, "C26", "PAL-2014")[0]["detail"]
    assert "below the 200 now required" in _has(u200, "C18", "SIF-200-01")[0]["detail"]


def test_the_traps_that_were_sprung_by_units_and_wording_stay_quiet(u200):
    codes = lambda c: [f for f in u200["findings"] if f["code"] == c]      # noqa: E731
    assert not codes("X16")                                                # 350 mbarg is 0.35 barg
    assert not codes("C11")                                                # 'Sensors 12 months, final elements 24 months'
    assert not _has(u200, "C7", "LT-2040") and not _has(u200, "C5", "LAL-2040") and not _has(u200, "C5", "LAH-2040")
    assert not _has(u200, "C13", "MOS-2001B") and not _has(u200, "C24", "FT-2001B")      # a properly recorded bypass
    assert not _has(u200, "C25", "LAL-2031") and not _has(u200, "C22", "LAL-2031")       # a cancelled removal
    assert [f["level"] for f in _has(u200, "C3", "FALL-2001")] == ["info"]               # a trip is not an alarm


def test_a_rule_can_set_a_findings_level(u200):
    assert _has(u200, "C20", "PT-2011")[0]["level"] == "stop" and _has(u200, "C21", "TAH-2021")[0]["level"] == "stop"
    assert all(f["level"] in ("stop", "warn", "info") for f in u200["findings"])


def test_the_scenario_text_no_longer_contradicts_the_documents(u200):
    recorded = _scenario(u200, "bypass:FT-2001B")
    text = " ".join(s["text"] for s in recorded["steps"])
    assert "OOS-200-0010" in text and "has no entry" not in text and recorded["verdict"]["level"] != "stop"
    for sif in ("SIF-200-03", "SIF-200-04"):
        v = _scenario(u200, f"trip:{sif}")["verdict"]
        assert v["level"] == "warn" and "agree on how this SIF trips" not in v["text"]
    assert _scenario(u200, "bypass:PT-2011")["verdict"]["level"] == "stop"
    assert _scenario(u200, "closeout:MOC-2026-039")["verdict"]["level"] != "ok"           # closed, but the DCS still alarms at 6 barg
    assert _scenario(u200, "closeout:MOC-2026-044")["verdict"]["level"] == "ok"           # a temporary bypass, removed and recorded
    assert _scenario(u200, "closeout:MOC-2026-037")["verdict"]["level"] == "stop"         # a temporary change closed with the alarm still disabled


# ---------------------------------------------------------------- nothing lost on U-100
def test_u100_keeps_every_planted_item_and_gains_only_true_findings(u100):
    assert u100["scorecard"]["found"] == u100["scorecard"]["planted"]
    assert _has(u100, "C17", "SIF-100-01")                 # configured 68 barg, SRS 65 barg
    assert _has(u100, "C19", "PAH-1001")                   # 10 min to respond, 120 s process safety time
    assert _has(u100, "C11", "SIF-100-01")                 # 24 months against a single 12 months: still a disagreement
    assert [f["level"] for f in _has(u100, "C3", "PAHH-1001")] == ["info"]


def test_every_check_fires_on_one_of_the_two_units(u100, u200):
    fired = {f["code"] for d in (u100, u200) for f in d["findings"] if f["code"].startswith("C")}
    assert fired == set(OC.TITLES) - {"C1"}
    assert all(f["title"] == OC.TITLES[f["code"]] and f["detail"] and f["sources"]
               for d in (u100, u200) for f in d["findings"] if f["code"].startswith("C") and f["code"] != "C1")
