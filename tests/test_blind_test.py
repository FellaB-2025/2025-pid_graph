"""The blind test's records are complete, consistent with each other, and shown as scored.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

These tests never judge the score. They check that the sealed findings, the answer key and the adjudication
describe the same run, that the counts add up, and that the page and the write-up repeat the scorer's numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
U200 = ROOT / "data" / "u200"

from pid_graph import demo  # noqa: E402

KEY = json.loads((U200 / "U200-BATCH2-ANSWER-KEY.json").read_text(encoding="utf-8"))
SEALED = json.loads((ROOT / "eval" / "blind" / "U200-BLIND-RUN-FINDINGS.json").read_text(encoding="utf-8"))
ADJ = json.loads((U200 / "U200-BLIND-ADJUDICATION.json").read_text(encoding="utf-8"))


def test_the_adjudication_covers_every_planted_item_and_every_control():
    assert [i["id"] for i in ADJ["items"]] == [i["id"] for i in KEY["items"]]
    assert len(ADJ["clean_controls"]) == len(KEY["clean_controls"])
    assert all(i["verdict"] in ("found", "partial", "missed") and i["reason"] for i in ADJ["items"])


def test_the_counts_add_up():
    s = ADJ["summary"]
    verdicts = [i["verdict"] for i in ADJ["items"]]
    assert (s["found"], s["partial"], s["missed"]) == tuple(verdicts.count(v) for v in ("found", "partial", "missed"))
    assert s["found"] + s["partial"] + s["missed"] == s["planted"] == len(KEY["items"])
    assert s["clean_flagged"] == sum(c["flagged"] for c in ADJ["clean_controls"]) and s["clean_controls"] == len(KEY["clean_controls"])
    by_class = {}
    for o in ADJ["other_findings"]:
        by_class[o["class"]] = by_class.get(o["class"], 0) + o["count"]
    assert by_class == {"true_unplanted": s["other_true_unplanted"], "input_gap": s["other_input_gap"], "false_alarm": s["other_false_alarm"]}
    assert s["findings_total"] == len(SEALED["findings"])


def test_every_finding_the_scorer_credits_is_in_the_sealed_output():
    sealed = {f"{f['code']} {f['id']}" for f in SEALED["findings"]}
    for item in ADJ["items"]:
        for by in item.get("by", []):
            if by.split()[0][0] in "CX" and by.split()[0][1:].isdigit():      # a finding, not a scenario verdict
                assert by in sealed, (item["id"], by)


def test_the_run_was_made_at_the_freeze():
    assert SEALED["freeze"] == ADJ["freeze"] and SEALED["freeze_commit"] and SEALED["unit"] == ADJ["unit"] == KEY["unit"] == "U-200"
    assert "pid_graph/ops_checks.py" in SEALED["frozen_paths"] and "pid_graph/reconcile.py" in SEALED["frozen_paths"]


def test_the_second_unit_builds_through_the_same_code():
    cfg = demo.unit_config("U-200")
    assert cfg["answer_key"] is None                                     # the demonstrator never reads a blind unit's key
    store, reports = demo.build_demo_store(unit="U-200")
    assert reports["unit"] == "U-200" and store.counts() == SEALED["counts"]     # the documents have not changed since the run
    assert {d["doc_no"] for d in SEALED["documents"]} == {n["key"]["doc_no"] for n in store.nodes("Document")}


def test_the_page_and_the_write_up_repeat_the_scorers_numbers():
    from pid_graph.demo_page import render
    data = demo.build()
    # Changed on 12 Nov 2026 with Alan's agreement (an exception to rule 12): a second blind unit (U-300) now follows U-200.
    # U-200 must still come first and be exactly its adjudication; every later one must be its own file, unedited.
    assert [b["unit"] for b in data["blind_tests"]][0] == "U-200" and data["blind_tests"][0] == ADJ
    for b in data["blind_tests"][1:]:
        slug = b["unit"].lower().replace("-", "")
        assert b == json.loads((ROOT / "data" / slug / f"{b['unit'].replace('-', '')}-BLIND-ADJUDICATION.json").read_text(encoding="utf-8"))
    page = render(data, standalone=False)
    assert "Blind test · unit" in page and "Development test · unit" in page
    s = ADJ["summary"]
    doc = (ROOT / "docs" / "BLIND_TEST.md").read_text(encoding="utf-8")
    assert f"**{s['found']} of {s['planted']} found outright, {s['partial']} partly, {s['missed']} missed.**" in doc
    assert f"**{s['clean_flagged']} of {s['clean_controls']} deliberately consistent items were wrongly flagged**" in doc
    for item in ADJ["items"]:
        assert f"| {item['id']} |" in doc
    for name in ("CLAUDE.md", "docs/DEMO_GUIDE.md"):
        assert f"{s['found']} of {s['planted']} found outright" in (ROOT / name).read_text(encoding="utf-8"), name
