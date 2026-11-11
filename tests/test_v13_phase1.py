"""v1.3 Phase 1 (PIDKG_UPGRADE.md): ontology v1.3 in the validators.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Additive only: 3 labels, 4 relationships, two widened ranges, the review property, and the
InlineItem safety-relationship ban. The v1.2 U-100 dump must stay byte-for-byte the same.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import ontology as O  # noqa: E402
from pid_graph.pipeline import build_store  # noqa: E402
from pid_graph.records import MemoryStore  # noqa: E402

DATA = ROOT / "data"
FIXTURE = ROOT / "tests" / "fixtures" / "graph_U-100_v1_2.json"

# A v1.2 fact (index row) and a v1.3 vision fact.
TABLE = {"source_doc": "IDX-1", "source_rev": "A", "source_sheet": "", "extracted_by": "table", "load_run": "t"}
VISION = {"source_doc": "PID-9", "source_rev": "A", "source_sheet": "1", "extracted_by": "pidkg_vision", "load_run": "t",
          "source_ref": "x.pdf:p2:bbox=10,10,50,50", "confidence": 0.95, "review": "pending"}

V12_LABELS = ("Instrument", "Equipment", "Line", "SIF", "Alarm", "State", "Document", "Scenario")
V12_RELS = ("MEASURES", "INSTALLED_ON", "FEEDS", "INITIATES", "ACTUATES", "PROTECTS", "RAISES", "CASCADES_TO", "GENERATES",
            "VALID_IN", "HAS_STATE", "COMPENSATES_FOR", "CREDITS", "THREATENS", "SHOWN_ON")
SAFETY_RELS = ("INITIATES", "ACTUATES", "PROTECTS", "CREDITS", "COMPENSATES_FOR", "GENERATES")

SEG = {"line_no": "L-1", "size": '6"', "service": "feed gas"}
ITEM = {"kind": "check_valve", "normal_position": "n/a", "indexed": False}
LOOP = {"loop_type": "feedback", "variable": "pressure"}


# ---- closed lists -------------------------------------------------------------
def test_closed_lists_are_v12_plus_the_planned_additions():
    assert O.LABELS == V12_LABELS + ("Segment", "InlineItem", "ControlLoop")
    assert tuple(O.RELS) == V12_RELS + ("SEGMENT_OF", "FLOWS_TO", "SIGNAL_TO", "MEMBER_OF")
    assert O.KEYS["Segment"] == ("segment_id",) and O.KEYS["InlineItem"] == ("item_id",) and O.KEYS["ControlLoop"] == ("loop_key",)
    assert O.EXTRACTED_BY == ("pid_audit", "llm", "manual", "table", "pidkg_vision")
    assert O.REVIEW == ("pending", "accepted", "rejected")


def test_v12_ranges_keep_their_meaning():
    le = {"Line", "Equipment"}
    assert O.RELS["FEEDS"] == (le, le)                                           # unchanged: no Segment in FEEDS
    assert O.RELS["MEASURES"] == ({"Instrument"}, le | {"Segment"})              # widened by Segment only
    assert O.RELS["INSTALLED_ON"] == ({"Instrument"}, le | {"Segment"})
    assert O.RELS["INITIATES"] == ({"Instrument"}, {"SIF"})
    assert O.RELS["ACTUATES"] == ({"SIF"}, {"Instrument"})
    assert O.RELS["PROTECTS"] == ({"SIF"}, le)
    assert O.RELS["CASCADES_TO"] == ({"SIF"}, {"SIF"})
    assert O.RELS["HAS_STATE"] == ({"Equipment"}, {"State"})
    assert O.RELS["COMPENSATES_FOR"] == ({"Alarm"}, {"SIF"})
    for k in V12_LABELS:
        assert k in O.RELS["SHOWN_ON"][0]


# ---- a made-up five-node graph per new label ----------------------------------
def test_segment_graph():
    """V-1 -> L-1.1 -> L-1.2 -> V-2, both segments SEGMENT_OF L-1."""
    s = MemoryStore()
    s.merge_node("Line", {"line_no": "L-1"}, TABLE)
    s.merge_node("Equipment", {"tag": "V-1"}, TABLE)
    s.merge_node("Equipment", {"tag": "V-2"}, TABLE)
    s.merge_node("Segment", {"segment_id": "L-1.1"}, {**VISION, **SEG})
    s.merge_node("Segment", {"segment_id": "L-1.2"}, {**VISION, **SEG})
    for k in ("L-1.1", "L-1.2"):
        s.merge_rel("SEGMENT_OF", "Segment", {"segment_id": k}, "Line", {"line_no": "L-1"}, VISION)
    flow = {**VISION, "flow_direction": "shown", "off_page": False}
    s.merge_rel("FLOWS_TO", "Equipment", {"tag": "V-1"}, "Segment", {"segment_id": "L-1.1"}, flow)
    s.merge_rel("FLOWS_TO", "Segment", {"segment_id": "L-1.1"}, "Segment", {"segment_id": "L-1.2"}, flow)
    s.merge_rel("FLOWS_TO", "Segment", {"segment_id": "L-1.2"}, "Equipment", {"tag": "V-2"}, {**flow, "flow_direction": "inferred"})
    c = s.counts()
    assert c["nodes"] == 5 and c["by_label"]["Segment"] == 2
    assert c["by_rel"] == {"FLOWS_TO": 3, "SEGMENT_OF": 2}
    assert all(n["props"]["review"] == "pending" for n in s.nodes("Segment"))


def test_inline_item_graph():
    """L-1.1 -> untagged check valve -> L-1.2, with a tagged valve and a sensor placed on segments."""
    s = MemoryStore()
    s.merge_node("Segment", {"segment_id": "L-1.1"}, {**VISION, **SEG})
    s.merge_node("Segment", {"segment_id": "L-1.2"}, {**VISION, **SEG})
    s.merge_node("InlineItem", {"item_id": "PID-9.c7"}, {**VISION, **ITEM})
    s.merge_node("Instrument", {"tag": "XV-1"}, TABLE)
    s.merge_node("Instrument", {"tag": "PT-1"}, TABLE)
    flow = {**VISION, "flow_direction": "shown"}
    s.merge_rel("FLOWS_TO", "Segment", {"segment_id": "L-1.1"}, "InlineItem", {"item_id": "PID-9.c7"}, flow)
    s.merge_rel("FLOWS_TO", "InlineItem", {"item_id": "PID-9.c7"}, "Instrument", {"tag": "XV-1"}, flow)
    s.merge_rel("FLOWS_TO", "Instrument", {"tag": "XV-1"}, "Segment", {"segment_id": "L-1.2"}, flow)
    s.merge_rel("INSTALLED_ON", "Instrument", {"tag": "XV-1"}, "Segment", {"segment_id": "L-1.2"}, VISION)   # widened range
    s.merge_rel("MEASURES", "Instrument", {"tag": "PT-1"}, "Segment", {"segment_id": "L-1.1"}, VISION)       # widened range
    c = s.counts()
    assert c["nodes"] == 5 and c["by_label"]["InlineItem"] == 1
    assert c["by_rel"] == {"FLOWS_TO": 3, "INSTALLED_ON": 1, "MEASURES": 1}
    assert s.get_node("InlineItem", {"item_id": "PID-9.c7"})["props"]["indexed"] is False


def test_control_loop_graph():
    """PT-5 -> PIC-5 -> PV-5 grouped as loop P-5; PT-5 also signals a trip to V-1."""
    s = MemoryStore()
    for tag in ("PT-5", "PIC-5", "PV-5"):
        s.merge_node("Instrument", {"tag": tag}, TABLE)
    s.merge_node("Equipment", {"tag": "V-1"}, TABLE)
    s.merge_node("ControlLoop", {"loop_key": "P-5"}, {**VISION, **LOOP})
    for tag, role in (("PT-5", "sensor"), ("PIC-5", "controller"), ("PV-5", "final_element")):
        s.merge_rel("MEMBER_OF", "Instrument", {"tag": tag}, "ControlLoop", {"loop_key": "P-5"}, {**VISION, "role": role})
    sig = {**VISION, "signal_type": "electrical"}
    s.merge_rel("SIGNAL_TO", "Instrument", {"tag": "PT-5"}, "Instrument", {"tag": "PIC-5"}, {**sig, "purpose": "measurement"})
    s.merge_rel("SIGNAL_TO", "Instrument", {"tag": "PIC-5"}, "Instrument", {"tag": "PV-5"}, {**sig, "purpose": "control"})
    s.merge_rel("SIGNAL_TO", "Instrument", {"tag": "PT-5"}, "Equipment", {"tag": "V-1"}, {**sig, "purpose": "trip"})
    c = s.counts()
    assert c["nodes"] == 5 and c["by_label"]["ControlLoop"] == 1
    assert c["by_rel"] == {"MEMBER_OF": 3, "SIGNAL_TO": 3}


# ---- direction and range of the four new relationships ------------------------
@pytest.mark.parametrize("rel,start,end", [
    ("SEGMENT_OF", "Segment", "Line"),
    ("FLOWS_TO", "Segment", "Segment"), ("FLOWS_TO", "Equipment", "Segment"), ("FLOWS_TO", "Segment", "InlineItem"),
    ("FLOWS_TO", "InlineItem", "Instrument"), ("FLOWS_TO", "Instrument", "Equipment"),
    ("SIGNAL_TO", "Instrument", "Instrument"), ("SIGNAL_TO", "Instrument", "Equipment"),
    ("MEMBER_OF", "Instrument", "ControlLoop"),
    ("MEASURES", "Instrument", "Segment"), ("INSTALLED_ON", "Instrument", "Segment"),
    ("SHOWN_ON", "Segment", "Document"), ("SHOWN_ON", "InlineItem", "Document"), ("SHOWN_ON", "ControlLoop", "Document"),
])
def test_new_relationships_allowed(rel, start, end):
    O.check_rel(rel, start, end)


@pytest.mark.parametrize("rel,start,end", [
    ("SEGMENT_OF", "Line", "Segment"), ("SEGMENT_OF", "Segment", "Equipment"), ("SEGMENT_OF", "InlineItem", "Line"),
    ("FLOWS_TO", "Line", "Segment"), ("FLOWS_TO", "Segment", "Line"), ("FLOWS_TO", "SIF", "Segment"),
    ("FLOWS_TO", "Segment", "ControlLoop"),
    ("SIGNAL_TO", "Equipment", "Instrument"), ("SIGNAL_TO", "Instrument", "SIF"), ("SIGNAL_TO", "InlineItem", "Instrument"),
    ("MEMBER_OF", "ControlLoop", "Instrument"), ("MEMBER_OF", "Equipment", "ControlLoop"), ("MEMBER_OF", "InlineItem", "ControlLoop"),
    ("FEEDS", "Segment", "Equipment"), ("FEEDS", "Equipment", "Segment"),          # FEEDS is unchanged
    ("MEASURES", "InlineItem", "Segment"), ("INSTALLED_ON", "InlineItem", "Segment"),
])
def test_new_relationships_refused_outside_their_range(rel, start, end):
    with pytest.raises(O.SchemaViolation):
        O.check_rel(rel, start, end)


# ---- the InlineItem safety-relationship ban -----------------------------------
def test_inline_item_on_initiates_is_refused():
    s = MemoryStore()
    s.merge_node("InlineItem", {"item_id": "PID-9.c7"}, {**VISION, **ITEM})
    s.merge_node("SIF", {"sif_id": "SIF-1"}, TABLE)
    with pytest.raises(O.SchemaViolation, match="InlineItem"):
        s.merge_rel("INITIATES", "InlineItem", {"item_id": "PID-9.c7"}, "SIF", {"sif_id": "SIF-1"}, VISION)
    assert s.counts()["rels"] == 0


@pytest.mark.parametrize("rel", SAFETY_RELS)
@pytest.mark.parametrize("other", ["Instrument", "SIF", "Alarm", "Scenario", "Equipment", "Line"])
def test_inline_item_never_starts_or_ends_a_safety_relationship(rel, other):
    assert set(O.INLINE_ITEM_BANNED_RELS) == set(SAFETY_RELS)
    with pytest.raises(O.SchemaViolation, match="InlineItem"):
        O.check_rel(rel, "InlineItem", other)
    with pytest.raises(O.SchemaViolation, match="InlineItem"):
        O.check_rel(rel, other, "InlineItem")


# ---- review -------------------------------------------------------------------
def test_vision_fact_must_carry_a_review_value():
    s = MemoryStore()
    no_review = {k: v for k, v in VISION.items() if k != "review"}
    with pytest.raises(O.SchemaViolation, match="review"):
        s.merge_node("Segment", {"segment_id": "L-1.1"}, {**no_review, **SEG})
    with pytest.raises(O.SchemaViolation, match="review"):
        s.merge_node("Segment", {"segment_id": "L-1.1"}, {**VISION, **SEG, "review": "ok"})
    s.merge_node("Segment", {"segment_id": "L-1.1"}, {**VISION, **SEG})
    s.merge_node("Line", {"line_no": "L-1"}, TABLE)
    with pytest.raises(O.SchemaViolation, match="review"):
        s.merge_rel("SEGMENT_OF", "Segment", {"segment_id": "L-1.1"}, "Line", {"line_no": "L-1"}, no_review)
    for value in O.REVIEW:
        O.check_review({**VISION, "review": value}, "x")


def test_v12_facts_need_no_review_but_a_stated_one_must_be_valid():
    O.check_review(TABLE, "x")                                   # table / manual / pid_audit facts: not required
    O.check_review({**TABLE, "review": "accepted"}, "x")
    with pytest.raises(O.SchemaViolation, match="review"):
        O.check_review({**TABLE, "review": "maybe"}, "x")


# ---- required and closed-value properties -------------------------------------
@pytest.mark.parametrize("label,key,good,drop", [
    ("Segment", {"segment_id": "L-1.1"}, SEG, "line_no"), ("Segment", {"segment_id": "L-1.1"}, SEG, "size"),
    ("Segment", {"segment_id": "L-1.1"}, SEG, "service"),
    ("InlineItem", {"item_id": "PID-9.c7"}, ITEM, "kind"), ("InlineItem", {"item_id": "PID-9.c7"}, ITEM, "normal_position"),
    ("InlineItem", {"item_id": "PID-9.c7"}, ITEM, "indexed"),
    ("ControlLoop", {"loop_key": "P-5"}, LOOP, "loop_type"), ("ControlLoop", {"loop_key": "P-5"}, LOOP, "variable"),
])
def test_new_labels_require_their_properties(label, key, good, drop):
    s = MemoryStore()
    with pytest.raises(O.SchemaViolation, match=drop):
        s.merge_node(label, key, {**VISION, **{k: v for k, v in good.items() if k != drop}})
    s.merge_node(label, key, {**VISION, **good})


def test_inline_item_is_never_indexed():
    with pytest.raises(O.SchemaViolation, match="indexed"):
        MemoryStore().merge_node("InlineItem", {"item_id": "PID-9.c7"}, {**VISION, **ITEM, "indexed": True})


@pytest.mark.parametrize("rel,prop,bad", [
    ("FLOWS_TO", "flow_direction", "guessed"), ("SIGNAL_TO", "purpose", "interlock"), ("MEMBER_OF", "role", "valve"),
])
def test_closed_values_on_new_relationships(rel, prop, bad):
    with pytest.raises(O.SchemaViolation, match=prop):
        O.check_rel_props(rel, {**VISION, prop: bad})
    for good in {"flow_direction": O.FLOW_DIRECTIONS, "purpose": O.SIGNAL_PURPOSES, "role": O.LOOP_ROLES}[prop]:
        O.check_rel_props(rel, {**VISION, prop: good})
    O.check_rel_props("MEASURES", {**TABLE, "role": "anything"})    # v1.2 relationships are not touched


# ---- the v1.2 dump is unchanged, byte for byte --------------------------------
def test_v12_dump_is_byte_identical():
    store, _ = build_store(unit="U-100", index=DATA / "U100-INST-INDEX-Rev-B.xlsx", ce=DATA / "U100-CE-CHART-Rev-A.xlsx",
                           srs=DATA / "U100-SRS-001-Rev-B.xlsx", lopa=DATA / "U100-LOPA-001-Rev-A.xlsx",
                           curated=DATA / "curated" / "compensating_measures_U-100.csv",
                           topology=DATA / "pid_audit_U100_topology.csv", pdf=DATA / "U100-PIDS-TX-0057.pdf",
                           transmittal="TX-0057", load_run="TX-0057-BASELINE")
    dump = (json.dumps(store.to_dict(), indent=1, default=str) + "\n").encode("utf-8")
    frozen = FIXTURE.read_bytes().replace(b"\r\n", b"\n")          # tolerate a CRLF checkout
    assert dump == frozen
    assert {n["label"] for n in store.nodes()} <= set(V12_LABELS)
    assert {r["type"] for r in store.rels()} <= set(V12_RELS)
