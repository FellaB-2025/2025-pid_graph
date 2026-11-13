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
