# THIRD_PARTY_NOTICES.md — pid_graph

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

This file lists third-party tools that pid_graph uses but does not contain. Python packages
installed from `requirements.txt` are not listed here; each carries its own licence.

## pid-to-kg

| | |
|---|---|
| What it is | A tool that reads P&ID PDFs with vision and writes a process knowledge graph (`graph.json`) |
| Source | https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph |
| Pinned commit | `7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1` (8 Nov 2026) |
| Version | 0.1.0 (its `pyproject.toml`) |
| Licence | MIT |
| Copyright | Copyright (c) 2026 The pid-to-kg contributors |
| Local path | `third_party/pid-to-kg/` (git-ignored; never committed to pid_graph) |
| Environment | `.venv-pidkg/` (git-ignored; separate from pid_graph's `.venv/`) |

### How pid_graph uses it

- As an **unmodified tool**. None of its files is edited, and none of its source is copied into
  pid_graph modules. Its `LICENSE` file stays with it in `third_party/pid-to-kg/`.
- Its output `graph.json` is read as an input file by pid_graph's own loader (Phase 4 of
  `PIDKG_UPGRADE.md`). pid_graph decides what is allowed into the graph.
- Not adopted: its derived `TRIPS` and `ACTUATES`, its `CASCADES_TO` and state-like items, and
  DuckDB as the store (`PIDKG_UPGRADE.md` section 1).

### Set-up (Windows, from the pid_graph folder)

```
git clone https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph third_party/pid-to-kg
git -C third_party/pid-to-kg checkout 7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1
py -m venv .venv-pidkg
.venv-pidkg\Scripts\python -m pip install -r third_party\pid-to-kg\skills\pid-to-kg\scripts\requirements.txt pytest
```

Smoke test, run from `third_party\pid-to-kg` so that nothing is written into the clone:

```
$env:PYTHONDONTWRITEBYTECODE = 1
..\..\.venv-pidkg\Scripts\python -m pytest -q -p no:cacheprovider
```

### Run log

| Date | Python | Result | Notes |
|---|---|---|---|
| 10 Nov 2026 | 3.14.3 | 78 passed, 0 skipped | OCR package **not installed**: `rapidocr-onnxruntime` supports Python 3.10–3.12 only and this machine has 3.14 only. The OCR hints and automatic page-orientation steps will be skipped in Phase 3 unless a 3.10–3.12 interpreter is added. Installed: pypdfium2 5.15.2, pillow 13.0.0, pydantic 2.14.3, duckdb 2.0.0, networkx 3.7, pytest 9.2.0. Clone clean after the run (`git status` empty, HEAD at the pinned commit). |
