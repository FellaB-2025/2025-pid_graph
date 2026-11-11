# PHASE0_PROMPT.md — instructions for Claude Code
© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Go ahead. Resolve the seven points like this, then do Phase 0 of PIDKG_UPGRADE.md and stop.

1. Git: before git init, write a .gitignore covering .venv, .env, __pycache__, work/,
   third_party/, data/external/ and any credentials. Show me git status before the first
   commit so I can confirm nothing sensitive is staged. Then commit and tag v1.2-baseline.
2. CLAUDE.md: create one from README.md, PID_GRAPH_DECISIONS.md and SESSION_LOG.md
   (purpose, rules, closed label and relationship lists, files, known-good answers).
   Copyright header: © 2026 Alan Bowden — Bowden Simulators. British spelling.
3. Renumber the plan's new competency questions to CQ14–CQ18.
4. The baseline is the README's v1.2 schema (8 labels, 15 relationships), not the dump.
   Check the plan's 3 new labels and 4 new relationships for name clashes. pid-to-kg's
   CASCADES_TO and HAS_STATE-like items are NOT mapped onto ours: different meaning, skip.
5. Use "relationship" everywhere, per D-P4-06. Fix the wording in the plan.
6. Read the code and report what actually exists for CFIHOS/QUDT anchoring and pid_audit.
   If anchoring is absent, Phase 10 adds dexpiClass as a standalone property. If pid_audit
   is absent, the three-way tag check becomes index vs vision only, and Phase 5 markup is
   written fresh with PyMuPDF. Do not build either now — just record it.
7. Put the review register in reports\ beside the exception register, same format
   and naming convention.

Apply points 3–7 as edits to PIDKG_UPGRADE.md itself so the plan matches the repo.
Note in the inventory that the session log says 44 tests and today's run is 41 passed,
4 skipped. Write docs/V1_3_INVENTORY.md, commit, and stop. Do not start Phase 1.
