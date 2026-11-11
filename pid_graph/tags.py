"""Canonical tag normalisation and prefix-based classification.

Ontology section 2: one normalised tag format, enforced by uniqueness constraints.
The regex is provisional until pid_audit's own rule is available (decision D-P1-02).
"""
from __future__ import annotations

import re

# [unit-]FUNC-NUMBER[SUFFIX]   e.g. PT-1001A, 100-PT-1001A, L-101, V-1002, BL-100
TAG_RE = re.compile(r"^(?:(?P<unit>\d{2,4})-)?(?P<func>[A-Z]{1,5})-?(?P<num>\d{2,6})(?P<suffix>[A-Z]{0,2})$")

FINAL_ELEMENT_PREFIXES = ("XV", "BDV", "SDV", "ESDV", "XZV", "UV", "PV", "FV", "LV", "TV", "PCV", "FCV", "LCV", "TCV")
MANUAL_VALVE_PREFIXES = ("HV", "MV", "HCV")
SENSOR_PREFIXES = ("PT", "LT", "TT", "FT", "AT", "PDT", "PSH", "PSL", "LSH", "LSL", "TSH", "FSL", "ZS", "ZSC", "ZSO",
                   "PS", "LS", "TS", "FS", "GD", "UT", "VT", "ST", "PDS", "FE", "TE")
LOCAL_INDICATOR_PREFIXES = ("PI", "LI", "TI", "FI", "PG", "LG", "TG", "PDI", "FG")
LOOP_PREFIXES = ("PIC", "LIC", "TIC", "FIC", "AIC", "PC", "LC", "TC", "FC")
ALARM_PREFIXES = ("PAH", "PAL", "LAH", "LAL", "TAH", "TAL", "FAH", "FAL", "PAHH", "LAHH", "TAHH", "FAHH",
                  "PALL", "LALL", "TALL", "FALL", "AAH", "AAL")
EQUIPMENT_PREFIXES = ("V", "D", "T", "E", "C", "K", "P", "H", "R", "F", "M", "S", "X", "BL", "TK")
OFFPAGE_PREFIXES = ("BL",)          # battery-limit / off-page references -> stub nodes
LINE_PREFIXES = ("L", "LINE")


def canonical_tag(raw) -> str | None:
    """Normalised tag, or None when the value is not tag-shaped."""
    s = re.sub(r"\s+", "", str(raw or "")).upper().replace("_", "-")
    s = re.sub(r"-{2,}", "-", s)
    m = TAG_RE.match(s)
    if not m:
        return None
    unit, func, num, suf = m.group("unit", "func", "num", "suffix")
    return f"{unit + '-' if unit else ''}{func}-{num}{suf}"


def canonical_id(raw) -> str:
    """Fallback for identifiers that are not ISA-style tags (FLARE-HDR, SIS-LS-100)."""
    s = re.sub(r"\s+", "", str(raw or "")).upper().replace("_", "-")
    return re.sub(r"-{2,}", "-", s).strip("-")


def func_prefix(tag: str) -> str:
    m = TAG_RE.match(tag or "")
    return m.group("func") if m else (tag or "").split("-")[0]


def role(tag: str) -> str:
    """'final_element' | 'manual_valve' | 'sensor' | 'local_indicator' | 'loop' | 'alarm' | 'unknown'."""
    p = func_prefix(tag)
    if p in ALARM_PREFIXES:
        return "alarm"
    if p in LOOP_PREFIXES:
        return "loop"
    if p in FINAL_ELEMENT_PREFIXES:
        return "final_element"
    if p in MANUAL_VALVE_PREFIXES:
        return "manual_valve"
    if p in SENSOR_PREFIXES:
        return "sensor"
    if p in LOCAL_INDICATOR_PREFIXES:
        return "local_indicator"
    return "unknown"


def classify(raw) -> tuple[str, str]:
    """(label, canonical id) for a bare identifier seen on a P&ID or in an index column.

    Instrument / Line / Equipment only - the three labels a drawing can evidence.
    Unknown-but-tag-shaped identifiers default to Equipment, as do non-tag-shaped ones
    (FLARE-HDR); the caller decides whether that is a stub."""
    c = canonical_tag(raw)
    if c is None:
        return "Equipment", canonical_id(raw)
    p = func_prefix(c)
    if p in LINE_PREFIXES:
        return "Line", c
    if role(c) != "unknown":
        return "Instrument", c
    return "Equipment", c


def is_offpage(ident: str) -> bool:
    """Battery limits, flare headers and other things that are references, not plant items."""
    return canonical_tag(ident) is None or func_prefix(ident) in OFFPAGE_PREFIXES
