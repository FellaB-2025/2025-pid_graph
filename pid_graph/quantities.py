"""Values with units, so that two documents writing the same value differently are not reported as disagreeing.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

`same("350 mbarg", "0.35 barg")` is True; `same("12 months", "1 year")` is True; `same("6 bar", "6 barg")` is
False (gauge and absolute-or-unstated pressure are different things and are never converted into each other).
Where the units are not in the table, or are of different kinds, nothing is converted: the caller chooses
between comparing the text (strict, the default) and comparing the numbers only (`numbers_only=True`).

Added after the blind test on U-200 (docs/BLIND_TEST.md): 12 of its 15 false alarms were values compared as text.
"""
from __future__ import annotations

import re

QTY_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(\S*)")
# kind -> unit (lower case) -> factor to the kind's base unit
UNITS = {
    "pressure_gauge": {"barg": 1.0, "mbarg": 1e-3, "kpag": 0.01, "psig": 0.0689476},
    "pressure": {"bar": 1.0, "mbar": 1e-3, "kpa": 0.01, "pa": 1e-5, "psi": 0.0689476},
    "pressure_absolute": {"bara": 1.0, "mbara": 1e-3, "kpaa": 0.01, "psia": 0.0689476},
    "length": {"mm": 1.0, "cm": 10.0, "m": 1000.0},
    "time": {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0, "hr": 3600.0, "hrs": 3600.0, "hour": 3600.0, "hours": 3600.0},
    "calendar": {"month": 1.0, "months": 1.0, "year": 12.0, "years": 12.0, "yr": 12.0},
    "temperature": {"degc": 1.0, "°c": 1.0},
}
KIND = {u: (k, f) for k, units in UNITS.items() for u, f in units.items()}


def parse(text) -> tuple[float, str] | None:
    """('350 mbarg') -> (350.0, 'mbarg'); None if the text does not start with a number."""
    m = QTY_RE.match(str(text if text is not None else ""))
    return (float(m.group(1)), m.group(2).strip(".,;")) if m else None


def canon(text) -> tuple[str, float] | None:
    """(kind, value in the kind's base unit), or None if the unit is not in the table."""
    q = parse(text)
    if not q or q[1].lower() not in KIND:
        return None
    kind, factor = KIND[q[1].lower()]
    return kind, q[0] * factor


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def same(a, b, numbers_only: bool = False) -> bool:
    ca, cb = canon(a), canon(b)
    if ca and cb and ca[0] == cb[0]:
        return _close(ca[1], cb[1])
    qa, qb = parse(a), parse(b)
    if qa and qb and (numbers_only or qa[1].lower() == qb[1].lower()):
        return _close(qa[0], qb[0])
    return re.sub(r"\s+", "", str(a or "")).lower() == re.sub(r"\s+", "", str(b or "")).lower()


def compare(a, b) -> int | None:
    """-1, 0 or 1 for a below, equal to or above b; None if they cannot be put on one scale."""
    ca, cb = canon(a), canon(b)
    if ca and cb and ca[0] == cb[0]:
        x, y = ca[1], cb[1]
    else:
        qa, qb = parse(a), parse(b)
        if not (qa and qb and qa[1].lower() == qb[1].lower()):
            return None
        x, y = qa[0], qb[0]
    return 0 if _close(x, y) else (-1 if x < y else 1)


def all_same(values) -> bool:
    values = list(values)
    return all(same(values[0], v) for v in values[1:])
