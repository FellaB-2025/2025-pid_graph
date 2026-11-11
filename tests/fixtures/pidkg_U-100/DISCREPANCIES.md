# DISCREPANCIES.md — the Phase 6 test fixture

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

`graph_discrepancies.json` is `graph.json` (the frozen pid-to-kg extraction, see `RUN.md`) with
**exactly one planted discrepancy for each reconciliation check** of `PIDKG_UPGRADE.md` Phase 6.
It is made by `scripts/make_pidkg_discrepancies.py` and is not a second extraction: no drawing
shows these things. Dummy data.

| Check | Planted edit | Expected exception |
|---|---|---|
| 1. Tag check, index vs vision | PI-1001 removed from the drawing | X22 PI-1001 |
| 2. Derived flow vs pid_audit | The blowdown flag on L-104 reads BL-200, not FLARE-HDR | X31 L-104 |
| 3. Instrument's line, index vs vision | PT-1005's tap moved from L-102 to L-105 | X32 PT-1005 |
| 4. Drawn trips vs C&E | A trip signal drawn from LT-1006 to XV-1002 | X33 LT-1006 -> XV-1002 |
| 5. Fail position, drawn vs index remark | LV-1006 drawn FO; the index says fail close | X35 LV-1006 |
| 6. Loop membership, drawn vs index | PV-1005 grouped into loop L-1006; the index says PIC-1005 | X36 PV-1005 |

The unedited `graph.json` already carries two genuine findings of the same checks, which stay
in this fixture too:

- X30 XV-1002: the index places it on PID-100-002, vision found it on PID-100-001;
- X34 SIF-100-03: the C&E has PT-1001D closing XV-1001, and no such trip is drawn.
