"""Batch 1 of the tag-location test documents for unit U-100. DUMMY DATA - not a real facility.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Four documents a real project holds besides the P&IDs, C&E, index, SRS and LOPA, written as the
registers they are usually exported as:

  U100-SILV-001-Rev-A.xlsx     SIL verification: per SIF the subsystems, voting, PFDavg, achieved SIL,
                               and the degraded case when one element is bypassed
  U100-MADB-001-Rev-A.xlsx     master alarm database (rationalisation record per alarm)
  U100-CFG-EXPORT-Rev-A.xlsx   DCS / SIS configuration export: points, alarms, SIS trips, overrides
  U100-MOC-REG-Rev-A.xlsx      management-of-change register
  U100-BATCH1-ANSWER-KEY.json  what was planted, where, and which question should find it
                               (not read by any loader - like U100-PIDS-DRAWN-CONTENT.json)

They agree with the existing U-100 documents except where a discrepancy is planted on purpose. Every
planted item is in PLANTED below with the cells that prove it ("evidence"); the answer key is written
from that list and tests/test_batch1_documents.py reads every evidence cell back from the files.

The questions (Q1-Q8) are the ones in docs/TAG_LOCATION_INVENTORY.xlsx: Q1 where-used, Q2 MOC impact,
Q3 bypass and compensating measures, Q4 SIF disabled, Q5 alarm shelved or disabled, Q6 document revised,
Q7 combined out-of-service picture, Q8 trip.

The SIL figures use the simplified low-demand equations (1oo1 lT/2, 1oo2 (lT)^2/3 + b.lT/2,
2oo2 lT, 2oo3 (lT)^2 + b.lT/2) with invented failure rates. They are test data, not a SIL verification.

    python scripts/make_dummy_batch1.py            # writes into data/
    python scripts/make_dummy_batch1.py --out DIR  # writes somewhere else (the test does this)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
STAMP = datetime(2026, 11, 12, 6, 0)          # fixed, so the files do not change from run to run
EXPORT_TIME = "2026-11-12 06:00"

SILV = "U100-SILV-001-Rev-A.xlsx"
MADB = "U100-MADB-001-Rev-A.xlsx"
CFG = "U100-CFG-EXPORT-Rev-A.xlsx"
MOCR = "U100-MOC-REG-Rev-A.xlsx"
KEY = "U100-BATCH1-ANSWER-KEY.json"

# Tags these documents name that the instrument index (U100-INST-INDEX Rev B) does not, and why.
# Anything else must be in the index. Alarm tags and SIF numbers are not index tags and are not listed.
NOT_IN_INDEX = {
    "PT-1001D": "SIF-100-03 initiator; already known (not in index, not drawn)",
    "PT-1001E": "added by MOC-2026-014, implemented, index not revised",
    "PT-1001F": "added by MOC-2026-014, implemented, index not revised",
    "LT-1002C": "proposed by MOC-2026-015, not installed",
    "FT-1007": "configured point left behind by cancelled MOC-2026-018",
    "HS-1001": "manual shutdown switch named in the SRS, never indexed",
    "MOS-1001A": "SIS maintenance override switch", "MOS-1001B": "SIS maintenance override switch",
    "MOS-1001C": "SIS maintenance override switch", "MOS-1002A": "SIS maintenance override switch",
    "MOS-1002B": "SIS maintenance override switch",
}


# ---------------------------------------------------------------- SIL arithmetic
HOURS_PER_MONTH = 730


def pfd(voting: str, lam: float, months: int, beta: float = 0.0) -> float:
    """Simplified low-demand PFDavg of one subsystem (lam per hour, proof-test interval in months)."""
    lt = lam * months * HOURS_PER_MONTH
    return {"1oo1": lt / 2, "1oo2": lt ** 2 / 3 + beta * lt / 2, "2oo2": lt,
            "2oo3": lt ** 2 + beta * lt / 2}[voting]


def sil(p: float) -> int:
    return 3 if p < 1e-3 else 2 if p < 1e-2 else 1 if p < 1e-1 else 0


LOGIC_SOLVER_PFD = 5e-5                        # SIS-LS-100, vendor certificate figure (dummy)

# SIF -> (target SIL, target RRF, sensor subsystem, final-element subsystem). Targets are the SRS's (Rev B).
# Each subsystem: (tags, voting, lambda_DU per hour, beta, proof-test interval in months).
SIFS = {
    "SIF-100-01": (2, 250, ("PT-1001A, PT-1001B, PT-1001C", "2oo3", 5e-7, 0.05, 12),
                   ("XV-1001, BDV-1001", "1oo2", 2e-6, 0.10, 24)),        # planted B1-01: SRS says 12 months
    "SIF-100-02": (1, 25, ("LT-1002A, LT-1002B, LT-1002C", "2oo3", 3e-6, 0.05, 12),   # planted B1-02: C not installed
                   ("XV-1001, XV-1002", "1oo2", 2e-6, 0.10, 12)),
    "SIF-100-03": (1, 15, ("PT-1001D", "1oo1", 5e-7, 0.0, 12),            # planted B1-04: MOC-2026-014 made it 2oo3
                   ("XV-1001", "1oo1", 2e-6, 0.0, 12)),
}


def sif_pfd(sensor, final) -> float:
    return pfd(sensor[1], sensor[2], sensor[4], sensor[3]) + LOGIC_SOLVER_PFD + pfd(final[1], final[2], final[4], final[3])


def as_installed_sif_100_02() -> float:
    """SIF-100-02 as the SIS is actually configured: 2oo2 on LT-1002A/B (the SILV assumes 2oo3 with LT-1002C)."""
    _, _, s, f = SIFS["SIF-100-02"]
    return sif_pfd(("LT-1002A, LT-1002B", "2oo2", s[2], s[3], s[4]), f)


# The degraded case: one element bypassed. (SIF, element bypassed, degraded voting the SILV assumes.)
DEGRADED = [
    ("SIF-100-01", "One of PT-1001A/B/C", "sensor", "1oo2"),            # planted B1-03: SIS configured to 2oo2
    ("SIF-100-01", "XV-1001 or BDV-1001", "final", "1oo1"),
    ("SIF-100-02", "One of LT-1002A/B/C", "sensor", "1oo2"),
    ("SIF-100-02", "XV-1001 or XV-1002", "final", "1oo1"),
    ("SIF-100-03", "PT-1001D", "sensor", None),                         # nothing left: function lost
]
SRS_MAX_BYPASS = {"SIF-100-01": "8 h", "SIF-100-02": "4 h", "SIF-100-03": "2 h"}


# ---------------------------------------------------------------- workbook helpers
def _book() -> Workbook:
    wb = Workbook()
    wb.properties.creator = "Bowden Simulators (dummy data)"
    wb.properties.created = wb.properties.modified = STAMP
    return wb


def _sheet(wb, name, title, doc, rev, status, header, rows, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = name
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Document No. {doc}    Rev {rev}    Status: {status}    (DUMMY DATA - not a real facility)"])
    ws.append([])
    ws.append(header)
    for c in ws[4]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(list(r))
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    return ws


def _g(x: float) -> float:
    return float(f"{x:.3g}")


# ---------------------------------------------------------------- 1. SIL verification
def silv_rows():
    summary, subsystems, degraded = [], [], []
    for sif_id, (tsil, trrf, s, f) in SIFS.items():
        ps, pf = pfd(s[1], s[2], s[4], s[3]), pfd(f[1], f[2], f[4], f[3])
        total = ps + LOGIC_SOLVER_PFD + pf
        summary.append([sif_id, tsil, "U100-SRS-001 Rev B", trrf, s[0], s[1], "SIS-LS-100", f[0], f[1], _g(ps), LOGIC_SOLVER_PFD,
                        _g(pf), _g(total), round(1 / total), sil(total), f"{s[4]} months", f"{f[4]} months",
                        "Meets target" if sil(total) >= tsil else "Does NOT meet target"])
        for name, sub in (("Sensors", s), ("Final elements", f)):
            subsystems.append([sif_id, name, sub[0], sub[1], sub[2], sub[3], sub[4] * HOURS_PER_MONTH,
                               _g(pfd(sub[1], sub[2], sub[4], sub[3])), "Generic data (dummy)"])
        subsystems.append([sif_id, "Logic solver", "SIS-LS-100", "1oo1D", "", "", "", LOGIC_SOLVER_PFD, "Vendor certificate (dummy)"])
    for sif_id, element, which, voting in DEGRADED:
        tsil, _, s, f = SIFS[sif_id]
        normal = s[1] if which == "sensor" else f[1]
        if voting is None:
            degraded.append([sif_id, element, normal, "None - function lost", "", "", SRS_MAX_BYPASS[sif_id],
                             "No protection while bypassed. Compensating measures per the SRS bypass conditions."])
            continue
        if which == "sensor":
            p = sif_pfd((s[0], voting, s[2], s[3], s[4]), f)
        else:
            p = sif_pfd(s, (f[0], voting, f[2], f[3], f[4]))
        degraded.append([sif_id, element, normal, voting, _g(p), sil(p), SRS_MAX_BYPASS[sif_id],
                         "Degraded voting assumed in the logic solver while one channel is overridden"])
    return summary, subsystems, degraded


def make_silv(out: Path) -> Path:
    summary, subsystems, degraded = silv_rows()
    wb = _book()
    t, d, r, st = "SIL VERIFICATION - UNIT 100 FEED GAS INLET", "U100-SILV-001", "A", "Issued for Design"
    _sheet(wb, "SIF Summary", t, d, r, st,
           ["SIF No.", "SIL Target", "Target Source", "RRF Target", "Sensor Tags", "Sensor Voting", "Logic Solver",
            "Final Element Tags", "Final Element Voting", "PFD Sensors", "PFD Logic Solver", "PFD Final Elements",
            "PFDavg", "RRF Achieved", "SIL Achieved", "Proof Test Interval - Sensors", "Proof Test Interval - Final Elements",
            "Result"], summary, first=True)
    _sheet(wb, "Subsystems", "SIL VERIFICATION - SUBSYSTEM DATA", d, r, st,
           ["SIF No.", "Subsystem", "Tags", "Voting", "Lambda DU (/h)", "Beta", "Proof Test Interval (h)", "PFDavg", "Data Source"],
           subsystems)
    _sheet(wb, "Degraded Operation", "SIL VERIFICATION - ONE ELEMENT BYPASSED", d, r, st,
           ["SIF No.", "Element Bypassed", "Normal Voting", "Degraded Voting Assumed", "PFDavg Degraded", "SIL Degraded",
            "SRS Max Bypass", "Note"], degraded)
    p = out / SILV
    wb.save(p)
    return p


# ---------------------------------------------------------------- 2. Master alarm database
MADB_HEADER = ["Alarm Tag", "Source Tag", "Description", "Alarm Type", "Setpoint", "Units", "Priority", "Alarm Class",
               "Cause", "Consequence of No Action", "Operator Action", "Time to Respond", "Deadband", "On-delay", "Off-delay",
               "IPL Credit", "LOPA Ref", "Rationalisation Outcome", "Implementation Status", "Rationalised", "Team"]
TEAM = "AB (alarm mgmt), ops rep, process eng (dummy)"
MADB_ROWS = [
    ["PAH-1001", "PT-1001A", "Feed gas inlet pressure high (pre-trip)", "Absolute high", "62", "barg", "High", "Safety",
     "PIC-1005 / PV-1005 fails open; upstream surge", "SIF-100-01 demand; overpressure of V-1002 if the trip fails",
     "Close HV-1001 or cut feed; check PIC-1005", "10 min", "1 barg", "2 s", "0 s", "Yes", "S-100-01", "Keep",
     "Implemented", "2026-03-18", TEAM],
    ["PAH-1005", "PT-1005", "Feed gas pressure high", "Absolute high", "60", "barg", "Medium", "Operational",
     "Pressure control drifting high", "Approach to PAH-1001 and the SIF-100-01 trip",
     "Check PIC-1005 output; take the loop to manual", "15 min", "1 barg", "5 s", "0 s", "No", "", "Keep",
     "Implemented", "2026-03-18", TEAM],
    # planted B1-08: the LOPA credits LAH-1006 as an IPL (S-100-02, PFD 0.1); the MADB says it is not one
    ["LAH-1006", "LT-1006", "Inlet KO drum level high", "Absolute high", "75", "%", "High", "Operational",
     "LIC-1006 / LV-1006 fails closed; slug from upstream", "Liquid carry-over to the compressor; SIF-100-02 demand",
     "Check LIC-1006 and LV-1006; reduce feed", "10 min", "2 %", "10 s", "0 s", "No", "", "Keep",
     "Implemented", "2026-03-18", TEAM],
    ["LAL-1006", "LT-1006", "Inlet KO drum level low", "Absolute low", "15", "%", "Low", "Operational",
     "LV-1006 stuck open", "Gas blow-by to the liquid outlet", "Close LV-1006 in manual", "20 min", "2 %", "10 s", "0 s",
     "No", "", "Keep", "Implemented", "2026-03-18", TEAM],
    ["FAL-1004", "FT-1004", "Feed gas inlet flow low", "Absolute low", "50", "t/h", "Low", "Operational",
     "Loss of upstream supply", "Compressor on recycle; approach to reverse flow",
     "Confirm upstream status; prepare for a SIF-100-03 trip", "15 min", "5 t/h", "10 s", "0 s", "No", "", "Keep",
     "Implemented", "2026-03-18", TEAM],
    # planted B1-15: the index says TT-1003 is indication only
    ["TAH-1003", "TT-1003", "Feed gas inlet temperature high", "Absolute high", "60", "degC", "Low", "Operational",
     "Upstream cooler out of service", "Reduced dehydration performance downstream", "Inform upstream; reduce rate",
     "30 min", "2 degC", "30 s", "0 s", "No", "", "Keep", "Implemented", "2026-03-18", TEAM],
    ["XA-1001", "XV-1001", "XV-1001 position does not match command", "Discrepancy", "20 s travel", "", "High", "Safety",
     "Valve stuck or limit switch fault", "Feed not isolated on a trip demand",
     "Confirm position in the field; isolate with HV-1001 if open", "5 min", "", "20 s", "0 s", "No", "", "Keep",
     "Implemented", "2026-03-18", TEAM],
    # planted B1-10: rationalised for MOC-2026-017, never configured
    ["PAL-1005", "PT-1005", "Feed gas pressure low (compensating alarm for SIF-100-03)", "Absolute low", "8", "barg", "High",
     "Safety", "Upstream depressurisation", "Reverse flow from V-1002 if SIF-100-03 is bypassed or fails",
     "Close XV-1001 from HS-1001", "5 min", "0.5 barg", "2 s", "0 s", "No", "", "Keep - new (MOC-2026-017)",
     "Approved - not implemented", "2026-10-15", TEAM],
]


def make_madb(out: Path) -> Path:
    wb = _book()
    _sheet(wb, "Alarms", "MASTER ALARM DATABASE - UNIT 100", "U100-MADB-001", "A", "Rationalised",
           MADB_HEADER, MADB_ROWS, first=True)
    p = out / MADB
    wb.save(p)
    return p


# ---------------------------------------------------------------- 3. DCS / SIS configuration export
POINTS_HEADER = ["Point Tag", "System", "Controller", "Block Type", "I/O Channel", "Range Low", "Range High", "Units",
                 "Description", "Loop"]
POINTS = [
    ["PT-1001A", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/01", 0, 100, "barg", "Feed gas inlet pressure A", ""],
    ["PT-1001B", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/02", 0, 100, "barg", "Feed gas inlet pressure B", ""],
    ["PT-1001C", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/03", 0, 100, "barg", "Feed gas inlet pressure C", ""],
    ["PT-1001D", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/04", 0, 100, "barg", "Feed gas inlet pressure D (low-low)", ""],
    ["PT-1001E", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/05", 0, 100, "barg", "Feed gas inlet pressure E (low-low)", ""],
    ["PT-1001F", "SIS", "SIS-LS-100", "AI", "SIS-AI-01/06", 0, 100, "barg", "Feed gas inlet pressure F (low-low)", ""],
    ["LT-1002A", "SIS", "SIS-LS-100", "AI", "SIS-AI-02/01", 0, 2000, "mm", "Inlet KO drum level A", ""],
    ["LT-1002B", "SIS", "SIS-LS-100", "AI", "SIS-AI-02/02", 0, 2000, "mm", "Inlet KO drum level B", ""],
    ["HS-1001", "SIS", "SIS-LS-100", "DI", "SIS-DI-01/01", "", "", "", "Manual shutdown push-button", ""],
    ["XV-1001", "SIS", "SIS-LS-100", "DO", "SIS-DO-01/01", "", "", "", "Feed gas inlet ESD valve", ""],
    ["XV-1002", "SIS", "SIS-LS-100", "DO", "SIS-DO-01/02", "", "", "", "KO drum liquid outlet ESD valve", ""],
    ["BDV-1001", "SIS", "SIS-LS-100", "DO", "SIS-DO-01/03", "", "", "", "KO drum blowdown valve", ""],
    # planted B1-09: the index says 0-100 barg (MOC-2026-016 re-ranged it; PAH-1005 sits at 60 barg)
    ["PT-1005", "DCS", "DCS-100-C01", "AI", "DCS-AI-03/01", 0, 60, "barg", "Feed gas pressure", "PIC-1005"],
    ["PV-1005", "DCS", "DCS-100-C01", "AO", "DCS-AO-03/01", 0, 100, "%", "Feed gas pressure control valve", "PIC-1005"],
    ["PIC-1005", "DCS", "DCS-100-C01", "PID", "", 0, 60, "barg", "Feed gas pressure control", "PIC-1005"],
    ["LT-1006", "DCS", "DCS-100-C01", "AI", "DCS-AI-03/02", 0, 2000, "mm", "Inlet KO drum level", "LIC-1006"],
    ["LV-1006", "DCS", "DCS-100-C01", "AO", "DCS-AO-03/02", 0, 100, "%", "Inlet KO drum level control valve", "LIC-1006"],
    ["LIC-1006", "DCS", "DCS-100-C01", "PID", "", 0, 100, "%", "Inlet KO drum level control", "LIC-1006"],
    ["TT-1003", "DCS", "DCS-100-C01", "AI", "DCS-AI-03/03", -50, 150, "degC", "Feed gas inlet temperature", ""],
    ["FT-1004", "DCS", "DCS-100-C01", "AI", "DCS-AI-03/04", 0, 500, "t/h", "Feed gas inlet flow", "FIC-1004"],
    ["FIC-1004", "DCS", "DCS-100-C01", "IND", "", 0, 500, "t/h", "Feed gas flow indication", "FIC-1004"],
    # planted B1-17: not in the index; its MOC was cancelled
    ["FT-1007", "DCS", "DCS-100-C01", "AI", "DCS-AI-03/05", 0, 200, "t/h", "Fuel gas take-off flow", ""],
]
ALARMS_HEADER = ["Alarm Tag", "Source Tag", "System", "Alarm Type", "Limit", "Units", "Priority", "Deadband", "On-delay",
                 "Enabled"]
ALARMS = [
    ["PAH-1001", "PT-1001A", "DCS", "HI", 64, "barg", "High", "1 barg", "2 s", "Yes"],        # B1-06: MADB 62
    ["PAH-1005", "PT-1005", "DCS", "HI", 60, "barg", "Medium", "1 barg", "5 s", "Yes"],
    ["LAH-1006", "LT-1006", "DCS", "HI", 75, "%", "Medium", "2 %", "10 s", "Yes"],           # B1-07: MADB High
    ["LAL-1006", "LT-1006", "DCS", "LO", 15, "%", "Low", "2 %", "10 s", "No"],               # B1-13: disabled
    ["FAL-1004", "FT-1004", "DCS", "LO", 50, "t/h", "Low", "5 t/h", "10 s", "Yes"],
    ["TAH-1003", "TT-1003", "DCS", "HI", 60, "degC", "Low", "2 degC", "30 s", "Yes"],
    ["TAL-1003", "TT-1003", "DCS", "LO", -10, "degC", "Low", "2 degC", "30 s", "Yes"],      # B1-14: not in MADB
    ["XA-1001", "XV-1001", "SIS", "DISC", "", "", "High", "", "20 s", "Yes"],
    ["PAHH-1001", "PT-1001A", "SIS", "TRIP NOTIFY", 68, "barg", "High", "", "0 s", "Yes"],  # B1-16: not in MADB
]
TRIPS_HEADER = ["SIF No.", "Logic Solver", "Initiators", "Voting", "Trip Setpoint", "Units", "Direction", "Final Elements",
                "Action", "Trip Enabled"]
TRIPS = [
    ["SIF-100-01", "SIS-LS-100", "PT-1001A, PT-1001B, PT-1001C", "2oo3", 68, "barg", "High", "XV-1001, BDV-1001",
     "XV-1001 close, BDV-1001 open", "Yes"],
    ["SIF-100-02", "SIS-LS-100", "LT-1002A, LT-1002B", "2oo2", 1750, "mm", "High", "XV-1001, XV-1002",       # B1-22
     "XV-1001 close, XV-1002 close", "Yes"],
    ["SIF-100-03", "SIS-LS-100", "PT-1001D, PT-1001E, PT-1001F", "2oo3", 5, "barg", "Low", "XV-1001",       # B1-05
     "XV-1001 close", "Yes"],
]
OVERRIDES_HEADER = ["Override Tag", "SIF No.", "Element", "Degraded Voting", "Max Duration (h)", "Timeout Action",
                    "Override Alarm Priority", "Active", "Active Since"]
OVERRIDES = [
    ["MOS-1001A", "SIF-100-01", "PT-1001A", "2oo2", 8, "Alarm only", "Medium", "No", ""],     # B1-03: SILV 1oo2
    ["MOS-1001B", "SIF-100-01", "PT-1001B", "2oo2", 8, "Alarm only", "Medium", "Yes", "2026-11-10 14:20"],  # B1-23
    ["MOS-1001C", "SIF-100-01", "PT-1001C", "2oo2", 8, "Alarm only", "Medium", "No", ""],
    ["MOS-1002A", "SIF-100-02", "LT-1002A", "1oo1", 8, "Alarm only", "Medium", "No", ""],     # B1-12: SRS 4 h
    ["MOS-1002B", "SIF-100-02", "LT-1002B", "1oo1", 8, "Alarm only", "Medium", "No", ""],
    # B1-11: no override for PT-1001D/E/F although the SRS permits a bypass of SIF-100-03
]


def make_config(out: Path) -> Path:
    wb = _book()
    d, r, st = "U100-CFG-EXPORT", "A", f"Configuration export {EXPORT_TIME} from DCS-100 and SIS-LS-100"
    _sheet(wb, "Points", "DCS / SIS CONFIGURATION EXPORT - UNIT 100 - POINTS", d, r, st, POINTS_HEADER, POINTS, first=True)
    _sheet(wb, "Alarms", "DCS / SIS CONFIGURATION EXPORT - UNIT 100 - ALARMS", d, r, st, ALARMS_HEADER, ALARMS)
    _sheet(wb, "SIS Trips", "DCS / SIS CONFIGURATION EXPORT - UNIT 100 - SIS TRIPS", d, r, st, TRIPS_HEADER, TRIPS)
    _sheet(wb, "Overrides", "DCS / SIS CONFIGURATION EXPORT - UNIT 100 - MAINTENANCE OVERRIDES", d, r, st,
           OVERRIDES_HEADER, OVERRIDES)
    p = out / CFG
    wb.save(p)
    return p


# ---------------------------------------------------------------- 4. MOC register
MOC_HEADER = ["MOC No.", "Title", "Change Type", "Status", "Raised", "Approved", "Implemented", "Closed", "Tags Affected",
              "Documents to Revise", "Documents Revised", "Originator", "Notes"]
MOCS = [
    ["MOC-2026-009", "Raise PAH-1001 alarm limit from 62 to 64 barg (nuisance alarms during feed surges)",
     "Alarm setting change", "Closed", "2026-05-12", "2026-05-20", "2026-06-03", "2026-06-10", "PAH-1001; PT-1001A",
     "U100-ALM-REG; U100-MADB-001; U100-ALM-PHIL", "", "Operations Supervisor (dummy)", ""],
    ["MOC-2026-011", "Reduce LAH-1006 priority from High to Medium (alarm-rate reduction)", "Alarm priority change",
     "Closed", "2026-06-22", "2026-07-01", "2026-07-08", "2026-07-15", "LAH-1006; LT-1006",
     "U100-MADB-001; U100-ALM-REG", "", "Alarm Management Engineer (dummy)", ""],
    ["MOC-2026-012", "Temporary: bypass LT-1002B for GWR probe replacement", "Temporary bypass", "Closed",
     "2026-08-10", "2026-08-12", "2026-08-14", "2026-08-14", "LT-1002B; MOS-1002B; SIF-100-02",
     "U100-OP-PROC-020", "U100-OP-PROC-020", "Maintenance Planner (dummy)",
     "Bypass 08:00-11:30 on 2026-08-14 (3.5 h), LAH-1006 confirmed active, operator on watch"],
    ["MOC-2026-014", "Upgrade SIF-100-03 initiator architecture from 1oo1 to 2oo3", "Voting change",
     "Implemented - close-out open", "2026-09-04", "2026-09-18", "2026-10-21", "",
     "SIF-100-03; PT-1001D; PT-1001E; PT-1001F; XV-1001",
     "U100-CE-CHART; U100-SRS-001; U100-SILV-001; U100-INST-INDEX; U100-LOOP-1001; U100-SIS-IO-001; U100-PTP-001; PID-100-001",
     "U100-SIS-IO-001", "Process Control Engineer (dummy)", "See data/moc/MOC-2026-014.json"],
    ["MOC-2026-015", "Add third level transmitter LT-1002C to SIF-100-02 to complete the 2oo3 group", "Add initiator",
     "Approved - awaiting implementation", "2026-09-04", "2026-10-02", "", "",
     "SIF-100-02; LT-1002A; LT-1002B; LT-1002C",
     "U100-CE-CHART; U100-SRS-001; U100-SILV-001; U100-INST-INDEX; U100-SIS-IO-001; U100-PTP-001; PID-100-001",
     "U100-SILV-001", "Functional Safety Engineer (dummy)", "See data/moc/MOC-2026-015.json"],
    ["MOC-2026-016", "Re-range PT-1005 from 0-100 to 0-60 barg for better control resolution", "Instrument re-range",
     "Closed", "2026-08-25", "2026-09-01", "2026-09-15", "2026-09-22", "PT-1005; PIC-1005",
     "U100-INST-INDEX; U100-LOOP-REG", "", "Instrument Engineer (dummy)", ""],
    ["MOC-2026-017", "Add PAL-1005 at 8 barg as the compensating alarm for any bypass of SIF-100-03",
     "New alarm", "In review", "2026-10-08", "", "", "", "PAL-1005; PT-1005; SIF-100-03",
     "U100-MADB-001; U100-ALM-REG; U100-SRS-001; U100-OP-PROC-020", "U100-MADB-001",
     "Functional Safety Engineer (dummy)", "Closes the gap in data/curated/compensating_measures_U-100.csv"],
    ["MOC-2026-018", "Install FT-1007 fuel gas take-off flow meter", "New instrument", "Cancelled", "2026-07-20",
     "2026-08-03", "", "2026-10-30", "FT-1007", "U100-INST-INDEX; PID-100-001", "",
     "Process Engineer (dummy)", "Cancelled: take-off not required"],
]


def make_moc(out: Path) -> Path:
    wb = _book()
    _sheet(wb, "Register", "MANAGEMENT OF CHANGE REGISTER - UNIT 100", "U100-MOC-REG", "A", "Live register",
           MOC_HEADER, MOCS, first=True)
    p = out / MOCR
    wb.save(p)
    return p


# ---------------------------------------------------------------- answer key
def _ev(doc, sheet, key, column, value):
    """One evidence cell: in file `doc`, sheet `sheet`, the row whose first column is `key`, column `column` reads `value`."""
    return {"file": doc, "sheet": sheet, "row": key, "column": column, "value": value}


def planted() -> list[dict]:
    _, _, s2, f2 = SIFS["SIF-100-02"]
    installed = as_installed_sif_100_02()
    silv_total = sif_pfd(s2, f2)
    return [
        dict(id="B1-01", kind="value_mismatch", questions=["Q6", "Q1"], tags=["XV-1001", "BDV-1001", "SIF-100-01"],
             documents=["U100-SILV-001", "U100-SRS-001"],
             finding="SIL verification takes a 24-month proof-test interval for the SIF-100-01 final elements; the SRS "
                     "specifies 12 months. Either the calculation or the SRS (and the proof-test procedure) is wrong.",
             evidence=[_ev(SILV, "SIF Summary", "SIF-100-01", "Proof Test Interval - Final Elements", "24 months")]),
        dict(id="B1-02", kind="calculation_assumes_uninstalled_equipment", questions=["Q1", "Q2", "Q6"],
             tags=["LT-1002C", "LT-1002A", "LT-1002B", "SIF-100-02"],
             documents=["U100-SILV-001", "U100-MOC-REG", "U100-CFG-EXPORT", "U100-INST-INDEX", "U100-LOPA-001"],
             finding=f"SIL verification credits a 2oo3 group with LT-1002C (PFDavg {_g(silv_total)}, RRF "
                     f"{round(1 / silv_total)}). LT-1002C is only proposed (MOC-2026-015 not implemented; not in the index); "
                     f"the SIS runs 2oo2 on LT-1002A/B. As installed PFDavg is about {_g(installed)}, RRF about "
                     f"{round(1 / installed)}: SIL {sil(installed)}. That meets the SRS target (SIL 1, RRF 25) but not the "
                     f"LOPA's (S-100-02, RRF 100). MOC-2026-015 lists the SILV as already revised.",
             evidence=[_ev(SILV, "Subsystems", "SIF-100-02", "Tags", "LT-1002A, LT-1002B, LT-1002C"),
                       _ev(MOCR, "Register", "MOC-2026-015", "Status", "Approved - awaiting implementation"),
                       _ev(MOCR, "Register", "MOC-2026-015", "Documents Revised", "U100-SILV-001"),
                       _ev(CFG, "SIS Trips", "SIF-100-02", "Voting", "2oo2")],
             computed={"silv_pfd": _g(silv_total), "as_installed_pfd": _g(installed),
                       "as_installed_rrf": round(1 / installed), "as_installed_sil": sil(installed)}),
        dict(id="B1-03", kind="degraded_mode_mismatch", questions=["Q3", "Q4"], tags=["PT-1001A", "PT-1001B", "PT-1001C",
             "MOS-1001A", "MOS-1001B", "MOS-1001C", "SIF-100-01"], documents=["U100-SILV-001", "U100-CFG-EXPORT"],
             finding="SIL verification assumes SIF-100-01 degrades to 1oo2 when one pressure transmitter is overridden; "
                     "the SIS overrides are configured to degrade to 2oo2 (less safe: one failed transmitter then defeats "
                     "the trip). The bypass case was verified for a configuration that is not the one running.",
             evidence=[_ev(SILV, "Degraded Operation", "SIF-100-01", "Degraded Voting Assumed", "1oo2"),
                       _ev(CFG, "Overrides", "MOS-1001A", "Degraded Voting", "2oo2")]),
        dict(id="B1-04", kind="document_not_revised_after_moc", questions=["Q2", "Q6"],
             tags=["PT-1001D", "PT-1001E", "PT-1001F", "SIF-100-03"], documents=["U100-SILV-001", "U100-MOC-REG", "U100-CFG-EXPORT"],
             finding="MOC-2026-014 (SIF-100-03 to 2oo3 on PT-1001D/E/F) is implemented in the SIS, but the SIL verification "
                     "still calculates 1oo1 on PT-1001D. Only U100-SIS-IO-001 of the eight listed documents has been revised.",
             evidence=[_ev(SILV, "SIF Summary", "SIF-100-03", "Sensor Voting", "1oo1"),
                       _ev(CFG, "SIS Trips", "SIF-100-03", "Voting", "2oo3"),
                       _ev(MOCR, "Register", "MOC-2026-014", "Documents Revised", "U100-SIS-IO-001")]),
        dict(id="B1-05", kind="config_differs_from_ce", questions=["Q2", "Q8"],
             tags=["PT-1001E", "PT-1001F", "SIF-100-03"], documents=["U100-CFG-EXPORT", "U100-CE-CHART", "U100-INST-INDEX"],
             finding="The SIS trips SIF-100-03 on 2oo3 of PT-1001D/E/F; the C&E (Rev A) still shows 1oo1 on PT-1001D. "
                     "PT-1001E and PT-1001F exist in the configuration but in no index, drawing or C&E (MOC-2026-014 close-out).",
             evidence=[_ev(CFG, "SIS Trips", "SIF-100-03", "Initiators", "PT-1001D, PT-1001E, PT-1001F"),
                       _ev(CFG, "Points", "PT-1001E", "System", "SIS")]),
        dict(id="B1-06", kind="config_differs_from_madb", questions=["Q1", "Q2", "Q3"], tags=["PAH-1001", "PT-1001A"],
             documents=["U100-CFG-EXPORT", "U100-MADB-001", "U100-INST-INDEX", "U100-MOC-REG", "U100-SRS-001", "U100-LOPA-001"],
             finding="PAH-1001 is configured at 64 barg; the MADB and the index alarm register say 62. MOC-2026-009 made the "
                     "change and closed without revising any document. The pre-alarm now sits 1 barg below the SRS trip "
                     "setpoint (65 barg), and it is credited as an IPL in LOPA S-100-01.",
             evidence=[_ev(CFG, "Alarms", "PAH-1001", "Limit", 64), _ev(MADB, "Alarms", "PAH-1001", "Setpoint", "62"),
                       _ev(MOCR, "Register", "MOC-2026-009", "Status", "Closed"),
                       _ev(MOCR, "Register", "MOC-2026-009", "Documents Revised", None)]),
        dict(id="B1-07", kind="config_differs_from_madb", questions=["Q2", "Q3"], tags=["LAH-1006", "LT-1006", "SIF-100-02"],
             documents=["U100-CFG-EXPORT", "U100-MADB-001", "U100-MOC-REG", "U100-LOPA-001", "U100-SRS-001"],
             finding="LAH-1006 is configured Medium; the MADB says High (MOC-2026-011, closed, no document revised). "
                     "LAH-1006 is an IPL in LOPA S-100-02, the SRS bypass condition for SIF-100-02, and the rank-1 "
                     "compensating measure for that SIF in the curated register.",
             evidence=[_ev(CFG, "Alarms", "LAH-1006", "Priority", "Medium"), _ev(MADB, "Alarms", "LAH-1006", "Priority", "High")]),
        dict(id="B1-08", kind="ipl_flag_differs_from_lopa", questions=["Q1", "Q5"], tags=["LAH-1006"],
             documents=["U100-MADB-001", "U100-LOPA-001"],
             finding="The MADB records LAH-1006 as Operational with no IPL credit; the LOPA credits it as an IPL "
                     "(S-100-02, PFD 0.1). An IPL alarm needs the class, testing and management of change that go with it.",
             evidence=[_ev(MADB, "Alarms", "LAH-1006", "IPL Credit", "No"),
                       _ev(MADB, "Alarms", "LAH-1006", "Alarm Class", "Operational")]),
        dict(id="B1-09", kind="range_change_breaks_alarm", questions=["Q2", "Q3", "Q7"], tags=["PT-1005", "PAH-1005", "SIF-100-01"],
             documents=["U100-CFG-EXPORT", "U100-INST-INDEX", "U100-MADB-001", "U100-MOC-REG", "U100-SRS-001"],
             finding="PT-1005 is configured 0-60 barg; the index says 0-100 (MOC-2026-016, closed, no document revised). "
                     "PAH-1005 at 60 barg is now at 100 % of span and cannot be relied on to annunciate. PAH-1005 is the "
                     "SRS bypass condition for SIF-100-01 and the rank-1 compensating measure for it; the MOC listed "
                     "neither the MADB, the SRS nor the compensating-measures register.",
             evidence=[_ev(CFG, "Points", "PT-1005", "Range High", 60), _ev(CFG, "Alarms", "PAH-1005", "Limit", 60),
                       _ev(MOCR, "Register", "MOC-2026-016", "Documents to Revise", "U100-INST-INDEX; U100-LOOP-REG")]),
        dict(id="B1-10", kind="rationalised_not_configured", questions=["Q3", "Q4"], tags=["PAL-1005", "PT-1005", "SIF-100-03"],
             documents=["U100-MADB-001", "U100-CFG-EXPORT", "U100-MOC-REG", "U100-SRS-001"],
             finding="PAL-1005 (8 barg, High) is rationalised in the MADB as the compensating alarm for SIF-100-03 but is "
                     "not configured (MOC-2026-017 in review). The SRS forbids bypassing SIF-100-03 without it, so today "
                     "SIF-100-03 cannot be bypassed in line with the SRS.",
             evidence=[_ev(MADB, "Alarms", "PAL-1005", "Implementation Status", "Approved - not implemented"),
                       _ev(MOCR, "Register", "MOC-2026-017", "Status", "In review")],
             absent=[{"file": CFG, "sheet": "Alarms", "row": "PAL-1005"}]),
        dict(id="B1-11", kind="bypass_permitted_no_override", questions=["Q3", "Q4"],
             tags=["PT-1001D", "PT-1001E", "PT-1001F", "SIF-100-03"], documents=["U100-SRS-001", "U100-CFG-EXPORT"],
             finding="The SRS permits a bypass of SIF-100-03 (max 2 h, with a temporary low-pressure alarm), but no "
                     "maintenance override is configured on PT-1001D/E/F. A bypass would have to be made by forcing, "
                     "outside the override alarm and timeout.",
             absent=[{"file": CFG, "sheet": "Overrides", "column": "SIF No.", "value": "SIF-100-03"}]),
        dict(id="B1-12", kind="override_timeout_exceeds_srs", questions=["Q3"], tags=["MOS-1002A", "MOS-1002B", "SIF-100-02"],
             documents=["U100-CFG-EXPORT", "U100-SRS-001"],
             finding="The overrides on LT-1002A/B time out after 8 h, and only raise an alarm; the SRS limits a bypass of "
                     "SIF-100-02 to 4 h.",
             evidence=[_ev(CFG, "Overrides", "MOS-1002A", "Max Duration (h)", 8),
                       _ev(CFG, "Overrides", "MOS-1002B", "Max Duration (h)", 8)]),
        dict(id="B1-13", kind="alarm_disabled_unrecorded", questions=["Q5", "Q7"], tags=["LAL-1006", "LT-1006"],
             documents=["U100-CFG-EXPORT", "U100-MADB-001"],
             finding="LAL-1006 is disabled in the DCS. The MADB says Keep / Implemented and the out-of-service register "
                     "(data/oos/out_of_service_U-100.csv) has no entry: an alarm out of service with no record.",
             evidence=[_ev(CFG, "Alarms", "LAL-1006", "Enabled", "No"),
                       _ev(MADB, "Alarms", "LAL-1006", "Implementation Status", "Implemented")]),
        dict(id="B1-14", kind="configured_not_rationalised", questions=["Q1"], tags=["TAL-1003", "TT-1003"],
             documents=["U100-CFG-EXPORT", "U100-MADB-001"],
             finding="TAL-1003 is configured and enabled but has no MADB record: an alarm nobody rationalised.",
             evidence=[_ev(CFG, "Alarms", "TAL-1003", "Enabled", "Yes")],
             absent=[{"file": MADB, "sheet": "Alarms", "row": "TAL-1003"}]),
        dict(id="B1-15", kind="function_differs_from_index", questions=["Q1"], tags=["TT-1003", "TAH-1003"],
             documents=["U100-MADB-001", "U100-INST-INDEX"],
             finding="The MADB rationalises TAH-1003 on TT-1003; the index says TT-1003 is indication only (and TT-1003 "
                     "is not drawn on any P&ID - existing finding).",
             evidence=[_ev(MADB, "Alarms", "TAH-1003", "Source Tag", "TT-1003")]),
        dict(id="B1-16", kind="trip_notification_not_rationalised", questions=["Q8", "Q1"], tags=["PAHH-1001", "SIF-100-01"],
             documents=["U100-CE-CHART", "U100-CFG-EXPORT", "U100-MADB-001"],
             finding="PAHH-1001 is a C&E effect of SIF-100-01 and is configured as a High-priority SIS trip notification, "
                     "but the MADB has no record of it. A trip is not an alarm: rationalise it as an event or remove it "
                     "from the alarm list.",
             evidence=[_ev(CFG, "Alarms", "PAHH-1001", "Alarm Type", "TRIP NOTIFY")],
             absent=[{"file": MADB, "sheet": "Alarms", "row": "PAHH-1001"}]),
        dict(id="B1-17", kind="orphan_configured_point", questions=["Q1", "Q2"], tags=["FT-1007"],
             documents=["U100-CFG-EXPORT", "U100-INST-INDEX", "U100-MOC-REG"],
             finding="FT-1007 is configured in the DCS but is in no index or drawing; MOC-2026-018, which would have "
                     "installed it, was cancelled. The point was never removed.",
             evidence=[_ev(CFG, "Points", "FT-1007", "Block Type", "AI"),
                       _ev(MOCR, "Register", "MOC-2026-018", "Status", "Cancelled")]),
        dict(id="B1-18", kind="configured_not_indexed", questions=["Q1"], tags=["PT-1001D", "HS-1001"],
             documents=["U100-CFG-EXPORT", "U100-INST-INDEX", "U100-SRS-001"],
             finding="PT-1001D and HS-1001 are configured SIS points that the index does not list (PT-1001D is an "
                     "existing finding; HS-1001 is named only in the SRS).",
             evidence=[_ev(CFG, "Points", "PT-1001D", "Controller", "SIS-LS-100"),
                       _ev(CFG, "Points", "HS-1001", "Block Type", "DI")]),
        dict(id="B1-19", kind="moc_impact_incomplete", questions=["Q2"], tags=["PAH-1001"],
             documents=["U100-MOC-REG", "U100-LOPA-001", "U100-SRS-001"],
             finding="MOC-2026-009 listed only alarm documents. PAH-1001 is credited in LOPA S-100-01 and sits between "
                     "normal operation and the SIF-100-01 trip, so the LOPA and the SRS were in its blast radius too.",
             evidence=[_ev(MOCR, "Register", "MOC-2026-009", "Documents to Revise", "U100-ALM-REG; U100-MADB-001; U100-ALM-PHIL")]),
        dict(id="B1-20", kind="moc_impact_incomplete", questions=["Q2", "Q3"], tags=["LAH-1006"],
             documents=["U100-MOC-REG", "U100-LOPA-001", "U100-SRS-001"],
             finding="MOC-2026-011 listed only the MADB and the alarm register. LAH-1006 is a LOPA IPL, the SRS bypass "
                     "condition for SIF-100-02 and its curated compensating measure.",
             evidence=[_ev(MOCR, "Register", "MOC-2026-011", "Documents to Revise", "U100-MADB-001; U100-ALM-REG")]),
        dict(id="B1-21", kind="moc_impact_incomplete", questions=["Q2", "Q3"], tags=["PT-1005", "PAH-1005"],
             documents=["U100-MOC-REG", "U100-MADB-001", "U100-SRS-001"],
             finding="MOC-2026-016 re-ranged PT-1005 without listing the alarms on it (PAH-1005 in the MADB) or the "
                     "SRS and compensating-measures register that rely on PAH-1005. See B1-09.",
             evidence=[_ev(MOCR, "Register", "MOC-2026-016", "Status", "Closed")]),
        dict(id="B1-22", kind="voting_mismatch", questions=["Q1", "Q8"], tags=["LT-1002A", "LT-1002B", "SIF-100-02"],
             documents=["U100-CFG-EXPORT", "U100-CE-CHART", "U100-SRS-001"],
             finding="The SIS votes SIF-100-02 2oo2 on LT-1002A/B; the C&E and the SRS say 2oo3. Corroborates the "
                     "existing finding (2oo3 declared with two transmitters) from a third document.",
             evidence=[_ev(CFG, "SIS Trips", "SIF-100-02", "Initiators", "LT-1002A, LT-1002B")]),
        dict(id="B1-23", kind="bypass_active_unrecorded", questions=["Q4", "Q7", "Q3"],
             tags=["MOS-1001B", "PT-1001B", "SIF-100-01", "PAH-1005", "PAH-1001"],
             documents=["U100-CFG-EXPORT", "U100-SRS-001"],
             finding="At the export (2026-11-12 06:00) MOS-1001B has been active since 2026-11-10 14:20 - about 40 h "
                     "against the SRS limit of 8 h - with no out-of-service register entry. SIF-100-01 is running 2oo2 on "
                     "PT-1001A/C. Its compensating measures are both impaired: PAH-1005 is at the top of PT-1005's span "
                     "(B1-09) and PAH-1001 was raised to 64 barg (B1-06). The combined picture (Q7) is the point.",
             evidence=[_ev(CFG, "Overrides", "MOS-1001B", "Active", "Yes"),
                       _ev(CFG, "Overrides", "MOS-1001B", "Active Since", "2026-11-10 14:20")]),
    ]


def answer_key() -> dict:
    return {
        "_note": "Answer key for batch 1 of the U-100 test documents. DUMMY DATA. Written by scripts/make_dummy_batch1.py; "
                 "not read by any loader. Evidence cells are checked by tests/test_batch1_documents.py.",
        "documents": [SILV, MADB, CFG, MOCR],
        "export_time": EXPORT_TIME,
        "not_in_index": NOT_IN_INDEX,
        "items": planted(),
    }


def write_all(out: Path = OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [make_silv(out), make_madb(out), make_config(out), make_moc(out)]
    key = out / KEY
    key.write_text(json.dumps(answer_key(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return paths + [key]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT))
    for p in write_all(Path(ap.parse_args().out)):
        print(p)
