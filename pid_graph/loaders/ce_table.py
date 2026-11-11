"""Read a Cause & Effect chart into one row per (SIF, cause, effect).

Handles the row-per-triple form and the common EPC matrix form (causes down,
effects across, marks in the cells, an optional action row under the effect tags).
SIF-level cells (SIF No., SIL, Logic Solver, Protected Equipment) are carried down
the block, as merged cells print. A cause with no marked effect still yields one
row with an empty effect so its INITIATES edge is not lost.
Ported from the prototype's ce_matrix.py.
"""
from __future__ import annotations

from pathlib import Path

from .tables import CE_ALIASES, clean, norm, raw_rows, read_table

ACTION_WORDS = {"close", "open", "stop", "start", "trip", "de-energise", "de-energize", "energise", "energize",
                "isolate", "vent", "blowdown", "alarm", "inhibit", "run", "shutdown"}
MARKS = {"x", "1", "y", "yes", "c", "o", "t", "s"}
MARK_ACTION = {"c": "Close", "o": "Open", "t": "Trip", "s": "Stop"}
CARRY = ("sif_id", "sif_description", "sil", "logic_solver", "protects")
FIELDS = ("sif_id", "sif_description", "sil", "logic_solver", "cause_tag", "cause_description", "voting",
          "setpoint", "protects", "effect_tag", "effect_action", "ref")


def ce_rows(path: str | Path, sheet: str | None = None) -> list[dict]:
    path = Path(path)
    rows = read_table(path, sheet, CE_ALIASES)
    if any(r.get("effect_tag") for r in rows):
        out = []
        carry: dict[str, str] = {}
        for r in rows:
            for k in CARRY:
                if r.get(k):
                    carry[k] = r[k]
                else:
                    r[k] = carry.get(k, "")
            out.append({**{f: r.get(f, "") for f in FIELDS}, "ref": f"{path.name}:{r['_row']}"})
        return out
    return _matrix_rows(path, sheet)


def _matrix_rows(path: Path, sheet: str | None) -> list[dict]:
    rows, title = raw_rows(path, sheet)
    accepted = {a: canon for canon, names in CE_ALIASES.items() for a in names}
    h = next((i for i, r in enumerate(rows[:30])
              if any(accepted.get(norm(c)) == "cause_tag" for c in r if c)), None)
    if h is None:
        raise ValueError(f"{path.name}: no 'Cause Tag' header in the first 30 rows")
    header = rows[h]
    cause_cols: dict[str, int] = {}
    for j, c in enumerate(header):
        canon = accepted.get(norm(c)) if c else None
        if canon and canon not in cause_cols:
            cause_cols[canon] = j
    last_cause_col = max(cause_cols.values())
    effect_cols = [(j, clean(c).upper()) for j, c in enumerate(header) if j > last_cause_col and c not in (None, "")]
    action_row = rows[h + 1] if h + 1 < len(rows) else []
    has_action_row = any(clean(action_row[j]).lower() in ACTION_WORDS for j, _ in effect_cols if j < len(action_row))
    actions = {j: clean(action_row[j]) for j, _ in effect_cols if j < len(action_row)} if has_action_row else {}
    data_start = h + 2 if has_action_row else h + 1

    out: list[dict] = []
    carry: dict[str, str] = {}
    for i, r in enumerate(rows[data_start:], start=data_start + 1):
        if not r or all(v in (None, "") for v in r):
            continue
        cause = {canon: clean(r[j]) if j < len(r) else "" for canon, j in cause_cols.items()}
        for k in CARRY:
            if cause.get(k):
                carry[k] = cause[k]
            else:
                cause[k] = carry.get(k, "")
        if not cause.get("cause_tag"):
            continue
        base = {f: cause.get(f, "") for f in FIELDS}
        effects = []
        for j, effect_tag in effect_cols:
            mark = clean(r[j]).lower() if j < len(r) else ""
            if not mark or (mark not in MARKS and len(mark) > 2):
                continue
            effects.append((effect_tag, actions.get(j, "") or MARK_ACTION.get(mark, ""), j))
        if not effects:
            out.append({**base, "effect_tag": "", "effect_action": "", "ref": f"{path.name}:{title}:R{i}"})
        for effect_tag, action, j in effects:
            out.append({**base, "effect_tag": effect_tag, "effect_action": action,
                        "ref": f"{path.name}:{title}:R{i}C{j + 1}"})
    return out
