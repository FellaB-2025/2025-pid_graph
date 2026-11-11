"""Closed v1.2 schema, transcribed from PID_GRAPH_ONTOLOGY_V1_2.md.

Anything not in these tables is rejected by the stores at write time. To change
the schema, change the ontology document first, then this file.
"""
from __future__ import annotations

LABELS = ("Instrument", "Equipment", "Line", "SIF", "Alarm", "State", "Document", "Scenario")

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
}

_LE = frozenset({"Line", "Equipment"})
_ANY = frozenset(LABELS)

# Relationship -> (allowed start labels, allowed end labels). Direction is part of the definition.
RELS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "MEASURES":        (frozenset({"Instrument"}), _LE),
    "INSTALLED_ON":    (frozenset({"Instrument"}), _LE),
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
}

# Provenance on every node and relationship (ontology section 4).
PROVENANCE = ("source_doc", "source_rev", "source_sheet", "extracted_by", "load_run")
PROVENANCE_REQUIRED = ("source_doc", "source_rev", "extracted_by", "load_run")
# Ontology lists pid_audit / llm / manual. "table" is added for deterministic loads of
# tabular registers (instrument index, alarm register) - decision D-P1-01.
EXTRACTED_BY = ("pid_audit", "llm", "manual", "table")
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
    starts, ends = RELS[rel]
    if start_label not in starts or end_label not in ends:
        raise SchemaViolation(f"{rel} must be {sorted(starts)} -> {sorted(ends)}, got {start_label} -> {end_label}")


def check_provenance(props: dict, what: str) -> None:
    missing = [p for p in PROVENANCE_REQUIRED if not props.get(p)]
    if missing:
        raise SchemaViolation(f"{what}: provenance incomplete, missing {missing}")
    if props["extracted_by"] not in EXTRACTED_BY:
        raise SchemaViolation(f"{what}: extracted_by={props['extracted_by']!r} not in {EXTRACTED_BY}")
