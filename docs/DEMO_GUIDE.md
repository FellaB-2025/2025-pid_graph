# U-100 Scenario Explorer — presenter's guide

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

A 15-minute demonstration of what a cross-document knowledge graph does for functional safety and alarm
management. Unit U-100 is synthetic: every document is dummy data with discrepancies planted on purpose.

## 1. Open it

Online (private to you until you share it from the page's Share menu):
https://claude.ai/artifact/6q2YAhHoohUn2HyCCV3XFa

From the project folder, with no network and no database:

```bash
.venv\Scripts\python -m pid_graph.demo
```

Then open `reports\demo_U-100.html`. Rebuild after any change to the documents in `data\`.

## 2. The one idea to land

Each document is right on its own page. The problem is between the pages: a closed MOC re-ranges a
transmitter, and nobody sees that the alarm on it is the condition the SRS sets for bypassing a trip. The
graph holds every tag once, with every document that mentions it attached, so one question walks all of
them. Say that first, then show it.

## 3. The page

| Part | What it is for |
|---|---|
| Demonstration order | Nine prepared scenarios, numbered in the order below |
| Scenario type and Element | Run the same question for any other initiator, alarm, SIF, MOC, tag or document |
| Step through / Next | Reveal one step at a time; the graph on the right lights up what that step followed |
| The graph walked | Columns: change, instruments, alarms, safety functions, hazard and equipment, documents. Select a node to see its properties and where each came from |
| Findings on what this scenario touched | Rule findings about the elements just walked, most serious first |
| All findings, Scorecard, Documents, How it works | The whole rule output, the test against the answer key, the document list, the method |

## 4. Running order

| # | Scenario | Show | The point |
|---|---|---|---|
| 1 | Bypass a trip initiator: PT-1001B | Step through all six steps | MOS-1001B has been on for 39.7 h against an SRS limit of 8 h with no out-of-service entry, and both compensating alarms are impaired by two closed MOCs. No single document shows this |
| 2 | Shelve or disable an alarm: LAH-1006 | Steps 2 and 3 | An "operational" alarm in the MADB is an IPL in the LOPA and a bypass condition in the SRS |
| 3 | MOC impact: MOC-2026-016 | "What the MOC did not list" | A re-range listed two documents; the graph reaches five more, including the SRS |
| 4 | MOC close-out: MOC-2026-014 | Last step | The SIS runs 2oo3; the C&E, SRS and SIL verification still say 1oo1 |
| 5 | SIF out of service: SIF-100-03 | Verdict | Sole layer in its LOPA scenario, no override switch, compensating alarm rationalised but never configured |
| 6 | Trip investigation: SIF-100-02 | Step 1 | C&E, SRS and configuration disagree on the voting |
| 7 | Where used: PT-1005 | Count of documents | One tag, ten documents. This is the search nobody has time to do by hand |
| 8 | Document revised: U100-SRS-001 | "Changes waiting on it" | Three open MOCs to fold into the next revision |
| 9 | Everything impaired now | Whole page | The combined picture at the time of the configuration export |

Then change the Element to something not prepared (bypass LT-1002A, shelve PAH-1001, where used XV-1001) to
show that nothing is scripted: each scenario type is one fixed template run for every element.

Finish on the Scorecard tab.

## 5. Scenario types

| Type | Question | What the template follows |
|---|---|---|
| Bypass a trip initiator | Q3 | INITIATES to the SIF; remaining initiators and the configured degraded vote; PROTECTS and LOPA CREDITS; SRS bypass conditions; curated COMPENSATES_FOR alarms and the findings against each; the live override state |
| Shelve or disable an alarm | Q5 | GENERATES and MEASURES; LOPA CREDITS; COMPENSATES_FOR and SRS bypass conditions that name it; trips on the same sensor; other alarms at the same place; MOCs that touched it |
| MOC impact | Q2 | The tags the MOC names; impact rules I1 to I5; documents reached against documents listed |
| MOC close-out | Q2/Q6 | The same, plus what the configuration, C&E, SRS and SIL verification each say now |
| SIF out of service | Q4 | PROTECTS; the other layers in each LOPA scenario; shared final elements; SRS conditions; compensating measures; open MOCs |
| Trip investigation | Q8 | Initiators and voting by document; pre-alarms; final elements and actions; trip notifications; the LOPA requirement |
| Where used | Q1 | Every document that shows the element or states a fact about it, and the same for its alarms |
| Document revised | Q6 | What the document covers; documents that share that content; open MOCs waiting on it |
| Everything impaired now | Q7 | Active overrides, disabled or unconfigured alarms, the state of each SIF and its compensating measures, changes in flight |

## 6. The rules behind the findings

Cross-document checks (`pid_graph/ops_checks.py`):

| Code | Rule |
|---|---|
| C1 | Document register names something not in the graph |
| C2 | Configured point not in the instrument index |
| C3 | Alarm configured but not rationalised in the MADB |
| C4 | Alarm rationalised in the MADB but not configured |
| C5 | Alarm setpoint or priority disagrees between alarm register, MADB and configuration |
| C6 | Alarm disabled in the configuration with no out-of-service entry |
| C7 | Configured range disagrees with the instrument index |
| C8 | Alarm limit at or beyond the end of the instrument's range |
| C9 | LOPA-credited alarm not recorded as an IPL in the MADB |
| C10 | SIF architecture disagrees between C&E, SRS, SIL verification and configuration |
| C11 | SIL verification assumption not met |
| C12 | Bypass provision disagrees with the SRS |
| C13 | Maintenance override active with no out-of-service entry |
| C14 | MOC implemented or closed with documents not revised |
| C15 | MOC impact list misses documents the graph links to the change |
| C16 | Alarm on an instrument the index lists as indication only |

X-codes (X1 to X36) are the design reconciliation that already existed: index against P&IDs, C&E, SRS and LOPA.

What a change reaches (MOC impact):

- I1 If the MOC names alarms, the alarms are what change and the other names are context; otherwise every
  element it names is affected.
- I2 An affected instrument's alarms are affected.
- I3 An affected alarm reaches the documents that credit it (LOPA), rely on it as a compensating measure
  (curated register) or name it in a bypass condition (SRS).
- I4 An alarm on a SIF initiator reaches that SIF's SRS, for the margin to the trip.
- I5 An affected element reaches every document it is shown on or that states a fact about it.

## 7. What to say when asked

**Is this AI deciding safety questions?** No. Every answer is a fixed, tested template that follows named
relationships. Nothing safety-relevant is extracted or written by a language model, and compensating measures
come only from a register an engineer approved.

**How do the documents get in?** Each is read as the register it is exported as (spreadsheet or CSV). A
document nobody parses, such as a procedure, still appears through the document register's "covers" column.

**What happens when two documents disagree?** Both claims are kept, each with its document, revision, sheet
and row. The graph never picks a winner; it reports the disagreement.

**Did it find all 23 planted problems by itself?** The checks were written knowing what was planted. The
scorecard shows the method works end to end on a known set. It does not show that it finds unknown problems;
the next batch of test documents is intended as a blind test.

**Is this real plant data?** No. U-100 is invented. No real project document or tag is in the repository.

## 8. Limits to be straight about

- One small unit: 82 nodes and 27 documents. Scale is untested.
- The as-installed SIL figure for SIF-100-02 is in the answer key, not calculated by the graph. The graph
  reports that the calculation credits a transmitter that is not installed.
- "Shown on" for procedures, proof tests and loop drawings comes from the document register, not from
  reading those documents.
- The page is a snapshot. It reflects the documents and the out-of-service register at the time it was built.
- An alarm tag named inside SRS free text is found by matching the tag in the bypass-conditions field. A
  differently worded condition would be missed.

## 9. Standards

The demonstration follows the lifecycle framing of IEC 61511 for safety instrumented functions and of
ISA-18.2 / IEC 62682 and EEMUA 191 for alarms (rationalisation records, shelving, out-of-service handling,
management of change). The standards are referred to by name only. No text, table or figure from any
standard is reproduced here, and users must hold their own licensed copies.
