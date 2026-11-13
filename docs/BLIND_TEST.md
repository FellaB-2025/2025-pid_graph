# Blind test of the cross-document checks — unit U-200

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Run on 12 November 2026. All data is synthetic.

## 1. Why

The checks (C1–C16, X1–X36) were written by the same hand that planted the 23 problems in the U-100 test
documents, so "23 of 23" on U-100 shows only that the method works end to end. This test asks the question
that matters: what do the checks find on a unit they have never seen, with problems planted by someone else?

## 2. Protocol

| Step | Who | What | Evidence |
|---|---|---|---|
| Freeze | Runner | The checks, loaders and reconciliation are tagged before any new document exists | git tag `blind-freeze-1` |
| Plant | Planter (separate agent) | Invents unit U-200 and its documents, plants discrepancies between them, writes the answer key. Barred from reading the checks, the demonstrator, their tests and the U-100 answer key | `scripts/make_dummy_batch2.py`, `data/u200/`, `U200-BATCH2-ANSWER-KEY.json` |
| Seal the key | Runner | Commits the planter's files without opening the key or the generator | commit "Blind test: unit U-200 as planted" |
| Run | Runner | `python -m eval.blind_run --unit U-200 --freeze blind-freeze-1`: refuses to run if anything frozen has changed, never reads the key, writes every finding and scenario verdict | `eval/blind/U200-BLIND-RUN-FINDINGS.json`, committed before the key was opened |
| Score | Scorer (third agent) | Compares the sealed findings with the key and the documents. Wrote neither. Told to be strict | `data/u200/U200-BLIND-ADJUDICATION.json`, recorded unedited |

A planted item counts as **found** only if a finding states the actual disagreement (right element, right
substance). **Partly** means a finding points at the right place but states a lesser or different problem, or
the problem shows only in a scenario verdict. Everything in this document below this line is the scorer's.

## 3. Result

**12 of 24 found outright, 3 partly, 9 missed.**
**5 of 8 deliberately consistent items were wrongly flagged**, and
15 of the 85 findings were false alarms.

| Severity | Found | Partly | Missed |
|---|---|---|---|
| high | 3 | 3 | 4 |
| medium | 7 | 0 | 2 |
| low | 2 | 0 | 3 |

| Item | Severity | Result | What was planted | Found by |
|---|---|---|---|---|
| B2-01 | high | Missed | The SRS and the cause & effect chart trip SIF-200-04 at 345 degC but the SIS as exported trips at 355 degC. |  |
| B2-02 | high | Found | The SRS and the SIL verification use 1oo2 voting on the fuel gas low pressure transmitters, but the cause & effect chart and the configured logic are 2oo2. | C10 SIF-200-02; X20 SIF-200-02 |
| B2-03 | high | Missed | The SRS and SIL verification give SIF-200-03 two final elements voted 1oo2, but the cause & effect chart and the configured trip drive only XV-2001. |  |
| B2-04 | high | Missed | The SIL verification for SIF-200-01 still cites SRS Rev B and a risk reduction target of 120, while the LOPA and the current SRS Rev C require 200 and only 187 is achieved. |  |
| B2-05 | medium | Found | MOC-2026-034 is closed and moved the SIF-200-05 proof test interval to 24 months, but the SRS and the SIL verification were not revised and still say 12 months. | C14 MOC-2026-034 |
| B2-06 | high | Found | Maintenance override MOS-2030A on LT-2030A has been active since 2026-11-08 09:15 with no out-of-service entry, against an SRS limit of 4 h. | C13 MOS-2030A |
| B2-07 | medium | Found | LAH-2031 is disabled in the DCS although the master alarm database records it as implemented, and the temporary change that disabled it was closed without re-enabling it. | C6 LAH-2031 |
| B2-08 | high | Partly | SIF-200-05 is running 1oo1 on LT-2030B with its one approved compensating alarm, LAH-2031, disabled. | C13 MOS-2030A; C6 LAH-2031; scenario_verdict bypass:LT-2030A |
| B2-09 | medium | Found | The SRS limits a bypass of a SIF-200-04 temperature channel to 8 h but the three override switches are configured with a 24 h maximum. | C12 MOS-2020A; C12 MOS-2020B; C12 MOS-2020C |
| B2-10 | medium | Found | PT-2010B is 0-4 barg in the instrument index but the SIS point is scaled 0-6 barg. | C7 PT-2010B |
| B2-11 | low | Found | TT-2026 is a configured DCS point that appears in no other document. | C2 TT-2026 |
| B2-12 | medium | Found | PDAH-2003 is marked implemented in the master alarm database and listed in the alarm register, but the DCS export has no such alarm. | C4 PDAH-2003 |
| B2-13 | high | Found | The LOPA credits alarm PAH-2014 and the SRS makes it the bypass condition for SIF-200-03, but the alarm does not exist in any alarm list or the DCS. | X18 PAH-2014; C9 PAH-2014; X14 SIF-200-03 |
| B2-14 | high | Partly | PAL-2014 is rationalised at 0.6 barg but configured at 0.3 barg, which is below the 0.35 barg trip of the SIF it is the compensating alarm for. | C5 PAL-2014; scenario_verdict bypass:PT-2010A |
| B2-15 | medium | Found | MOC-2026-039 lowered the PAH-2041 limit to 5.5 barg and is closed, and the alarm documents were revised, but the DCS still alarms at 6 barg. | C5 PAH-2041 |
| B2-16 | low | Found | AAL-2024 is High priority in the master alarm database and the alarm register and Medium in the DCS. | C5 AAL-2024 |
| B2-17 | medium | Found | The LOPA credits TAH-2022 in scenario S-200-04, but the master alarm database records that credit against TAH-2021 and treats TAH-2022 as an uncredited operational alarm. | C9 TAH-2022 |
| B2-18 | high | Partly | TAH-2022 has been shelved since 2026-11-09 although it is the alarm LOPA scenario S-200-04 credits and a curated compensating measure for SIF-200-04. | scenario_verdict bypass:TT-2020A; scenario_verdict shelve:TT-2022.TAH |
| B2-19 | medium | Missed | The LOPA credits operator response to FAL-2002, for which the master alarm database allows 15 min, but the SRS gives the process safety time for the same event as 90 s. |  |
| B2-20 | high | Missed | PT-2011, the single initiator of SIF-200-03, is a SIS instrument in the index but is wired to DCS controller DCS-200-C01 in the export. |  |
| B2-21 | medium | Missed | TAH-2021 is rationalised on BPCS transmitter TT-2021 and approved as an independent compensating measure for SIF-200-04, but in the DCS it is configured on TT-2020A, one of that function's own initiators. |  |
| B2-22 | low | Missed | TAL-2021 was removed by rationalisation and is no longer in the alarm register, but it is still configured and enabled in the DCS. |  |
| B2-23 | low | Missed | The SIS bypass management procedure covers SIF-200-01 to SIF-200-04 only, so no bypass procedure covers SIF-200-05. |  |
| B2-24 | low | Missed | The out-of-service register still shows an override on TT-2020C as active more than ten days past its expiry, while the SIS export shows MOS-2020C off. |  |

## 4. The traps (things deliberately consistent)

| Control | Outcome | Scorer's reason |
|---|---|---|
| SIF-200-02 trip setpoint is written '350 mbarg' in the SRS and '0.35 barg' in the cause & effect chart and the SIS export: the same value in different units. | FLAGGED | X16 reports SRS 350 mbarg against C&E 0.35 barg as a trip setpoint disagreement; they are the same value. |
| LT-2040 is ranged 0-3000 mm in the index and its DCS block is scaled 0-100 %; LAL-2040 (600 mm = 20 %) and LAH-2040 (2400 mm = 80 %), with a 60 mm = 2 % deadband, are the same settings in both. Likewise PT-2025 is '-25 to 25' mmWG in the index and -25 / 25 in the export. | FLAGGED | The LT-2040 range (0-3000 mm against 0-100 %) and both alarm setpoints (600 mm / 20 %, 2400 mm / 80 %) are flagged as disagreements although they are the same settings; PT-2025 was correctly left alone. |
| Two bypasses are properly recorded. MOS-2001B on FT-2001B is active since 2026-11-12 02:10 and has a matching active out-of-service entry (OOS-200-0010) inside the 8 h the SRS allows, with its compensating alarm FAL-2002 enabled. The PT-2010A bypass of 2026-10-28 is closed in the register (OOS-200-0007), closed as MOC-2026-044, and MOS-2010A is off. | left alone | No finding flags either bypass; note that the bypass:FT-2001B scenario verdict wrongly says MOS-2001B has no out-of-service entry (OOS-200-0010 exists) and the MOC-2026-044 verdicts are 'stop'. |
| LAH-2031 is listed in LOPA scenario S-200-05 with no PFD: deliberately not credited, because it shares LT-2031 with the initiating control loop. The master alarm database agrees (IPL Credit 'No'). | left alone | LAH-2031 was correctly loaded as listed but not credited; no C9 finding was raised for it. |
| MOC-2026-031 (re-range PT-2013 to 0-16 barg) is closed out properly: the index and the DCS point both show 0-16 barg and the one document to revise was revised. | FLAGGED | C15 says the impact list misses the MADB (via PAL-2013), but a re-range changes nothing the MADB records; an advisory 'check each' prompt, so a soft flag. |
| MOC-2026-043 (remove LAL-2031) was cancelled and MOC-2026-046 (TAH-2023 on-delay to 60 s) is still in review: LAL-2031 is rightly still in every alarm list, and TAH-2023 rightly still has a 30 s on-delay everywhere. | left alone | Nothing flags LAL-2031 or the TAH-2023 on-delay; the C15 on MOC-2026-046 is about the impact list, not about these settings. |
| FALL-2001 is configured in the SIS as a trip notification of SIF-200-01 and is in neither the master alarm database nor the alarm register. That is correct: a trip is not an alarm. | FLAGGED | C3 raises a warning that FALL-2001 is configured with no MADB record, although its own detail notes it is a trip notification and a trip is not an alarm. |
| For SIF-200-01 to SIF-200-04 the SRS states the proof test interval in one cell ('Sensors 12 months, final elements 24 months') where the SIL verification has two columns (12 months / 24 months); the SRS writes architectures as '2oo3 FT' or '1oo2 (XV-2001 or XV-2002)' where other documents write '2oo3' or list the tags. Same facts, different wording. | FLAGGED | Eight stop-level C11 findings (two per SIF) report the SRS cell 'Sensors 12 months, final elements 24 months' as disagreeing with the SIL verification's 12 and 24 months; the architecture wording was handled correctly. |

## 5. Every other finding

| Class | Code | Count | Scorer's reason |
|---|---|---|---|
| true unplanted | C2 | 11 | True and checked: none of the eleven override switches has an index row. Info level; soft switches are not normally index items, so of little value. |
| true unplanted | C15 | 1 | Variant of B2-05: the LOPA link is defensible (its PFD credit for SIF-200-05 depends on the test interval); the other four documents listed carry no proof test interval and are where-used noise. |
| true unplanted | C15 | 1 | Variant of B2-13: correctly notes the LOPA already credits and the SRS already relies on the PAH-2014 this MOC adds; whether they belong on the impact list is arguable. |
| input gap | X1 | 37 | No P&ID extraction or topology was supplied for U-200 (unit.json: topology and pdf null), so every one of the 37 index rows is reported as not found on a P&ID. |
| input gap | X7 | 2 | No P&ID title block was supplied; the document register does give revisions D and C, so the graph holds each P&ID twice (UNKNOWN and the registered revision). |
| false alarm | C11 | 8 | Checked all four SIFs: SIL verification 12 months sensors / 24 months final elements is exactly what the SRS cell says; the compound cell was not parsed (clean control). |
| false alarm | C5 | 2 | 600 mm and 2400 mm are 20 % and 80 % of the 0-3000 mm span the index remark says the block is scaled to (clean control). |
| false alarm | C7 | 1 | 0-3000 mm and 0-100 % are the same range; the index remark says so (clean control). |
| false alarm | X16 | 1 | 350 mbarg equals 0.35 barg (clean control). |
| false alarm | C3 | 1 | A SIS trip notification is rightly absent from the MADB; the finding is a warning even though its detail concedes the point (clean control). |
| false alarm | C15 | 1 | The MADB records PAL-2013 in barg with no range, so the PT-2013 re-range changes nothing in it; the MOC was closed out properly (clean control). |
| false alarm | C15 | 1 | Neither the instrument index nor its alarm register sheet has an on-delay column, so an on-delay change does not reach it. |

"Input gap" findings arise because U-200 was supplied without P&ID drawings, not from a discrepancy.

## 6. What would have caught the rest (scorer's words)

- B2-01, B2-03: every SIF attribute (trip setpoint, initiators, voting, final elements) should be compared across SRS, cause & effect, SIL verification AND the configured logic, with values normalised to one unit; here the configuration was compared on sensor voting only and final elements not at all.
- B2-04: check the SIL verification's own target and cited source revision against the current SRS and LOPA requirement, and re-test 'achieved' against the current target rather than trusting the calculation's 'meets target'.
- B2-19: for every alarm credited as a protection layer, compare the operator response time allowed in the alarm database with the process safety time of the scenario it is credited in.
- B2-20: compare the system, controller and I/O allocation of each instrument between the index and the configuration, and flag any SIF initiator or final element that is not on the safety logic solver.
- B2-21: compare an alarm's source tag (not only setpoint and priority) across alarm register, alarm database and configuration, and flag a compensating alarm that is sourced from an initiator of the SIF it backs up.
- B2-22: use the alarm database's lifecycle status in both directions - an alarm recorded as removed or not implemented that is still configured and enabled is a discrepancy, the mirror of 'implemented but not configured'.
- B2-23: a coverage check on the document register - every SIF in the SRS should appear under each kind of procedure that covers its sibling SIFs (bypass, proof test).
- B2-24: reconcile the out-of-service register against the live override and alarm states in both directions and against the clock - an 'active' entry whose override is off, or that is past its expiry, is a finding.
- B2-08, B2-18 (partial): as-found interactions should be findings in their own right - an active bypass, shelf or disabled alarm whose compensating measure or LOPA credit is itself out of service - not left to what-if verdict text.
- B2-14 (partial): compare the configured limit of every pre-alarm or compensating alarm with the trip setpoint of the SIF it stands in front of; the alarm must sit on the safe side of the trip.

## 7. Scorer's notes

Counted strictly on the `findings` list; scenario verdicts earn at most partial. Found 12 of 24, partial 3, missed 9. Most arguable calls: B2-14 would be 'found' on a lenient reading (the 0.6 v 0.3 barg mismatch is stated; the comparison with the 0.35 barg trip is not), and B2-18 is a weak partial that a harder scorer could call missed - so found is 12 to 13 and missed 9 to 10 depending on the reader. B2-05, B2-07, B2-15 and B2-17 are 'found' on their main claim although part of the story (values still at 12 months, the closed MOC, the credit sitting on TAH-2021) is not in any finding. Clean controls: 5 of 8 flagged by findings. A sixth (the two properly recorded bypasses) is not flagged by any finding but is contradicted in scenario verdicts: bypass:FT-2001B says MOS-2001B has no out-of-service entry when OOS-200-0010 is there, and moc/closeout:MOC-2026-044 are 'stop' for a bypass that was closed correctly. Scenario verdicts also assert agreement where the documents disagree: trip:SIF-200-04 and trip:SIF-200-03 say C&E, SRS and configuration agree (B2-01, B2-03), bypass:PT-2011 is 'ok' (B2-20), closeout:MOC-2026-039 is 'ok' (B2-15). False alarms: 15 findings from 7 entries; 12 are unit or wording normalisation (mbarg v barg, % of span v mm, a compound proof-test cell), 8 of them at stop level. The two C15 impact-list entries classed false are advisory 'check each' prompts; a lenient scorer could call them noise rather than false, and I kept the other two C15 entries as true because their content is correct. Input gap: 39 findings exist only because no P&ID was supplied. The key itself checked out against the documents wherever I tested it (evidence cells, the RRF 27 and 28 figures, dates); I found no error in it and did not need the generator script. Verified by reading every workbook and CSV directly; I did not read the checker's source. Confidence is high on the found and missed verdicts, moderate on the three partials and on the C15 classifications.

## 8. What this means

- The method transfers. The loaders read a new unit's documents without change and the checks found half of
  what a stranger planted, including the unrecorded override, the disabled alarm and the range change.
- It is not ready to be trusted unsupervised. Half the high-severity items were missed or only partly found,
  and five of eight traps were sprung.
- The false alarms have two causes, both ordinary: values compared as text without converting units
  (350 mbarg against 0.35 barg; millimetres against per cent of span) and a compound SRS cell read as one value.
  Eight of the fifteen come from that one cell.
- The misses are mostly comparisons nobody wrote, not comparisons that failed: trip setpoint against the
  configuration, final elements across documents, response time against process safety time, which system a
  SIF device is wired to, the out-of-service register checked in both directions.
- Two statements in scenario text were simply wrong on U-200 (a bypass described as having no out-of-service
  entry when it had one; trips described as agreeing when they did not). Those are defects in the scenario
  templates, found by this test.

## 9. Rules for what happens next

1. This result is never overwritten. Fixes are scored as a separate, later row.
2. A fix must be a general rule (section 6), never a special case for U-200.
3. After fixes, U-200 becomes a regression test: its score then shows the fixes work, and nothing more.
4. Only a new unit, planted by someone who has not seen the fixed checks, counts as the next blind result.

## 10. After the fixes — U-200 as a regression test (not a blind result)

12 November 2026, later the same day. Sections 1 to 9 are the record and are unchanged; the sealed findings
(`eval/blind/U200-BLIND-RUN-FINDINGS.json`) and the adjudication were not touched. What follows was produced by the
person who wrote the fixes, with the answer key open. It shows that the fixes do what they were written to do and
nothing more (rule 3). It has not been scored by anyone independent.

| | Blind run (scored independently) | After the fixes (self-checked) |
|---|---|---|
| Planted items with a finding that states them | 12 of 24, 3 partly | 24 of 24 |
| Findings the scorer called false alarms | 15 | 2 still raised, 1 reduced to information, 12 gone |
| Traps touched by a finding | 5 of 8 | 2 of 8 (the trip notification, now information only; the PT-2013 re-range impact list) |
| Findings in all | 85 | 87 (45 C, 42 X; 39 of the X only because no P&IDs were supplied) |

What changed, each as a general rule (rule 2):

| Section 6 item | Fix | Code |
|---|---|---|
| Values normalised to one unit | `pid_graph/quantities.py`: values are compared with their units; gauge and unstated pressure are never converted into each other; a limit in per cent of span is read through the index range | C5, C7, X16 |
| Compound SRS cell | A proof-test cell is split into its sensor and final-element statements before it is compared | C11 |
| B2-01 | Trip setpoint as configured against the C&E and the SRS | C17 |
| B2-03 | Final elements and their voting across C&E, SRS, SIL verification and configuration | C10 |
| B2-04 | The SIL verification's cited revision and target against the current SRS; achieved risk reduction against the current SRS and LOPA requirement | C18 |
| B2-19 | Operator response time in the MADB against the process safety time of the SIF in the same LOPA scenario | C19 |
| B2-20 | System in the index against the configuration; a SIF initiator or final element not on the SIF's logic solver | C20 |
| B2-21 | An alarm's source in each document; a compensating alarm sourced from an initiator of the SIF it backs up | C21 |
| B2-22 | An alarm the MADB records as removed that is still configured and enabled (and such an alarm is no longer "rationalised but not configured") | C22 |
| B2-23 | A procedure that covers two or more SIFs and misses one that no other procedure of its kind covers | C23 |
| B2-24 | An active out-of-service entry past its expiry, or whose override is off in the configuration | C24 |
| B2-08, B2-18 | As found: an element out of service whose compensating measure, SRS bypass condition or LOPA credit is also out | C25 |
| B2-14 | An alarm on the same variable and of the same sense as a trip must come before the trip | C26 |
| Trip notification | Still reported when it has no MADB record, but for information: whether trips are rationalised is for the alarm philosophy | C3 |

Scenario text that was wrong on U-200 and is corrected: a recorded bypass now quotes its out-of-service entry
instead of saying there is none; a trip is said to agree only if no finding about its setpoint, voting, final elements
or logic solver exists; a bypass of a transmitter that is not on the logic solver is a stop; a closed MOC whose element
still disagrees between documents is a caution; a temporary change is judged on whether it was removed, not on
documents it never had to revise.

Not fixed, and why:

- The two MOC impact prompts the scorer classed as false (a re-range reaching the MADB; an on-delay change reaching the
  alarm register). Rule I2 sends a change on an instrument to every document its alarms are in. Narrowing it needs to
  know which attribute a change alters and which attributes each document holds; the MOC register gives the first only
  as free text. Left as "check each".
- The 39 input-gap findings: U-200 still has no P&IDs.
- C19 compares response time with the process safety time of the SIF in the same scenario. That is the comparison the
  planted item used; an engineer should say whether it is the right one for a pre-alarm, which has the time from the
  alarm limit, not from the trip point.

What U-100 gained from the same rules (none planted): C17 on SIF-100-01 (configured 68 barg, SRS 65 barg) and C19 on
PAH-1001 and LAH-1006 (10 min to respond against 120 s and 300 s). Eight of the ten new checks have nothing to fire on in U-100.

The next blind result needs a new freeze tag and a new unit from a planter who has not seen C17 to C26 (rule 4).

## 11. Second blind test — unit U-300

12 November 2026. Checks frozen at `blind-freeze-2` (sections 1 to 10 describe how they got there). Same protocol as
section 2: a planter who had not read the checks wrote U-300 (an export gas compressor) and its key
(`scripts/make_dummy_batch3.py`, `data/u300/`); the files were committed unread; `eval/blind_run.py` ran the frozen
checks and the sealed findings (`eval/blind/U300-BLIND-RUN-FINDINGS.json`) were committed before the key was opened; a
third agent scored them (`data/u300/U300-BLIND-ADJUDICATION.json`, recorded unedited). Everything in the tables below
is the scorer's.

How blind it was: less than it should be. Project instructions (`CLAUDE.md`) are loaded into every agent in this
repository, so the planter and the scorer both saw the check code ranges and the "known causes" of the U-200 result.
The planter also read the U-200 documents as format examples, and those show that unit's planted problems. Both
say they did not use it. A planter working outside this repository would remove the doubt.

**17 of 25 found outright, 3 partly, 5 missed.** **1 of 10 deliberately consistent items flagged by a finding** (2 more contradicted in scenario text only), and 6 of the 59 findings were false alarms.
On a lenient reading the scorer gives found 16 to 19, partly 1 to 4, missed 5, false alarms 2 to 6.

| Severity | Planted | Found | Partly | Missed |
|---|---|---|---|---|
| high | 11 | 8 | 1 | 2 |
| medium | 9 | 7 | 2 | 0 |
| low | 5 | 2 | 0 | 3 |

| | U-200 (blind-freeze-1) | U-300 (blind-freeze-2) |
|---|---|---|
| Found outright | 12 of 24 | 17 of 25 |
| Partly | 3 | 3 |
| Missed | 9 | 5 |
| Clean controls flagged | 5 of 8 | 1 of 10 |
| False alarms | 15 of 85 findings | 6 of 59 findings |
| Input-gap findings | 39 | 11 |

The two units are different and were planted by different agents, so the columns are not a like-for-like
measure of improvement; and see "How blind it was" above.

| Item | Severity | Result | What was planted | Found by |
|---|---|---|---|---|
| B3-01 | high | Found | SIF-300-06 is 1oo2 on PT-3007A/B in the C&E, the SRS and the SIL verification, but the logic solver is configured 2oo2, so one failed transmitter defeats the trip. | C10 SIF-300-06 |
| B3-02 | high | Found | SIF-300-01 must trip K-301 through XY-3040 and close XV-3001 (C&E, SRS, SIL verification), but the configured trip drives XY-3040 only; XV-3001 is not closed. | C10 SIF-300-01 |
| B3-03 | high | Found | MOC-2026-053 (closed) lowered the SIF-300-03 trip from 85 to 82 barg and the SRS and C&E say 82 barg, but the logic solver still trips at 85 barg. | C17 SIF-300-03 |
| B3-04 | high | Partial | MOC-2026-055 (closed) extended the XV-3001 proof test interval to 24 months and the SRS says so, but the SIL verification still assumes 12 months and was not revised; at 24 months SIF-300-01 achieves about RRF 70 against a target of 100. | C14 MOC-2026-055 |
| B3-05 | high | Found | The revalidated LOPA requires SIL 2 / RRF 100 of SIF-300-02 (scenario S-300-02), but the SRS and the C&E still specify SIL 1 (RRF 10) and the SIL verification achieves only RRF 91. | X15 SIF-300-02; C18 SIF-300-02 |
| B3-06 | high | Missed | LOPA scenario S-300-06 credits PAL-3006 (PFD 0.1), but PAL-3006 is generated from PT-3006, the transmitter of the PIC-3006 loop whose failure is the initiating event; without the credit SIF-300-06 would need RRF 200, not 20. |  |
| B3-07 | high | Found | PAL-3021 (credited IPL in S-300-05, compensating measure and SRS bypass condition for SIF-300-05) is rationalised at 1.5 barg but configured at 0.7 barg, below the 0.8 barg trip, so it cannot annunciate before the trip. | C26 PAL-3021; C5 PAL-3021 |
| B3-08 | high | Found | MOC-2026-057 and out-of-service entry OOS-300-0010 record the TT-3014B bypass as restored and closed on 2026-11-04, but MOS-3014B is still active in the configuration export of 2026-11-12 06:00 (since 2026-11-04 08:00, about 190 h against 8 h), leaving SIF-300-04 on one transmitter with no live record. | C13 MOS-3014B |
| B3-09 | high | Found | PT-3012A is overridden (OOS-300-0012) with compensating measures recorded as confirmed and PAH-3013 noted as active, but PAH-3013 has been shelved since 2026-11-10 with PT-3013 isolated (OOS-300-0011); PAH-3013 is the only approved compensating measure and the SRS bypass condition for SIF-300-03, and a credited IPL in S-300-03. | C25 PT-3012A; C25 PAH-3013 |
| B3-10 | high | Found | SIF-300-02 is assigned to the logic solver SIS-LS-300 in the C&E, SRS, SIL verification and index, but it is configured in the DCS controller DCS-300-C01, with LT-3005 and XV-3003 wired to DCS I/O; it is not independent of the BPCS level loop whose failure is its demand. | C20 LT-3005; C20 XV-3003 |
| B3-11 | high | Missed | PT-3020B and PT-3020C are both overridden at the export time (MOS-3020B and MOS-3020C active; OOS-300-0014 and OOS-300-0015 overlap), but the SRS allows only one channel of SIF-300-05 at a time and the SIL verification covers one bypassed channel only; the trip rests on PT-3020A alone. |  |
| B3-12 | medium | Found | LAL-3003 was removed under MOC-2026-058 (MADB 'Removed', no longer configured), but it is still the SRS bypass condition and the approved compensating measure for SIF-300-02 and is still listed in the alarm register; the MOC did not list the SRS or the compensating measures register and the alarm register was not revised. | C15 MOC-2026-058; C14 MOC-2026-058 |
| B3-13 | medium | Found | LT-3002C is configured 0-1500 mm while the index gives 0-2000 mm (as LT-3002A/B are configured); the SIF-300-01 trip point of 1500 mm is at the top of that channel's configured range. | C7 LT-3002C |
| B3-14 | medium | Found | The SIL verification of SIF-300-04 takes TT-3014A and TT-3015 as the 1oo2 sensor pair; TT-3015 is the BPCS transmitter. The C&E and the configured trip use TT-3014A and TT-3014B. | C10 SIF-300-04 |
| B3-15 | medium | Partial | The out-of-service register starts the PT-3020C override at 2026-11-12 04:00 (2 h before the export), but the logic solver shows MOS-3020C active since 2026-11-10 16:00: 38 h at the export against the 8 h limit, which the register does not show. |  |
| B3-16 | medium | Found | PDAL-3030 is rationalised at 0.5 bar (50 kPa) but configured at 5 kPa on a point scaled 0-200 kPa: a factor of ten low, so the seal gas differential pressure alarm will not annunciate until the differential is almost lost. | C5 PDAL-3030 |
| B3-17 | medium | Found | PT-3033 (MOC-2026-054, implemented) is on PID-300-003 and configured in the DCS, but it is not in the instrument index, which the MOC lists as still to be revised. | C2 PT-3033; X2 PT-3033; C14 MOC-2026-054 |
| B3-18 | medium | Found | MOC-2026-056 (closed) raised LAH-3003 from 1100 to 1200 mm and records the alarm register as revised; the MADB and the configuration say 1200 mm but the alarm register still says 1100 mm. | C5 LAH-3003 |
| B3-19 | medium | Found | FAH-3032 (primary seal vent flow high, High priority) is in the MADB as implemented and in the alarm register, but no such alarm is configured. | C4 FAH-3032 |
| B3-20 | medium | Partial | The LOPA credits TAH-3015 in S-300-04 on the basis that 10 min are available between the alarm and the trip point, but the MADB rationalises TAH-3015 with a time to respond of 30 min. | C19 TAH-3015 |
| B3-21 | low | Found | The SIL verification takes the SIF-300-05 target from SRS Rev B (RRF 10); the current SRS Rev C and the LOPA require RRF 20. The achieved RRF still exceeds both. | C18 SIF-300-05 |
| B3-22 | low | Missed | MOC-2026-060 (in review, not approved) proposes raising the TAH-3016 on-delay from 10 s to 60 s; the configuration already has 60 s while the MADB has 10 s. |  |
| B3-23 | low | Found | PAH-3006 (PT-3006, 32 barg, Low) is configured in the DCS but is in neither the MADB nor the alarm register. | C3 PAH-3006 |
| B3-24 | low | Missed | The index places TT-3008 on L-302 (compressor suction, downstream of V-301); the P&ID extraction shows it on L-301, upstream of the scrubber. |  |
| B3-25 | low | Missed | The document register lists the cause & effect chart U300-CE-CHART at Rev B; the chart in use is Rev C (re-issued under MOC-2026-053). |  |

### The traps

| Control | Outcome | Scorer's reason |
|---|---|---|
| SIF-300-05 trip setpoint: 0.8 barg in the C&E and the configuration, 80 kPag in the SRS. | left alone | No finding on the SIF-300-05 trip setpoint; trip:SIF-300-05 says the C&E, SRS and configuration agree. 80 kPag was read as 0.8 barg. |
| SIF-300-01 trip setpoint: 1500 mm in the C&E and the configuration, 1.5 m in the SRS. | left alone | No finding on the SIF-300-01 trip setpoint (1.5 m against 1500 mm). The only SIF-300-01 finding is the final element one (B3-02). |
| PDT-3023 and PDAH-3023: index range 0-2.5 bar and alarm 1 bar (register, MADB) against a configured range of 0-250 kPa, limit 100 kPa and deadband 5 kPa. The configured range of PDT-3030 (0-200 kPa against 0-2 bar) and the PDAL-3030 deadband are the same kind. | left alone | No C5 or C7 finding for PDT-3023, PDAH-3023 or the PDT-3030 range; only the PDAL-3030 limit was flagged, which is the planted item B3-16. |
| LT-3002B overridden: MOS-3002B active since 2026-11-12 01:30, out-of-service entry OOS-300-0013 active from 01:30 to 09:30. | left alone | No finding flags MOS-3002B or OOS-300-0013. But the bypass:LT-3002A/B/C scenario verdicts (warn) say compensating measure LAH-3003 'is impaired'. In the documents LAH-3003 is configured at 1200 mm, enabled and not shelved; the only thing wrong with it is the stale 1100 mm in the alarm register (B3-18). The verdict contradicts this control although no finding does. |
| MOC-2026-052 proposed lowering the SIF-300-04 trip from 175 to 165 degC; every document and the configuration still say 175 degC and no document was revised. | left alone | No C14, C15 or C17 finding on MOC-2026-052 or the 175 degC trip. But the moc:MOC-2026-052 scenario verdict is 'stop: the plant and its safety documents disagree because of this change', which is wrong: the change was cancelled and every document and the configuration say 175 degC. Contradicted by a scenario verdict, not by a finding. |
| LAH-3003 is listed in the LOPA IPL sheet for S-300-01 with no PFD, and is marked 'IPL Credit: No' in the MADB, yet it is the approved compensating measure and the SRS bypass condition for SIF-300-01. | left alone | No finding treats the uncredited LAH-3003 as a problem; the LOPA loader's 'listed, not credited' skip is in load_reports only, as the key expects. C15 MOC-2026-056 mentions LAH-3003 as a compensating measure and bypass condition, which is true and is not about the LOPA credit. |
| PT-3011 remark says it was re-ranged from 0-100 to 0-120 barg; MOC-2026-050. | flagged | C15 (warn) says the impact list of MOC-2026-050 misses U300-MADB-001 because of PAH-3011, and the moc/closeout:MOC-2026-050 verdicts (warn) say 'the impact list is incomplete'. The MADB holds no range and PAH-3011 is 75 barg in engineering units in all three documents, so nothing in the MADB needed revising. The MOC itself lists PAH-3011 as an affected tag and the finding only says 'check each', so a lenient reader could call it advisory noise and leave this control unflagged. |
| PT-3007B temporary bypass (MOC-2026-051, OOS-300-0009). | left alone | No finding on PT-3007B, MOS-3007B, OOS-300-0009 or MOC-2026-051; the moc/closeout:MOC-2026-051 verdicts are 'ok'. |
| VAH-3017B is disabled in the configuration while the MADB says implemented. | left alone | No finding on VAH-3017B being disabled; moc:MOC-2026-059 is 'ok'. now:U-300 mentions one unnamed 'alarm problem' the register does not show; it cannot be VAH-3017B on the evidence (OOS-300-0016 is active) but the verdict does not say which alarm it means. |
| SIF-300-03, -04, -05 and -06 achieve a higher SIL band in the SIL verification than their target; PAH-3011 (75 barg) and PAH-3013 (76 barg) are two high pressure alarms on the discharge with different limits. | left alone | No finding on a SIL achieved above target, and none on PAH-3011 against PAH-3013. C18 SIF-300-05 concerns the superseded target (B3-21), not the higher band. |

### Every other finding

| Class | Code | Count | Level | Scorer's reason |
|---|---|---|---|---|
| true unplanted | C2 | 14 | info | True and checked: none of the fourteen override switches has an index row. The key's note expects them as configured-only points; soft switches are not normally index items, so of little value. |
| true unplanted | C15 | 1 | warn | True and checked: the MOC that raised LAH-3003 lists only the MADB and the alarm register, while LAH-3003 is the approved compensating measure for SIF-300-01 (whose register entry quotes the setpoint) and its SRS bypass condition. The curated register already says 1200 mm, so nothing is wrong today; the impact list was still short. |
| variant | C15 | 1 | warn | Variant of B3-04: the LOPA link is defensible (its 0.01 credit for SIF-300-01 depends on the proof test interval, and at 24 months the function no longer delivers it); the other six documents listed carry no proof test interval and are where-used noise. |
| false alarm | C15 | 1 | warn | Clean control CC3-07: the MADB has no range field and PAH-3011 is 75 barg everywhere; the re-range needed no MADB revision. |
| false alarm | C15 | 1 | warn | Seven documents listed for the 85 to 82 barg trip change; checked each: the index and the SIL verification carry no trip setpoint, the LOPA none, the compensating measures register already says 82 barg, and the P&ID, loop drawings and bypass procedure were not supplied. The one place that is actually wrong, the configuration, is not on the list (that is C17 / B3-03). Advisory 'check each' wording; a lenient reader could call it noise rather than false. |
| false alarm | C15 | 1 | warn | Says the on-delay change should reach the instrument index; the alarm register sheet has no on-delay column, so there is nothing to revise. It concerns the MOC of B3-22 but says nothing about the change having been made before approval. |
| false alarm | C19 | 3 | warn | Compares the MADB time to respond with the process safety time of the SIF, which runs from the trip point, not from the alarm. For PAH-3013 the LOPA itself states 15 min available against 10 min in the MADB, so the documents agree. For PAL-3006 and PAL-3021 the LOPA states no time; the quoted figures are in the documents but are not the same quantity, so no disagreement is shown. A lenient reader could call those two unverifiable rather than false. |
| input gap | X1 | 3 | info | Checked: all three are in the index on PID-300-002 and absent from the topology CSV. The key's note (4) says the CSV format cannot carry push-button, relief valve and relay tags; an artefact of the input, neither planted nor a fair false alarm. |
| input gap | X7 | 3 | info | No P&ID PDF was supplied (unit.json pdf: null; key note 5), so title-block revisions are unknown to the loaders. The document register does give E, D and C. |
| input gap | X8 | 5 | info | Battery limits and the flare header in the topology CSV belong to units that were not supplied. Informational and true as far as it goes; not named in the key's note, so 'true unplanted' would also be defensible. |

### What would have caught the rest (scorer's words)

- B3-04: when a change alters a proof test interval, compare the interval in the SRS with the interval actually used in the SIL verification (per subsystem, in hours) and re-test the achieved risk reduction at the new interval against the target, instead of relying on the change register's own 'documents revised' column.
- B3-06: for every alarm credited as a protection layer, trace its source transmitter and check it is not part of the control loop (sensor, controller or valve) named as the initiating event of the same scenario; an alarm that shares a component with the initiating cause cannot be credited.
- B3-11: evaluate the overrides active at the same moment per function, not one at a time: count the channels of one SIF overridden together and test that against the SRS bypass condition ('one channel at a time') and the degraded voting the SIL verification covers.
- B3-15: for every override that is active in the control system, compare its 'active since' time with the start time of the matching out-of-service entry, and compute the duration from the control system time, as a finding rather than only inside a scenario answer.
- B3-20: compare the operator response time in the alarm database with the time the hazard analysis itself says is available for that alarm (alarm to trip point), not with the safety function's process safety time, which is a different interval; where the analysis states no time, say so instead of substituting another figure.
- B3-22: compare every configured alarm attribute that the alarm database also holds (on-delay, off-delay, deadband, not only setpoint and priority), and where a difference matches the proposed value of a change that is not yet approved, report it as a change made ahead of approval.
- B3-24: compare the line or equipment an instrument is assigned to in the index with the line it sits on in the drawing extraction, not only the drawing number.
- B3-25: compare the revision of each document as loaded (from its own title block) with the revision the document register holds for it; two revisions of one document number in the same load is itself a finding.

### Scorer's notes

Counted strictly on the `findings` list; scenario verdicts earn at most partial. Found 17 of 25, partial 3, missed 5 (high 8 / 1 / 2 of 11, medium 7 / 2 / 0 of 9, low 2 / 0 / 3 of 5). Of the 59 findings, 26 are the basis of a found or partial item; the other 33 are 15 true unplanted (14 of them info-level override switches with no index row), 11 input gap, 6 false alarm and 1 variant. Clean controls: 1 of 10 flagged by a finding (CC3-07, by an advisory C15), and two more contradicted only by scenario verdicts: moc:MOC-2026-052 is 'stop' for a cancelled change that altered nothing (CC3-05), and bypass:LT-3002A/B/C call LAH-3003 'impaired' although it is configured, enabled and not shelved (CC3-04). Most arguable calls, all scored the stricter way: B3-04 (C14 says the SIL verification was not revised after the interval change but never states 12 against 24 months or the fall to about RRF 70) and B3-20 (C19 flags the right alarm with the right 30 min but against the 5 min process safety time of the SIF, not the 10 min in the LOPA, and fires equally on all four credited alarms) would both be 'found' to a lenient reader; B3-12 is 'found' only by reading C14 and C15 together and a harder scorer could call it partial. So found is 16 to 19, partial 1 to 4, missed 5 on any reading. B3-03, B3-08 and B3-18 are found on the disagreement itself although the 'closed on paper' half is in scenario verdicts only. False alarms: 6 strictly (three C19, three C15, all warn level); 3 if the two C19 entries with no LOPA time and the MOC-2026-053 where-used list are treated as unverifiable or noise. CC3-07 would be unflagged, and false alarms 2, only if the MOC-2026-050 entry were also treated as advisory. The five X8 battery-limit stubs are classed input gap; true unplanted would also be defensible. Other scenario verdicts that are wrong or unsafe against the documents: bypass:TT-3014A is 'ok, bypass can proceed' while MOS-3014B is already active on the other channel of the 1oo2 pair, and bypass:PT-3020A, PT-3012B/C and LT-3002A/C are only 'warn' with no mention that another channel of the same function is already overridden (the SRS allows one at a time); bypass:TT-3014B says there is 'no out-of-service entry' where a closed one (OOS-300-0010) exists (the C13 finding words it correctly as no active entry); shelve:LT-3003.LAL advises on shelving an alarm that has been removed and is not configured; shelve:PT-3006.PAL calls PAL-3006 an independent protection layer (B3-06); moc:MOC-2026-060 says only that the impact list is incomplete (B3-22); now:U-300 counts one override the register does not show and leaves out the 38 h of MOS-3020C. trip:SIF-300-05 'ok' is correct for the trip settings. The key: every evidence cell of all 25 items was opened and agrees with the files, and the derived figures check (190 h, 38 h, RRF about 70 at 24 months, RRF 200 without the PAL-3006 credit, the LOPA arithmetic). One small error: CC3-10 says SIF-300-03 achieves a higher SIL band than its target; its target is SIL 2 and it achieves SIL 2 (RRF 948 against 100), so it exceeds the target RRF but not the band; -04, -05 and -06 are as described. This affects no score. Confidence: high on found and missed; the three partials and the false alarm count are the judgement calls, with the ranges above. Read: the sealed findings file in full (findings, load reports, all 171 scenario verdicts, situation_as_found), the answer key, every sheet of every workbook and every CSV in data/u300, unit.json, and the U-200 adjudication for its field names only. Not read and not run: the checker's source, its tests and documentation, the session log, the README and the batch 3 generator. Project instructions (CLAUDE.md) were loaded into my context automatically; they name the check modules, the code ranges and the U-200 blind result but do not describe what individual checks do for U-300, and I did not use them in scoring.

### What this means

- The comparisons added after U-200 carried over to a unit they were not written for: voting, trip setpoint, final
  elements, units and the as-found interactions were found, and unit conversion sprang no trap.
- The misses are again comparisons nobody wrote: more than one channel of a SIF overridden at once, an alarm credited
  in the LOPA that shares its transmitter with the initiating control loop, the proof test interval after a change,
  and the times in the out-of-service register against the logic solver.
- C19 is now a known source of false alarms: it fired on all four credited alarms and the scorer accepted one, partly.
  It compares response time with the wrong clock for a pre-alarm (section 10 raised this).
- Scenario text is still wrong in places: a bypass is called acceptable while the other channel of the pair is
  already overridden; a closed out-of-service entry is reported as none; a removed alarm is treated as live.
- Section 9 applies again: this result is not overwritten, fixes are general rules, U-300 then becomes a
  regression test, and only a new unit counts as the next blind result.
