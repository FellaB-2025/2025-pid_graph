"""Build-your-own situation: the rules, and the page's JavaScript against the Python reference.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

The rules are tested on small made-up models, so each test shows one rule (S1-S8 in pid_graph/situation.py)
and none depends on U-100. The equivalence test runs the page's function in node on every single element,
every pair and a spread of larger combinations of the real U-100 model, and requires the same answer as Python.
"""
from __future__ import annotations

import itertools
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import demo  # noqa: E402
from pid_graph.situation import SITUATION_JS, describe, evaluate  # noqa: E402


def _alarm(source, unavailable=(), impaired=()):
    return {"caption": "A", "source": source, "unavailable": list(unavailable), "impaired": [{"code": c, "detail": ""} for c in impaired]}


def _sif(sid="S1", n=2, tags=("T1", "T2", "T3"), overrides=("T1", "T2", "T3"), degraded="2oo2", silv="2oo2", fe=(1, 2),
         fes=("V1", "V2"), cms=("AL1",), named=()):
    return {"id": sid, "description": "", "voting": {"n": n, "m": len(tags), "text": f"{n}oo{len(tags)}", "source": "configuration"},
            "initiators": [{"tag": t, "override": {"switch": f"MOS-{t}", "degraded": degraded, "max_h": 8.0} if t in overrides else None} for t in tags],
            "silv_degraded": silv, "fe": {"n": fe[0], "m": fe[1], "text": f"{fe[0]}oo{fe[1]}"} if fe else None,
            "final_elements": [{"tag": t, "action": "Close"} for t in fes],
            "cms": [{"alarm": a, "rank": str(i + 1), "basis": "independent_bpcs"} for i, a in enumerate(cms)],
            "srs_named": list(named), "bypass_conditions": "", "max_h": 8.0, "protects": ["EQ1"]}


def _model(sifs=None, alarms=None, scenarios=None):
    return {"sifs": sifs or [_sif()], "alarms": alarms or {"AL1": _alarm("X1")},
            "scenarios": scenarios or [{"id": "SC1", "consequence": "", "threatens": ["EQ1"], "layers": [
                {"label": "SIF", "id": "S1", "caption": "S1", "pfd": 0.01, "ipl_type": "SIF"},
                {"label": "Alarm", "id": "AL1", "caption": "A", "pfd": 0.1, "ipl_type": "Alarm"},
                {"label": "Instrument", "id": "PSV1", "caption": "PSV1", "pfd": 0.01, "ipl_type": "Relief"}]}],
            "elements": [], "presets": {"as_found": [], "recorded": []}, "export_time": ""}


def _one(res, sid="S1"):
    return next(s for s in res["sifs"] if s["id"] == sid)


def _codes(res, sid="S1"):
    return [v["code"] for v in _one(res, sid)["violations"]]


def test_nothing_out_is_as_designed():
    res = evaluate(_model(), [])
    assert res["level"] == "ok" and _one(res)["status"] == "normal" and _one(res)["sensor"]["effective"] == "2oo3"
    assert res["scenarios"][0]["ok"] == res["scenarios"][0]["total"] == 3


def test_s1_one_initiator_out_runs_the_configured_degraded_vote():
    s = _one(evaluate(_model(), ["T2"]))
    assert s["status"] == "degraded" and s["sensor"] == {"state": "degraded", "effective": "2oo2", "out": ["T2"], "remaining": ["T1", "T3"]}
    assert s["violations"] == [] and s["level"] == "warn"                 # degraded, compensated, within what is defined


def test_s1_the_sil_verification_assuming_another_vote_is_a_violation():
    assert _codes(evaluate(_model([_sif(silv="1oo2")]), ["T2"])) == ["silv_mismatch"]


def test_s2_no_override_means_the_vote_is_not_defined():
    res = evaluate(_model([_sif(overrides=("T1",))]), ["T3"])
    assert _one(res)["status"] == "undefined" and _codes(res) == ["no_override"] and res["level"] == "stop"


def test_s3_two_initiators_out_is_not_defined():
    res = evaluate(_model(), ["T1", "T2"])
    assert _one(res)["status"] == "undefined" and _codes(res) == ["multiple_channels"]


def test_s4_every_initiator_out_or_the_sif_itself_out_cannot_trip():
    assert _one(evaluate(_model(), ["T1", "T2", "T3"]))["status"] == "lost"
    assert _one(evaluate(_model(), ["S1"]))["status"] == "out"
    assert evaluate(_model(), ["S1"])["scenarios"][0]["layers"][0]["state"] == "lost"


def test_s5_final_elements_follow_the_srs_architecture():
    one = _one(evaluate(_model(), ["V1"]))
    assert one["status"] == "degraded" and one["fe"]["effective"] == "1oo1"
    assert _one(evaluate(_model(), ["V1", "V2"]))["status"] == "lost"
    assert _one(evaluate(_model([_sif(fe=(2, 2))]), ["V1"]))["status"] == "lost"       # both needed
    assert _one(evaluate(_model([_sif(fe=None)]), ["V2"]))["status"] == "lost"         # no architecture: all needed


@pytest.mark.parametrize("alarm,out,state", [
    (_alarm("X1"), ["AL1"], "shelved"), (_alarm("X1"), ["X1"], "source_out"), (_alarm("X1", unavailable=["disabled"]), [], "unavailable"),
    (_alarm("X1", impaired=["C8"]), [], "impaired"), (_alarm("X1"), [], "ok")])
def test_s6_when_a_compensating_alarm_counts(alarm, out, state):
    res = evaluate(_model(alarms={"AL1": alarm}), ["T1"] + out)
    assert _one(res)["cms"][0]["state"] == state
    assert ("no_valid_cm" in _codes(res)) == (state != "ok")


def test_s7_a_degraded_sif_needs_a_counting_alarm_and_its_srs_named_alarms():
    m = _model([_sif(cms=("AL1", "AL2"), named=("AL2",))], {"AL1": _alarm("X1"), "AL2": _alarm("X2")})
    assert _codes(evaluate(m, ["T1"])) == []
    assert _codes(evaluate(m, ["T1", "AL2"])) == ["srs_alarm_unavailable"]             # AL1 still counts
    assert _codes(evaluate(m, ["T1", "AL1", "AL2"])) == ["srs_alarm_unavailable", "no_valid_cm"]
    assert _codes(evaluate(m, ["AL1", "AL2"])) == []                                   # the SIF is normal: nothing is asked of them
    assert _codes(evaluate(_model([_sif(cms=())]), ["T1"])) == ["no_valid_cm"]


def test_s8_lopa_layers():
    layers = lambda out, **kw: [x["state"] for x in evaluate(_model(**kw), out)["scenarios"][0]["layers"]]     # noqa: E731
    assert layers(["T1"]) == ["degraded", "ok", "ok"]
    assert layers(["AL1", "PSV1"]) == ["ok", "lost", "lost"]
    assert layers([], alarms={"AL1": _alarm("X1", impaired=["C5"])}) == ["ok", "degraded", "ok"]
    assert evaluate(_model(), ["PSV1"])["level"] == "stop" and evaluate(_model(), ["T1"])["level"] == "warn"


def test_a_shared_element_reaches_every_sif_that_uses_it():
    m = _model([_sif("S1"), _sif("S2", tags=("T4",), overrides=(), fe=(1, 1), fes=("V1",), cms=())])
    res = evaluate(m, ["V1"])
    assert _one(res, "S1")["status"] == "degraded" and _one(res, "S2")["status"] == "lost"
    assert [(e["tag"], e["level"]) for e in res["equipment"]] == [("EQ1", "stop")]


def test_the_result_does_not_depend_on_the_order_things_were_ticked():
    m = demo.build()["situation"]
    ids = [e["id"] for e in m["elements"]][:6]
    assert evaluate(m, ids) == evaluate(m, list(reversed(ids))) == evaluate(m, ids + ids)


# ---------------------------------------------------------------- U-100
@pytest.fixture(scope="module")
def model():
    return demo.build()["situation"]


def test_the_model_offers_every_initiator_final_element_alarm_and_sif(model):
    ids = {e["id"] for e in model["elements"]}
    for s in model["sifs"]:
        assert s["id"] in ids and {i["tag"] for i in s["initiators"]} <= ids and {f["tag"] for f in s["final_elements"]} <= ids
    assert set(model["alarms"]) <= ids and len(ids) == len(model["elements"])
    assert set(model["presets"]["as_found"]) <= ids


def test_the_as_found_preset_is_what_the_configuration_shows_overridden(model):
    store, _ = demo.build_demo_store()
    active = {n["key"]["tag"] for n in store.nodes("Instrument")
              if str(n["props"].get("override_active", "")).lower() == "yes" and n["props"].get("block_type_cfg") != "MOS"}
    assert active and set(model["presets"]["as_found"]) == active          # the out-of-service register is empty on U-100
    res = evaluate(model, model["presets"]["as_found"])
    assert res["level"] == "stop" and "DEGRADED" in describe(model, res)


def test_taking_out_a_shared_final_element_reaches_every_sif_it_serves(model):
    shared = [e["id"] for e in model["elements"] if e["group"] == "Final elements" and "," in e["note"]]
    assert shared
    for tag in shared:
        res = evaluate(model, [tag])
        hit = {s["id"] for s in res["sifs"] if s["status"] != "normal"}
        assert hit == {s["id"] for s in model["sifs"] if any(f["tag"] == tag for f in s["final_elements"])}


# ---------------------------------------------------------------- the page's JavaScript is the same function
RUNNER = """
const fs = require('fs');
%s
const M = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const combos = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
process.stdout.write(JSON.stringify(combos.map(c => evaluateSituation(M, c))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed: the page's JavaScript cannot be run here")
def test_the_page_gives_the_same_answer_as_python_for_every_combination_tried(model, tmp_path):
    ids = [e["id"] for e in model["elements"]]
    rng = random.Random(62682)
    combos = [[]] + [[i] for i in ids] + [list(c) for c in itertools.combinations(ids, 2)]
    combos += [rng.sample(ids, k) for k in (3, 4, 5, 8) for _ in range(150)] + [ids]
    (tmp_path / "run.js").write_text(RUNNER % SITUATION_JS, encoding="utf-8")
    (tmp_path / "model.json").write_text(json.dumps(model), encoding="utf-8")
    (tmp_path / "combos.json").write_text(json.dumps(combos), encoding="utf-8")
    out = subprocess.run(["node", str(tmp_path / "run.js"), str(tmp_path / "model.json"), str(tmp_path / "combos.json")],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    js = json.loads(out)
    assert len(js) == len(combos) > 500
    for combo, got in zip(combos, js):
        assert got == json.loads(json.dumps(evaluate(model, combo))), combo


def test_the_page_carries_the_function_and_the_tab(model):
    from pid_graph.demo_page import render
    page = render(demo.build(), standalone=False)
    assert "function evaluateSituation(M, outList)" in page and 'data-tab="sit"' in page and 'id="sit-res"' in page
