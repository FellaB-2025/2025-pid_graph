"""Closed v1.3 schema, transcribed from PID_GRAPH_ONTOLOGY_V1_3.md.

v1.3 is v1.2 plus segment topology (PIDKG_UPGRADE.md section 2): additive only, nothing in
v1.2 is removed, renamed or changes meaning.

Anything not in these tables is rejected by the stores at write time. To change
the schema, change the ontology document first, then this file.
"""
from __future__ import annotations

LABELS = ("Instrument", "Equipment", "Line", "SIF", "Alarm", "State", "Document", "Scenario",
          "Segment", "InlineItem", "ControlLoop")                        # v1.3

# Canonical key properties. Neo4j uniqueness constraints are created on these.
KEYS: dict[str, tuple[str, ...]] = {
    "Instrument": ("tag",),
    "Equipment": ("tag",),
    "Line": ("line_no",),
    "SIF": ("sif_id",),
    "Alarm": ("alarm_id",),
    "State": ("state_id",),
    "Document": ("doc_no", "rev"),
    "Scenario": ("scenario_id",),                                        # v1.2: LOPA hazard scenario
    "Segment": ("segment_id",),                                          # v1.3: stretch of one Line between two in-line items
    "InlineItem": ("item_id",),                                          # v1.3: untagged in-line valve or fitting
    "ControlLoop": ("loop_key",),                                        # v1.3: loop grouped from ISA tags and drawn signals
}

_LE = frozenset({"Line", "Equipment"})
_LES = _LE | {"Segment"}                                                 # v1.3: MEASURES / INSTALLED_ON may end on a Segment
_FLOW = frozenset({"Segment", "Equipment", "Instrument", "InlineItem"})  # v1.3: what process flow passes through
_ANY = frozenset(LABELS)

# Relationship -> (allowed start labels, allowed end labels). Direction is part of the definition.
RELS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "MEASURES":        (frozenset({"Instrument"}), _LES),                 # v1.3: range widened by Segment
    "INSTALLED_ON":    (frozenset({"Instrument"}), _LES),                 # v1.3: range widened by Segment
    "FEEDS":           (_LE, _LE),
    "INITIATES":       (frozenset({"Instrument"}), frozenset({"SIF"})),
    "ACTUATES":        (frozenset({"SIF"}), frozenset({"Instrument"})),
    "PROTECTS":        (frozenset({"SIF"}), _LE),
    "RAISES":          (frozenset({"SIF"}), frozenset({"Alarm"})),        # v1.1: trip announces itself
    "CASCADES_TO":     (frozenset({"SIF"}), frozenset({"SIF"})),          # v1.1: ESD hierarchy
    "GENERATES":       (frozenset({"Instrument"}), frozenset({"Alarm"})),
    "VALID_IN":        (frozenset({"Alarm"}), frozenset({"State"})),
    "HAS_STATE":       (frozenset({"Equipment"}), frozenset({"State"})),
    "COMPENSATES_FOR": (frozenset({"Alarm"}), frozenset({"SIF"})),
    "CREDITS":         (frozenset({"Scenario"}), frozenset({"SIF", "Alarm", "Instrument"})),   # v1.2: LOPA IPL credit
    "THREATENS":       (frozenset({"Scenario"}), _LE),                                       # v1.2
    "SHOWN_ON":        (_ANY, frozenset({"Document"})),
    "SEGMENT_OF":      (frozenset({"Segment"}), frozenset({"Line"})),                         # v1.3
    "FLOWS_TO":        (_FLOW, _FLOW),                                                        # v1.3
    "SIGNAL_TO":       (frozenset({"Instrument"}), frozenset({"Instrument", "Equipment"})),   # v1.3
    "MEMBER_OF":       (frozenset({"Instrument"}), frozenset({"ControlLoop"})),               # v1.3
}

# v1.3: an InlineItem has no tag and no index row, so it can never start or end a safety relationship.
INLINE_ITEM_BANNED_RELS = ("INITIATES", "ACTUATES", "PROTECTS", "CREDITS", "COMPENSATES_FOR", "GENERATES")

# v1.3: properties a new label must carry (ontology v1.3 section 2). `review` is checked by check_review.
REQUIRED_PROPS: dict[str, tuple[str, ...]] = {
    "Segment": ("line_no", "size", "service"),
    "InlineItem": ("kind", "normal_position", "indexed"),
    "ControlLoop": ("loop_type", "variable"),
}

# v1.3: closed values on the new relationships (checked when the property is stated).
FLOW_DIRECTIONS = ("shown", "inferred")
SIGNAL_PURPOSES = ("control", "measurement", "trip", "alarm", "status", "unknown")
LOOP_ROLES = ("sensor", "controller", "relay", "final_element")
REL_VALUES: dict[str, dict[str, tuple[str, ...]]] = {
    "FLOWS_TO": {"flow_direction": FLOW_DIRECTIONS},
    "SIGNAL_TO": {"purpose": SIGNAL_PURPOSES},
    "MEMBER_OF": {"role": LOOP_ROLES},
}

# Provenance on every node and relationship (ontology section 4).
PROVENANCE = ("source_doc", "source_rev", "source_sheet", "extracted_by", "load_run")
PROVENANCE_REQUIRED = ("source_doc", "source_rev", "extracted_by", "load_run")
# Ontology lists pid_audit / llm / manual. "table" is added for deterministic loads of
# tabular registers (instrument index, alarm register) - decision D-P1-01.
EXTRACTED_BY = ("pid_audit", "llm", "manual", "table", "pidkg_vision")   # v1.3: pidkg_vision
VISION = "pidkg_vision"
# v1.3: every pidkg_vision fact carries a review state; default pending (trust rule T4).
REVIEW = ("pending", "accepted", "rejected")
# v1.3 trust rule T7: what a safety-relevant template may traverse. A fact from one of these
# sources, or any fact an engineer has accepted. The Cypher form is queries.trusted_rel().
TRUSTED_EXTRACTED_BY = ("table", "manual", "pid_audit")


def trusted(props: dict) -> bool:
    """T7: extracted_by IN ['table', 'manual', 'pid_audit'] OR review = 'accepted'."""
    return props.get("extracted_by") in TRUSTED_EXTRACTED_BY or props.get("review") == "accepted"
DOC_TYPES = ("PID", "CE", "IDX", "CUR", "SRS", "LOPA")   # CUR: curated register (D-P2-10); SRS/LOPA: v1.2
UNKNOWN_REV = "UNKNOWN"   # decision D-P1-03: revision not stated by the referencing document


class SchemaViolation(ValueError):
    """Raised when something outside the closed schema tries to enter the graph."""


def check_label(label: str) -> None:
    if label not in KEYS:
        raise SchemaViolation(f"label {label!r} is not in the v1 ontology {LABELS}")


def check_key(label: str, key: dict) -> None:
    check_label(label)
    missing = [k for k in KEYS[label] if not key.get(k)]
    extra = [k for k in key if k not in KEYS[label]]
    if missing or extra:
        raise SchemaViolation(f"{label} key must be exactly {KEYS[label]}; missing={missing} extra={extra}")


def check_rel(rel: str, start_label: str, end_label: str) -> None:
    if rel not in RELS:
        raise SchemaViolation(f"relationship {rel!r} is not in the v1 ontology {tuple(RELS)}")
    if rel in INLINE_ITEM_BANNED_RELS and "InlineItem" in (start_label, end_label):
        raise SchemaViolation(f"{rel}: an InlineItem can never start or end a safety relationship "
                              f"{INLINE_ITEM_BANNED_RELS}, got {start_label} -> {end_label}")
    starts, ends = RELS[rel]
    if start_label not in starts or end_label not in ends:
        raise SchemaViolation(f"{rel} must be {sorted(starts)} -> {sorted(ends)}, got {start_label} -> {end_label}")


def check_provenance(props: dict, what: str) -> None:
    missing = [p for p in PROVENANCE_REQUIRED if not props.get(p)]
    if missing:
        raise SchemaViolation(f"{what}: provenance incomplete, missing {missing}")
    if props["extracted_by"] not in EXTRACTED_BY:
        raise SchemaViolation(f"{what}: extracted_by={props['extracted_by']!r} not in {EXTRACTED_BY}")


def check_review(props: dict, what: str) -> None:
    """v1.3: a pidkg_vision fact must state its review; any stated review must be a closed value."""
    review = props.get("review")
    if review in (None, ""):
        if props.get("extracted_by") == VISION:
            raise SchemaViolation(f"{what}: a {VISION} fact must carry review, one of {REVIEW}")
        return
    if review not in REVIEW:
        raise SchemaViolation(f"{what}: review={review!r} not in {REVIEW}")


def check_node_props(label: str, props: dict) -> None:
    """v1.3: required properties of the new labels. v1.2 labels have none and are not touched."""
    required = REQUIRED_PROPS.get(label, ())
    missing = [p for p in required if props.get(p) in (None, "")]
    if missing:
        raise SchemaViolation(f"{label}: required properties missing {missing}; required are {required + ('review',)}")
    if label == "InlineItem" and props["indexed"] is not False:
        raise SchemaViolation(f"InlineItem: indexed must be false (an item with an index row is an Instrument), got {props['indexed']!r}")


def check_rel_props(rel: str, props: dict) -> None:
    """v1.3: closed values on the new relationships, checked when stated."""
    for prop, allowed in REL_VALUES.get(rel, {}).items():
        value = props.get(prop)
        if value not in (None, "") and value not in allowed:
            raise SchemaViolation(f"{rel}: {prop}={value!r} not in {allowed}")
