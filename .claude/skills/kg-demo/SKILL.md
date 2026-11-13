---
name: kg-demo
description: Rebuild, republish, present or extend the U-100 Scenario Explorer (pid_graph's knowledge-graph demonstrator). Use when Alan asks to update or show the demo, add a scenario type, add a cross-document check, add or change dummy test documents, or prepare the demonstration for colleagues.
---

<!-- © 2026 Alan Bowden — Bowden Simulators. All rights reserved. -->

# U-100 Scenario Explorer

The demonstrator answers "pick a situation, show me everything it touches" over the pid_graph knowledge
graph. Read `CLAUDE.md` first; its rules apply here without exception. `docs/DEMO_GUIDE.md` is the
presenter's script and the list of limits.

## How it fits together

| Piece | File | Rule |
|---|---|---|
| Test documents and answer key | `scripts/make_dummy_batch1.py` -> `data/U100-*.xlsx`, `data/U100-BATCH1-ANSWER-KEY.json` | One generator; every planted item lists the cells that prove it |
| Loaders (off by default) | `pid_graph/loaders/{madb,config,silv,moc,docreg}_loader.py` | No new label or relationship (D-V13-12); claims go in source-named properties |
| Checks | `pid_graph/ops_checks.py` (C1-C26, impact rules I1-I5, `scorecard`), `pid_graph/quantities.py` | A fixed rule each; a finding names its documents; values are compared with their units, never as text |
| Scenarios | `pid_graph/demo.py` (`t_bypass`, `t_shelve`, `t_moc`, `t_sif_out`, `t_trip`, `t_where_used`, `t_doc_revised`, `t_now`) | One template per type, run for every element it applies to; trusted view only (T7) |
| Build a situation | `pid_graph/situation.py` (`build_model`, `evaluate`, `SITUATION_JS`) | Rules S1-S8; Python is the reference and the page's JavaScript must match it (`tests/test_situation.py` runs both) |
| Page | `pid_graph/demo_page.py` | Self-contained, no external load, house style (Arial, navy/teal/amber, light), copyright footer |
| Tests | `tests/test_batch1_documents.py`, `tests/test_ops_demo.py` | Relative to `data/` and the answer key; showcase verdicts are the only pinned values |

## Rebuild and republish

1. `.venv\Scripts\python -m pytest -q` must be green.
2. `.venv\Scripts\python -m pid_graph.demo --artifact <scratchpad>\u100-scenario-explorer.html`
3. Publish that file with the Artifact tool, passing `url` = https://claude.ai/artifact/6q2YAhHoohUn2HyCCV3XFa so
   the link Alan has shared stays the same. Keep the title "U-100 Scenario Explorer".
4. If counts or showcase verdicts changed, update "Known-good answers" in `CLAUDE.md`, section 4 of
   `docs/DEMO_GUIDE.md` and `SESSION_LOG.md` in the same commit.

## Extending it

**A new scenario type.** Add a row to `KINDS`, write `t_<kind>(g, element, findings)` with `Builder`
(each step names the relationships it followed; never write a conclusion the steps do not support), call it
in `run_all_scenarios` for every element it applies to, add the type to the `KINDS` array in the page
script and a row to section 5 of the guide. Add a showcase entry only if it makes a point the nine do not.

**A new check.** Add the title to `TITLES` in `ops_checks.py` (next free C number, never renumber), write
the rule in `run()`, map any answer-key `kind` to it in `KIND_TO_CODES`, give it a level in `STOP` / `WARN`
in `demo.py` (or pass `level=` to `add()` when the level depends on the case), and add the row to section 6 of the guide (a test compares the two tables).

**A new situation rule.** Change `evaluate()` and `SITUATION_JS` in the same edit, add a made-up-model test for the rule, add its row to
section 6a of the guide and to the docstring. If the rule needs a fact the model lacks, add it in `build_model()`; never read the graph
from `evaluate()`.

**New test documents.** Extend the generator, never the workbooks. Plant the discrepancy in the data, add
the item to `planted()` with its evidence cells, and regenerate.

**A blind test.** Follow `docs/BLIND_TEST.md` section 2 exactly: tag the freeze, brief a fresh agent as planter
(it must not read `ops_checks.py`, `reconcile.py`, `demo.py`, `situation.py`, their tests, the guide or any answer
key; it writes `data/<slug>/` with a `unit.json`), commit its files unread, run `python -m eval.blind_run`, commit
the sealed findings, then brief a second fresh agent as scorer and record its adjudication unedited. Never edit
or regenerate a sealed findings file or an adjudication. After fixing checks, the old unit is a regression test,
not a blind result; only a new unit planted by someone who has not seen the fixed checks counts.

**A document type the graph has not seen.** If it fits an existing loader pattern, add a value to
`O.DOC_TYPES` and say so in section 0c of the ontology document. If it needs a new label or relationship,
stop: that is a schema change, the ontology document changes first, and it is Alan's decision.

## What must stay true

- The default build (no operations documents) is the v1.3 graph unchanged; X1-X36 are untouched.
- Nothing safety-relevant is produced by a language model; `COMPENSATES_FOR` comes only from the curated
  register.
- Synthetic data only. No real drawing, tag or project document enters the repository.
- The page never claims more than the guide's "Limits" section allows. The U-100 scorecard always says the
  checks were written knowing what was planted; the blind result is shown beside it exactly as scored.
- British spelling; "node" and "relationship", never "edge".
